# Recovered Data Label Design

**Date:** 2026-05-10
**Status:** Approved
**Parent Plan:** 2026-05-07-auto-density-recovery

## Problem Statement

The CID-font auto-recovery pipeline (`word_recovery.py`) successfully recovers numeric values from garbled PDFs, but stores them with position-based keys like `p161_r1_c1` instead of meaningful financial item names like `经营活动产生的现金流量净额`. This makes recovered data unusable for financial analysis.

**Example of current state:**
```json
"p161_r1_c0": 285449.0,
"p161_r1_c1": 390367.0,
```
**Desired state:**
```json
"经营活动产生的现金流量净额": 285449000000,
"其中：经营活动净流量": 390367000000,
```

## Architecture

### Core Insight

CID-font PDFs have two readable layers:
1. **Numbers** — extracted correctly via `extract_structured_numeric()` (commas, parentheses, decimals all parsed)
2. **Chinese text** — garbled in the text layer, but the layout structure (x/y positions, column alignment, row order) is preserved

The row-label association (which y-position corresponds to which financial item) can be recovered by matching row positions against:
- A reference PDF of the same company/year (preferred)
- Standard regulatory financial statement templates (fallback)

## Three-Layer Label Recovery Strategy

### Layer 1: Reference PDF Matching (Highest Priority)

**When:** At least one statement of the same company/year was successfully extracted (normal extraction).

**How:**
1. Load the reference extracted data (e.g., successfully extracted BS for 600016 2024)
2. For each reference row (label, value), compute its y-position from the source PDF
3. For each recovered row (position, value), find the nearest reference row by y-position
4. If y-distance < `Y_TOLERANCE` (15pt), assign the reference label to the recovered row
5. Validate by checking financial scale consistency

**Example:**
```
Reference BS page 96 row y=229.2 → "货币资金"
Recovered CF page 161 row y=229.2 → assign label "货币资金" (y-distance = 0)
```

**Y_TOLERANCE:** 15pt — empirically validated on 600016 (CF page 161 and BS page 96 have excellent row alignment at y=229.2).

### Layer 2: Standard Template Matching (Fallback)

**When:** No reference PDF available (all statements for company/year are garbled).

**How:**
1. Load standard template for the statement type (证监会格式):
   - `balance_sheet_template` — 65 standard line items in standard order
   - `income_statement_template` — 35 standard line items
   - `cash_flow_template` — 30 standard line items
2. For each recovered row, use row index to look up the corresponding template item
3. Filter: only assign labels to rows with |value| > 1000 (skip footnote-scale items)

**Templates are strict about order** — CF always starts with "一、经营活动产生的现金流量净额", etc. Recovery must respect this ordering.

### Layer 3: Financial Scale Validation

After label assignment, validate each labeled item:
- |v| < 1000 → mark as `footnote` (label assigned but low confidence)
- |v| >= 1000 → mark as `primary`
- Cross-statement validation: if same item appears in both BS and IS, |BS_value - IS_value| should be small (within 5% tolerance)

## File Structure

### New File: `extraction/label_recovery.py`

| Function | Responsibility |
|----------|---------------|
| `recover_labels(recovered_data, reference_data, statement_type)` | Main entry point — applies 3-layer strategy |
| `_load_template(statement_type)` | Returns standard template item list |
| `_match_by_y_position(recovered_rows, reference_rows, y_tolerance)` | Layer 1 logic |
| `_match_by_template(recovered_rows, statement_type)` | Layer 2 logic |
| `_validate_labels(labeled_data, statement_type)` | Layer 3 validation |
| `_build_labeled_flat_data(page_data, labels)` | Replaces position-keys with labels in flat_data |

### Modified Files

| File | Change |
|------|--------|
| `extraction/word_recovery.py` | After `recover_statement()`, call `recover_labels()` to relabel flat_data before returning |
| `extraction/extractors/base.py` | Quality gate integration unchanged (recovers dict already includes labels) |
| `extraction/storage/json_store.py` | No changes needed (flat_data key format updated by label recovery) |
| `extraction/word_recovery.py` | Add constants: `Y_TOLERANCE`, `MIN_PRIMARY_VALUE`, `BS_BALANCE_TOLERANCE` |

## Data Flow

```
PDF page
  ↓
extract_structured_numeric() → {rows: [{y, values}]}
  ↓
recover_statement(pages) → {page_data, flat_data}  ← current, position-keys only
  ↓
recover_labels(flat_data, reference_data, statement_type)
  ↓  layer 1: y-position matching vs reference PDF
  ↓  layer 2: template matching if no reference
  ↓  layer 3: scale validation
  ↓
{flat_data_with_labels, confidence_score, label_map}
  ↓
Result saved to JSON/SQLite with readable keys
```

## Key Data Structures

### Label Map Entry
```python
{
    "original_key": "p161_r1_c1",      # position-based key
    "label": "经营活动产生的现金流量净额",  # recovered label
    "y_position": 229.2,                # for debugging
    "value": 285449.0,
    "confidence": 0.95,                 # 1.0=reference-matched, 0.7=template-matched
    "is_primary": True,               # |value| >= 1000
}
```

### recover_labels() Signature
```python
def recover_labels(
    recovered_data: Dict,        # output from recover_statement()
    reference_data: Dict = None, # successfully extracted data of same company/year, or None
    statement_type: str = None, # "balance_sheet" | "income_statement" | "cash_flow"
) -> Dict:
    """
    Returns:
        {
            "flat_data": {"经营活动产生的现金流量净额": 285449000000, ...},
            "label_map": [...],  # per-key metadata with confidence
            "confidence": 0.85,  # overall confidence score
            "match_method": "reference" | "template",  # primary strategy used
        }
    """
```

## Standard Templates

### Balance Sheet Template (证监会格式, partial)
```
0:  流动资产合计
1:  非流动资产合计
2:  资产总计
3:  流动负债合计
4:  非流动负债合计
5:  负债合计
6:  所有者权益合计
7:  负债和所有者权益总计
...
```
Full template: 65 items covering assets (货币资金, 应收账款, 存货...), liabilities (短期借款, 应付账款...), equity (实收资本, 资本公积...).

### Cash Flow Template (partial)
```
0:  一、经营活动产生的现金流量净额
1:  其中：取得投资收益收到的现金
2:  处置固定资产、无形资产收回的现金净额
...
```

## Acceptance Criteria

1. **600016 CF recovery**: 633 values → at least 30 items get proper labels via reference matching against 600016 BS
2. **601628 recovery**: All three statements recovered without reference → labels via template matching
3. **Labeled data is usable**: Financial ratio calculations (gross margin = 营业利润/营业收入) work on labeled recovered data
4. **Confidence tracking**: Every labeled item has a confidence score (1.0=reference, 0.7=template)
5. **Graceful degradation**: If reference matching fails and template has no match, keep position-key (backward compatible)
6. **No regression**: Standard (non-recovered) extraction unchanged — existing JSON files valid

## Testing Strategy

| Test | Target |
|------|--------|
| Unit: label recovery on 600016 CF with BS reference | Layer 1: reference matching |
| Unit: label recovery on 601628 (no reference) | Layer 2: template matching |
| Unit: high-value items get `is_primary=True` | Layer 3: scale validation |
| Integration: full extractor recovery + labeling end-to-end | All layers |
| Regression: standard PDFs don't trigger recovery | Existing behavior unchanged |

## Constants

```python
Y_TOLERANCE = 15          # max y-distance (points) for reference row matching
MIN_PRIMARY_VALUE = 1000  # minimum |value| for primary item label
TEMPLATE_MATCH_MIN = 0.5  # minimum y-overlap ratio for template matching
```

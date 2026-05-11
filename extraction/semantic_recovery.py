# extraction/semantic_recovery.py
from typing import Dict, List, Optional, Tuple
from extraction.cas_vocabulary import BALANCE_SHEET_ITEMS, INCOME_STATEMENT_ITEMS, CASH_FLOW_ITEMS


class SemanticRecovery:
    """语义恢复模块 - 从CID字体PDF中恢复科目名称"""

    def __init__(self):
        self.vocabulary = {
            "balance_sheet": set(BALANCE_SHEET_ITEMS),
            "income_statement": set(INCOME_STATEMENT_ITEMS),
            "cash_flow": set(CASH_FLOW_ITEMS),
        }

    def recover_from_html(self, pdf_path: str, page_nums: List[int],
                          statement_type: str) -> Dict[str, float]:
        """从pdf2htmlEX转换的HTML中恢复科目名称和数值"""
        from extraction.parsers.html_converter import convert_pdf_to_html
        import os

        # 1. 转换为HTML
        html_path, temp_dir = convert_pdf_to_html(pdf_path)
        try:
            # 2. 解析HTML提取文本和位置
            items = self._parse_html_structure(html_path, page_nums)

            # 3. 词汇匹配 + 上下文推断
            result = self._match_vocabulary(items, statement_type)

            return result
        finally:
            # 清理临时文件
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)

    def _parse_html_structure(self, html_path: str, page_nums: List[int]) -> List[Dict]:
        """解析HTML结构，提取文本和位置"""
        from bs4 import BeautifulSoup
        items = []
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')

            for page in soup.find_all('div', class_='page'):
                page_num = int(page.get('data-page-num', 0))
                if page_num not in page_nums:
                    continue

                for elem in page.find_all(['span', 'div']):
                    text = elem.get_text(strip=True)
                    if not text:
                        continue
                    # 提取位置信息
                    style = elem.get('style', '')
                    x = self._parse_position(style, 'left')
                    y = self._parse_position(style, 'top')
                    items.append({'text': text, 'x': x, 'y': y, 'page': page_num})
        except Exception:
            pass
        return items

    def _parse_position(self, style: str, axis: str) -> Optional[float]:
        """从CSS样式中解析位置"""
        import re
        match = re.search(rf'{axis}:\s*(\d+\.?\d*)px', style)
        return float(match.group(1)) if match else None

    def _match_vocabulary(self, items: List[Dict], statement_type: str) -> Dict[str, float]:
        """词汇表匹配 + 上下文推断"""
        result = {}
        target_vocab = self.vocabulary.get(statement_type, set())

        # 按y位置分行
        rows = self._cluster_by_y(items)

        for row in rows:
            # 检查是否有数值
            numeric_vals = [i for i in row if self._is_numeric(i['text'])]
            if not numeric_vals:
                continue

            # 查找最近的文本作为科目名
            texts = [i['text'] for i in row if not self._is_numeric(i['text'])]
            item_name = self._infer_item_name_from_context(texts, target_vocab)

            if item_name:
                # 取第一个数值作为值
                val = self._parse_numeric(numeric_vals[0]['text'])
                result[item_name] = val

        return result

    def _is_numeric(self, text: str) -> bool:
        import re
        return bool(re.match(r'^[\d,\.\-()%]+$', text.strip()))

    def _parse_numeric(self, text: str) -> float:
        text = text.strip().replace(",", "").replace(" ", "")
        is_neg = text.startswith("(") and text.endswith(")")
        if is_neg:
            text = text[1:-1]
        try:
            return -float(text) if is_neg else float(text)
        except ValueError:
            return 0.0

    def _cluster_by_y(self, items: List[Dict], tolerance: float = 10) -> List[List[Dict]]:
        """按y位置分行"""
        if not items:
            return []
        sorted_items = sorted(items, key=lambda x: x.get('y', 0))
        rows = []
        current_row = [sorted_items[0]]
        current_y = sorted_items[0].get('y', 0)

        for item in sorted_items[1:]:
            y = item.get('y', 0)
            if abs(y - current_y) <= tolerance:
                current_row.append(item)
            else:
                rows.append(sorted(current_row, key=lambda x: x.get('x', 0)))
                current_row = [item]
                current_y = y

        if current_row:
            rows.append(sorted(current_row, key=lambda x: x.get('x', 0)))
        return rows

    def _infer_item_name_from_context(self, texts: List[str], vocab: set) -> Optional[str]:
        """从上下文文本推断科目名"""
        for text in texts:
            if text in vocab:
                return text
            # 模糊匹配
            for v in vocab:
                if text in v or v in text:
                    return v
        return None
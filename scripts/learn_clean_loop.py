#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto-loop: baseline → learn aliases → re-measure → write progress report.

Closes the loop between measurement and rule learning:
  1. Run scripts/baseline_2019_2022.py to get current match rates
  2. Run scripts/learn_sina_aliases.py to add new discovered aliases
  3. Re-run baseline to measure the delta
  4. Append delta to data/ground_truth_reports/cleaning_progression.md

Iterates up to --rounds times, stopping when improvement < --min-delta.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime


BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, "scripts")
REPORT_DIR = os.path.join(BASE, "data", "ground_truth_reports")
PROGRESSION_PATH = os.path.join(REPORT_DIR, "cleaning_progression.md")


def _run(cmd: list, timeout: int = 600) -> int:
    """Run subprocess, return exit code. Print output."""
    print(f"  $ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.stdout:
            # Print last 20 lines for brevity
            lines = result.stdout.split('\n')[-20:]
            for line in lines:
                print(f"    {line}")
        if result.returncode != 0 and result.stderr:
            print(f"  STDERR: {result.stderr[-500:]}")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after {timeout}s")
        return 124


def _read_match_rates(baseline_path: str) -> dict:
    """Read current baseline_2019_2022.json match rates."""
    if not os.path.exists(baseline_path):
        return {}
    with open(baseline_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        st: round(v["match_rate"], 4)
        for st, v in data.get("by_statement", {}).items()
    }


def _format_progression_row(round_num: int, before: dict, after: dict) -> str:
    """Format a single progression row as markdown table row."""
    cells = [f"| Round {round_num}"]
    for st in ["balance_sheet", "income_statement", "cash_flow"]:
        before_v = before.get(st, 0)
        after_v = after.get(st, 0)
        delta = after_v - before_v
        sign = "+" if delta >= 0 else ""
        cells.append(f"{before_v*100:.1f}% → {after_v*100:.1f}% ({sign}{delta*100:.2f}%)")
    return " | ".join(cells) + " |"


def _append_to_progression(md_row: str, before: dict, after: dict, after_va: dict) -> None:
    """Append a new section to cleaning_progression.md if file exists; else create."""
    section = f"""
## Auto-loop run @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

| Stage | BS | IS | CF |
|-------|----|----|-----|
{md_row}

Value accuracy after run: BS={after_va.get('balance_sheet', 0):.2%}, IS={after_va.get('income_statement', 0):.2%}, CF={after_va.get('cash_flow', 0):.2%}
"""
    if not os.path.exists(PROGRESSION_PATH):
        with open(PROGRESSION_PATH, "w", encoding="utf-8") as f:
            f.write("# Sina→RDS Cleaning Progression (Auto-loop)\n" + section)
    else:
        with open(PROGRESSION_PATH, "a", encoding="utf-8") as f:
            f.write(section)


def run_loop(rounds: int, min_delta: float, years: list, stocks: list, industries: list):
    """Run baseline → learn → re-measure for up to N rounds."""
    baseline_path = os.path.join(REPORT_DIR, "baseline_2019_2022.json")
    before = _read_match_rates(baseline_path)
    print(f"\nStarting loop: {rounds} rounds, min-delta={min_delta*100:.2f}%")
    print(f"Initial rates: {before}\n")

    # Build learn command
    learn_cmd = [sys.executable, os.path.join(SCRIPTS, "learn_sina_aliases.py")]
    if stocks: learn_cmd.extend(["--stocks"] + stocks)
    if industries: learn_cmd.extend(["--industries"] + industries)
    if years: learn_cmd.extend(["--years"] + [str(y) for y in years])

    # Build baseline command
    baseline_cmd = [sys.executable, os.path.join(SCRIPTS, "baseline_2019_2022.py")]

    for r in range(1, rounds + 1):
        print(f"\n===== Round {r} =====")

        # Step 1: learn (skip on first round since rules may already exist)
        if r > 1 or not before:
            rc = _run(learn_cmd, timeout=900)
            if rc != 0:
                print(f"  learner failed (rc={rc}), stopping")
                break

        # Step 2: baseline
        rc = _run(baseline_cmd, timeout=600)
        if rc != 0:
            print(f"  baseline failed (rc={rc}), stopping")
            break

        after = _read_match_rates(baseline_path)
        # Also fetch value_accuracy
        with open(baseline_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        after_va = {
            st: round(v["avg_value_accuracy"], 4)
            for st, v in data.get("by_statement", {}).items()
        }

        # Compute delta
        deltas = {st: after.get(st, 0) - before.get(st, 0) for st in after}
        max_delta = max(deltas.values()) if deltas else 0
        print(f"\n  After round {r}: {after}")
        print(f"  Deltas: {deltas} (max: {max_delta*100:.2f}%)")

        # Append to progression
        md_row = _format_progression_row(r, before, after)
        _append_to_progression(md_row, before, after, after_va)

        # Stop if improvement is too small
        if r > 1 and max_delta < min_delta:
            print(f"  Improvement {max_delta*100:.2f}% < {min_delta*100:.2f}% threshold, stopping")
            break

        before = after


def main() -> int:
    p = argparse.ArgumentParser(description="Auto-loop: learn aliases + re-measure")
    p.add_argument("--rounds", type=int, default=3, help="Max iterations")
    p.add_argument("--min-delta", type=float, default=0.005,
                   help="Stop if max statement improvement < this (0.005 = 0.5%)")
    p.add_argument("--years", nargs="+", default=None,
                   help="Years to scope the loop to. Default: 2019-2022")
    p.add_argument("--stocks", nargs="+", default=None)
    p.add_argument("--industries", nargs="+", default=None,
                   help="Industry names from rules/industry_aliases.yaml")
    args = p.parse_args()

    years = [int(y) for y in args.years] if args.years else [2019, 2020, 2021, 2022]
    run_loop(
        rounds=args.rounds,
        min_delta=args.min_delta,
        years=years,
        stocks=args.stocks,
        industries=args.industries,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

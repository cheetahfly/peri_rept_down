import os
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline_runs_on_two_stocks():
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(PROJECT_ROOT, "scripts", "clean_sina_pipeline.py"),
            "--stocks", "000001", "600000",
            "--years", "2019", "2020", "2021", "2022",
            "--output-dir", os.path.join(PROJECT_ROOT, "data", "exports_v2"),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    out_dir = os.path.join(PROJECT_ROOT, "data", "exports_v2")
    assert os.path.exists(os.path.join(out_dir, "sina_cleaned_balance_sheet.csv"))
    assert os.path.exists(os.path.join(out_dir, "sina_cleaned_income_statement.csv"))
    assert os.path.exists(os.path.join(out_dir, "sina_cleaned_cash_flow.csv"))
import os
import subprocess
import sys

import pandas as pd


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


def test_pipeline_tidy_output_has_rows():
    """Round 1: Tidy output should not be empty headers only."""
    out_dir = os.path.join(PROJECT_ROOT, "data", "exports_v2")
    for st in ("balance_sheet", "income_statement", "cash_flow"):
        path = os.path.join(out_dir, f"sina_cleaned_{st}.csv")
        df = pd.read_csv(path, encoding="utf-8-sig")
        assert len(df) > 0, f"{st} Tidy output is empty"
        for col in ("stock_code", "year", "field_code", "field_name", "value", "display_order"):
            assert col in df.columns, f"{st} missing column {col}"


def test_pipeline_tidy_uses_field_codes():
    """Round 1: Tidy output field_code should be F006N-style codes from field_order."""
    out_dir = os.path.join(PROJECT_ROOT, "data", "exports_v2")
    df = pd.read_csv(os.path.join(out_dir, "sina_cleaned_balance_sheet.csv"), encoding="utf-8-sig")
    assert len(df) > 0
    sample = df["field_code"].iloc[0]
    assert sample.startswith("F") and sample.endswith("N"), f"unexpected code: {sample}"
    assert df["display_order"].between(0, 110).all()


def test_pipeline_runs_with_guosen_source():
    """Pipeline should accept --source=guosen and call GuosenLoader.

    Uses sys.executable with a fresh PYTHONPATH so the subprocess
    doesn't inherit sys.modules contamination from prior tests in the
    parent pytest process. The subprocess must re-import pandas,
    astock_fundamentals, etc. from scratch.
    """
    import subprocess
    import os
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(PROJECT_ROOT, "scripts", "clean_sina_pipeline.py"),
            "--source", "guosen",
            "--stocks", "000001",
            "--years", "2019", "2020",
            "--output-dir", os.path.join(PROJECT_ROOT, "data", "exports_v2"),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        # Build minimal env: only PATH, TEMP, HOME + PYTHONPATH
        env={
            "PATH": os.environ.get("PATH", ""),
            "TEMP": os.environ.get("TEMP", ""),
            "TMP": os.environ.get("TMP", ""),
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
            "PATHEXT": os.environ.get("PATHEXT", ""),
            "PYTHONPATH": PROJECT_ROOT,
        },
    )
    # Should fail with GuosenAuthError (no API key), NOT ModuleNotFoundError
    # or argument error
    assert "GS_API_KEY" in result.stdout + result.stderr or "guosen" in result.stdout.lower()
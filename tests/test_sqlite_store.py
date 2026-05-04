# -*- coding: utf-8 -*-
"""
Unit tests for sqlite_store.py - SqliteStore class
"""
import os
import sys
import sqlite3
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extraction.storage.sqlite_store import SqliteStore


@pytest.fixture
def db_path():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def store(db_path):
    """Create a SqliteStore instance with temporary DB."""
    return SqliteStore(db_path)


@pytest.fixture
def store_with_data(store):
    """Create a SqliteStore with test data already saved."""
    test_data = {
        "found": True,
        "data": {
            "流动资产合计": 1000000.0,
            "流动负债合计": 500000.0,
        }
    }
    store.save("000001", 2024, "balance_sheet", test_data)
    store.save("000001", 2023, "balance_sheet", {"found": True, "data": {"资产": 900000.0}})
    store.save("000001", 2024, "income_statement", {"found": True, "data": {"净利润": 100000.0}})
    store.save("000002", 2024, "balance_sheet", {"found": True, "data": {"资产": 2000000.0}})
    return store


class TestInitDb:
    """Tests for _init_db method."""

    def test_creates_table(self, db_path):
        store = SqliteStore(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='extractions'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_creates_indexes(self, db_path):
        store = SqliteStore(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert any("idx_stock_code" in idx for idx in indexes)
        assert any("idx_report_year" in idx for idx in indexes)


class TestSave:
    """Tests for save method."""

    def test_save_success(self, store):
        data = {"found": True, "data": {"净利润": 100000.0}}
        result = store.save("000001", 2024, "balance_sheet", data)
        assert result is True

    def test_save_replace_on_duplicate(self, store):
        data1 = {"found": True, "data": {"流动资产": 100.0}}
        data2 = {"found": True, "data": {"流动资产": 200.0}}
        store.save("000001", 2024, "balance_sheet", data1)
        store.save("000001", 2024, "balance_sheet", data2)
        loaded = store.load("000001", 2024, "balance_sheet")
        assert loaded["data"]["流动资产"] == 200.0

    def test_save_and_load_round_trip(self, store):
        original = {"found": True, "data": {"营业收入": 5000000.0, "净利润": 500000.0}}
        store.save("000001", 2024, "income_statement", original)
        loaded = store.load("000001", 2024, "income_statement")
        assert loaded["found"] is True
        assert loaded["data"]["营业收入"] == 5000000.0
        assert loaded["data"]["净利润"] == 500000.0


class TestSaveAll:
    """Tests for save_all method."""

    def test_save_all_filters_non_found(self, store):
        extracted = {
            "balance_sheet": {"found": True, "data": {"资产": 100.0}},
            "income_statement": {"found": False, "data": {}},
            "cash_flow": {"found": True, "data": {"现金": 50.0}},
        }
        count = store.save_all("000001", 2024, extracted)
        assert count == 2

    def test_save_all_returns_count(self, store):
        extracted = {
            "balance_sheet": {"found": True, "data": {"资产": 100.0}},
            "income_statement": {"found": True, "data": {"利润": 50.0}},
        }
        count = store.save_all("000001", 2024, extracted)
        assert count == 2


class TestLoad:
    """Tests for load method."""

    def test_load_existing(self, store_with_data):
        result = store_with_data.load("000001", 2024, "balance_sheet")
        assert result is not None
        assert result["found"] is True

    def test_load_nonexistent(self, store):
        result = store.load("999999", 2024, "balance_sheet")
        assert result is None

    def test_load_by_year_filter(self, store_with_data):
        result = store_with_data.load("000001", 2023, "balance_sheet")
        assert result is not None
        assert result["data"] == {"资产": 900000.0}


class TestLoadAll:
    """Tests for load_all method."""

    def test_load_all_no_filter(self, store_with_data):
        results = store_with_data.load_all()
        assert len(results) == 4

    def test_load_all_by_stock_code(self, store_with_data):
        results = store_with_data.load_all(stock_code="000001")
        assert len(results) == 3

    def test_load_all_by_year(self, store_with_data):
        results = store_with_data.load_all(year=2024)
        assert len(results) == 3

    def test_load_all_by_stock_and_year(self, store_with_data):
        results = store_with_data.load_all(stock_code="000001", year=2024)
        assert len(results) == 2

    def test_load_all_returns_dict_formatted(self, store_with_data):
        results = store_with_data.load_all(stock_code="000001", year=2024)
        for r in results:
            assert "stock_code" in r
            assert "report_year" in r
            assert "statement_type" in r
            assert "data" in r


class TestListStocks:
    """Tests for list_stocks method."""

    def test_list_stocks(self, store_with_data):
        stocks = store_with_data.list_stocks()
        codes = [code for code, years in stocks]
        assert "000001" in codes
        assert "000002" in codes

    def test_list_stocks_years(self, store_with_data):
        stocks = dict(store_with_data.list_stocks())
        assert 2024 in stocks["000001"]
        assert 2023 in stocks["000001"]
        assert 2024 in stocks["000002"]


class TestDelete:
    """Tests for delete method."""

    def test_delete_specific_type(self, store_with_data):
        deleted = store_with_data.delete("000001", 2024, "balance_sheet")
        assert deleted == 1
        assert store_with_data.load("000001", 2024, "balance_sheet") is None

    def test_delete_all_types_for_year(self, store_with_data):
        deleted = store_with_data.delete("000001", 2024)
        assert deleted == 2
        assert store_with_data.load("000001", 2024, "income_statement") is None

    def test_delete_nonexistent(self, store):
        deleted = store.delete("999999", 2024, "balance_sheet")
        assert deleted == 0


class TestGetStats:
    """Tests for get_stats method."""

    def test_get_stats_total_records(self, store_with_data):
        stats = store_with_data.get_stats()
        assert stats["total_records"] == 4

    def test_get_stats_total_stocks(self, store_with_data):
        stats = store_with_data.get_stats()
        assert stats["total_stocks"] == 2

    def test_get_stats_year_range(self, store_with_data):
        stats = store_with_data.get_stats()
        assert stats["year_range"][0] == 2023
        assert stats["year_range"][1] == 2024

    def test_get_stats_by_type(self, store_with_data):
        stats = store_with_data.get_stats()
        assert stats["by_type"]["balance_sheet"] == 3
        assert stats["by_type"]["income_statement"] == 1

    def test_get_stats_empty(self, store):
        stats = store.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_stocks"] == 0


class TestGetMultiYearData:
    """Tests for get_multi_year_data method."""

    def test_get_multi_year_data(self, store_with_data):
        result = store_with_data.get_multi_year_data(
            "000001", "balance_sheet", [2023, 2024]
        )
        assert 2023 in result
        assert 2024 in result
        assert result[2024]["流动资产合计"] == 1000000.0

    def test_get_multi_year_data_missing_year(self, store_with_data):
        result = store_with_data.get_multi_year_data(
            "000001", "balance_sheet", [2020]
        )
        assert 2020 not in result


class TestGetMultiStockData:
    """Tests for get_multi_stock_data method."""

    def test_get_multi_stock_data(self, store_with_data):
        result = store_with_data.get_multi_stock_data(
            ["000001", "000002"], 2024, "balance_sheet"
        )
        assert ("000001", "000001") in result
        assert ("000002", "000002") in result
        assert result[("000001", "000001")]["流动资产合计"] == 1000000.0

    def test_get_multi_stock_data_empty_list(self, store):
        result = store.get_multi_stock_data([], 2024, "balance_sheet")
        assert result == {}


class TestExportTable:
    """Tests for export_table method."""

    def test_export_csv(self, store):
        import pandas as pd
        df = pd.DataFrame({"科目": ["资产", "负债"], "金额": [100, 50]})
        path = store.export_table(df, format="csv")
        try:
            assert os.path.exists(path)
            assert path.endswith(".csv")
            loaded = pd.read_csv(path)
            assert len(loaded) == 2
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_export_csv_default_path(self, store):
        import pandas as pd
        df = pd.DataFrame({"A": [1, 2]})
        path = store.export_table(df)
        try:
            assert os.path.exists(path)
            assert "export_" in os.path.basename(path)
        finally:
            if os.path.exists(path):
                os.unlink(path)

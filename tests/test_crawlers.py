# -*- coding: utf-8 -*-
"""
Unit tests for crawlers/downloader.py - ReportDownloader class
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crawlers.downloader import ReportDownloader


class TestGetRandomUA:
    """Tests for _get_random_ua method."""

    def test_returns_string(self):
        downloader = ReportDownloader()
        ua = downloader._get_random_ua()
        assert isinstance(ua, str)
        assert len(ua) > 0


class TestDownloadFile:
    """Tests for download_file method."""

    @pytest.fixture
    def temp_dir(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        os.unlink(path)
        yield path
        if os.path.exists(path):
            os.unlink(path)

    @patch.object(ReportDownloader, '_make_request')
    def test_download_success(self, mock_make_request, temp_dir):
        mock_make_request.return_value = b"PDF content here"
        downloader = ReportDownloader()
        result = downloader.download_file("/finalpage/2024/test.PDF", temp_dir)
        assert result is True
        assert os.path.exists(temp_dir)

    @patch.object(ReportDownloader, '_make_request')
    def test_download_empty_url_skips(self, mock_make_request):
        downloader = ReportDownloader()
        result = downloader.download_file("", "/some/path")
        assert result is False
        mock_make_request.assert_not_called()

    @patch.object(ReportDownloader, '_make_request')
    def test_skips_existing_file(self, mock_make_request, temp_dir):
        # Create a file at the target path
        with open(temp_dir, "w") as f:
            f.write("existing")
        downloader = ReportDownloader()
        result = downloader.download_file("/finalpage/2024/test.PDF", temp_dir)
        assert result is True
        # Should not have called _make_request since file exists
        mock_make_request.assert_not_called()

    @patch.object(ReportDownloader, '_make_request')
    def test_download_failure(self, mock_make_request, temp_dir):
        mock_make_request.return_value = None
        downloader = ReportDownloader()
        result = downloader.download_file("/finalpage/2024/test.PDF", temp_dir)
        assert result is False
        assert not os.path.exists(temp_dir)

    @patch.object(ReportDownloader, '_make_request')
    def test_url_construction_leading_slash(self, mock_make_request, temp_dir):
        mock_make_request.return_value = b"content"
        downloader = ReportDownloader()
        downloader.download_file("/finalpage/2024/test.PDF", temp_dir)
        call_args = mock_make_request.call_args[0][0]
        assert call_args.startswith("https://static.cninfo.com.cn")

    @patch.object(ReportDownloader, '_make_request')
    def test_url_construction_finalpage_prefix(self, mock_make_request, temp_dir):
        mock_make_request.return_value = b"content"
        downloader = ReportDownloader()
        downloader.download_file("finalpage/2024/test.PDF", temp_dir)
        call_args = mock_make_request.call_args[0][0]
        assert "static.cninfo.com.cn" in call_args

    @patch.object(ReportDownloader, '_make_request')
    def test_url_construction_full_url(self, mock_make_request, temp_dir):
        mock_make_request.return_value = b"content"
        downloader = ReportDownloader()
        downloader.download_file("http://example.com/file.PDF", temp_dir)
        call_args = mock_make_request.call_args[0][0]
        assert call_args == "http://example.com/file.PDF"

    @patch.object(ReportDownloader, '_make_request')
    def test_url_construction_relative(self, mock_make_request, temp_dir):
        mock_make_request.return_value = b"content"
        downloader = ReportDownloader()
        downloader.download_file("other/path/file.PDF", temp_dir)
        call_args = mock_make_request.call_args[0][0]
        assert "static.cninfo.com.cn" in call_args


class TestDownloadReports:
    """Tests for download_reports method."""

    @patch.object(ReportDownloader, 'download_file')
    def test_batch_all_success(self, mock_download_file):
        mock_download_file.return_value = True
        downloader = ReportDownloader()
        reports = [
            {"announcement_title": "Report 1", "announcement_url": "/url1"},
            {"announcement_title": "Report 2", "announcement_url": "/url2"},
        ]
        results = downloader.download_reports(reports, lambda r: f"/tmp/{r['announcement_title']}.PDF")
        assert results["success"] == 2
        assert results["failed"] == 0
        assert results["skipped"] == 0

    @patch.object(ReportDownloader, 'download_file')
    def test_batch_all_failed(self, mock_download_file):
        mock_download_file.return_value = False
        downloader = ReportDownloader()
        reports = [
            {"announcement_title": "Report 1", "announcement_url": "/url1"},
        ]
        results = downloader.download_reports(reports, lambda r: f"/tmp/{r['announcement_title']}.PDF")
        assert results["success"] == 0
        assert results["failed"] == 1

    @patch.object(ReportDownloader, 'download_file')
    def test_batch_skips_existing(self, mock_download_file):
        mock_download_file.return_value = True
        downloader = ReportDownloader()
        # Create a temp file to simulate existing file
        fd, path = tempfile.mkstemp(suffix=".PDF")
        os.close(fd)
        reports = [
            {"announcement_title": os.path.basename(path), "announcement_url": "/url1"},
        ]
        try:
            results = downloader.download_reports(reports, lambda r: path)
            assert results["skipped"] == 1
            assert results["success"] == 0
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestRateLimiting:
    """Tests for rate limiting behavior."""

    def test_rate_limit_no_error(self):
        # Verify _rate_limit runs without error
        from crawlers.downloader import _rate_limit
        # Should not raise, just enforce a small sleep
        _rate_limit()
        _rate_limit()  # second call should sleep

    def test_rate_limit_uses_lock(self):
        from crawlers.downloader import _rate_lock, _min_interval
        assert _rate_lock is not None
        assert _min_interval >= 1.0

from unittest.mock import Mock

import pytest
import requests

from src import extract
from src.errors import ExtractionError


@pytest.mark.parametrize("page,suffix", [(1, "/"), (2, "/page2"), (50, "/page50")])
def test_page_urls(page, suffix):
    assert extract.build_page_url(page) == extract.BASE_URL + suffix


@pytest.mark.parametrize("page", [0, -1, 51, None, "2", True, 1.5])
def test_invalid_page(page):
    with pytest.raises(ExtractionError):
        extract.build_page_url(page)


def test_retry_policy_and_session_failure(monkeypatch):
    session = extract.build_session()
    retry = session.get_adapter("https://").max_retries
    assert retry.total == 3
    assert 429 in retry.status_forcelist and retry.respect_retry_after_header
    assert retry.allowed_methods == ["GET"]
    session.close()
    monkeypatch.setattr(extract.requests, "Session", Mock(side_effect=OSError))
    with pytest.raises(ExtractionError):
        extract.build_session()


def test_fetch_success_timeout_and_http_error():
    session = Mock()
    session.get.return_value.content = b"ok"
    assert extract.fetching_content("https://example.invalid", session) == b"ok"
    session.get.assert_called_once_with("https://example.invalid", timeout=(10, 30))
    session.get.side_effect = requests.Timeout("connection secret must not leak")
    with pytest.raises(ExtractionError, match="HTTP request failed"):
        extract.fetching_content("https://example.invalid", session)


@pytest.mark.parametrize("failure", [requests.HTTPError("503"), None])
def test_http_error_or_empty_body(failure):
    session = Mock()
    session.get.return_value.raise_for_status.side_effect = failure
    session.get.return_value.content = b""
    with pytest.raises(ExtractionError):
        extract.fetching_content("https://example.invalid", session)


@pytest.mark.parametrize("unavailable", [False, True])
def test_parser_two_price_tags_and_label_order(html_page, unavailable):
    rows = extract.parse_page(html_page(unavailable=unavailable), "now", 1)
    assert len(rows) == 20
    assert rows[0]["Price"] == ("Price Unavailable" if unavailable else "$102.15")
    assert rows[0]["Colors"] == "3 Colors"
    assert rows[0]["Gender"] == "Gender: Women"
    assert rows[0]["source_page"] == 1


def test_parser_missing_fields_are_quarantinable(html_page):
    html = html_page(missing_title=True).replace(b'<span class="price">$102.15</span>', b"")
    row = extract.parse_page(html, "now", 1)[0]
    assert row["Title"] is None and row["Price"] is None


@pytest.mark.parametrize("count", [0, 19, 21])
def test_parser_rejects_layout_drift(html_page, count):
    with pytest.raises(ExtractionError):
        extract.parse_page(html_page(count=count), "now", 1)


def test_all_pages_timestamp_lineage_and_caller_owned_session(html_page, monkeypatch):
    session = Mock()
    session.get.side_effect = [Mock(content=html_page(page=i)) for i in range(1, 51)]
    sleep = Mock()
    monkeypatch.setattr(extract.time, "sleep", sleep)
    rows = extract.scrape_main(50, session=session)
    assert len(rows) == 1000
    assert set(rows.source_page) == set(range(1, 51))
    assert rows.timestamp.str.contains("T").all()
    assert session.get.call_count == 50 and sleep.call_count == 49
    session.close.assert_not_called()


def test_owned_session_closed_after_success_and_failure(html_page, monkeypatch):
    session = Mock()
    session.get.return_value.content = html_page()
    monkeypatch.setattr(extract, "build_session", Mock(return_value=session))
    extract.scrape_main(1)
    session.close.assert_called_once()
    session.reset_mock()
    session.get.side_effect = requests.ConnectionError()
    with pytest.raises(ExtractionError):
        extract.scrape_main(1)
    session.close.assert_called_once()


def test_repeated_page_and_negative_delay(html_page):
    session = Mock()
    session.get.return_value.content = html_page()
    with pytest.raises(ExtractionError):
        extract.scrape_main(2, delay=0, session=session)
    with pytest.raises(ExtractionError):
        extract.scrape_main(1, delay=-1, session=session)

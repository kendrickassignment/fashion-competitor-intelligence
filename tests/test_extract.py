"""
test_extract.py
----------------
Unit test untuk modul utils/extract.py.

Seluruh pengujian yang melibatkan request HTTP menggunakan mock
(unittest.mock) sehingga tidak memerlukan koneksi internet sungguhan
ke https://fashion-studio.dicoding.dev/.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extract import (
    build_page_url,
    fetch_page,
    parse_product_card,
    parse_page,
    scrape_main,
    BASE_URL,
)
from tests.fixtures import SAMPLE_PAGE_HTML, EMPTY_PAGE_HTML
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------
# build_page_url
# ---------------------------------------------------------------------

def test_build_page_url_first_page():
    url = build_page_url(1)
    assert url == f"{BASE_URL}/"


def test_build_page_url_other_page():
    url = build_page_url(5)
    assert url == f"{BASE_URL}/page5"


def test_build_page_url_invalid_number_returns_none():
    assert build_page_url(0) is None
    assert build_page_url(-3) is None
    assert build_page_url(None) is None


# ---------------------------------------------------------------------
# fetch_page
# ---------------------------------------------------------------------

def test_fetch_page_success():
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "<html>ok</html>"
    mock_response.raise_for_status.return_value = None
    mock_session.get.return_value = mock_response

    result = fetch_page("https://fashion-studio.dicoding.dev/", session=mock_session)

    assert result == "<html>ok</html>"
    mock_session.get.assert_called_once()


def test_fetch_page_handles_request_exception():
    mock_session = MagicMock()
    mock_session.get.side_effect = requests.exceptions.ConnectionError("network down")

    result = fetch_page("https://fashion-studio.dicoding.dev/", session=mock_session)

    assert result is None


def test_fetch_page_handles_http_error():
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
    mock_session.get.return_value = mock_response

    result = fetch_page("https://fashion-studio.dicoding.dev/page999", session=mock_session)

    assert result is None


def test_fetch_page_handles_unexpected_exception():
    mock_session = MagicMock()
    mock_session.get.side_effect = ValueError("unexpected")

    result = fetch_page("https://fashion-studio.dicoding.dev/", session=mock_session)

    assert result is None


# ---------------------------------------------------------------------
# parse_product_card
# ---------------------------------------------------------------------

def _get_cards(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find_all("div", class_="collection-card")


def test_parse_product_card_valid_product():
    cards = _get_cards(SAMPLE_PAGE_HTML)
    result = parse_product_card(cards[1], timestamp="2026-06-17T00:00:00")

    assert result["Title"] == "T-shirt 2"
    assert result["Price"] == "$102.15"
    assert "3.9" in result["Rating"]
    assert result["Colors"] == "3 Colors"
    assert result["Size"] == "Size: M"
    assert result["Gender"] == "Gender: Women"
    assert result["timestamp"] == "2026-06-17T00:00:00"


def test_parse_product_card_unknown_product():
    cards = _get_cards(SAMPLE_PAGE_HTML)
    result = parse_product_card(cards[0], timestamp="2026-06-17T00:00:00")

    assert result["Title"] == "Unknown Product"
    assert result["Price"] == "$100.00"
    assert "Invalid Rating" in result["Rating"]


def test_parse_product_card_price_unavailable():
    cards = _get_cards(SAMPLE_PAGE_HTML)
    result = parse_product_card(cards[2], timestamp="2026-06-17T00:00:00")

    assert result["Title"] == "Pants 16"
    assert result["Price"] == "Price Unavailable"
    assert "Not Rated" in result["Rating"]
    assert result["Colors"] == "8 Colors"


def test_parse_product_card_handles_malformed_card_gracefully():
    # Objek bukan elemen BeautifulSoup yang valid -> harus memicu
    # exception internal yang ditangani dan mengembalikan None.
    broken_card = object()
    result = parse_product_card(broken_card, timestamp="2026-06-17T00:00:00")
    assert result is None


# ---------------------------------------------------------------------
# parse_page
# ---------------------------------------------------------------------

def test_parse_page_returns_all_cards():
    results = parse_page(SAMPLE_PAGE_HTML, timestamp="2026-06-17T00:00:00")
    assert len(results) == 4
    titles = [r["Title"] for r in results]
    assert "T-shirt 2" in titles
    assert "Hoodie 3" in titles


def test_parse_page_empty_collection_returns_empty_list():
    results = parse_page(EMPTY_PAGE_HTML, timestamp="2026-06-17T00:00:00")
    assert results == []


def test_parse_page_handles_empty_html_string():
    results = parse_page("", timestamp="2026-06-17T00:00:00")
    assert results == []


def test_parse_page_handles_none_html():
    results = parse_page(None, timestamp="2026-06-17T00:00:00")
    assert results == []


# ---------------------------------------------------------------------
# scrape_main
# ---------------------------------------------------------------------

@patch("src.extract.fetch_page")
def test_scrape_main_aggregates_multiple_pages(mock_fetch_page):
    mock_fetch_page.side_effect = [SAMPLE_PAGE_HTML, SAMPLE_PAGE_HTML, EMPTY_PAGE_HTML]

    results = scrape_main(total_pages=3, delay=0)

    assert len(results) == 8  # 4 produk x 2 halaman berisi data
    assert mock_fetch_page.call_count == 3


@patch("src.extract.fetch_page")
def test_scrape_main_skips_failed_pages(mock_fetch_page):
    mock_fetch_page.side_effect = [SAMPLE_PAGE_HTML, None, SAMPLE_PAGE_HTML]

    results = scrape_main(total_pages=3, delay=0)

    assert len(results) == 8
    assert mock_fetch_page.call_count == 3


@patch("src.extract.build_page_url")
def test_scrape_main_handles_all_invalid_urls(mock_build_url):
    mock_build_url.return_value = None

    results = scrape_main(total_pages=2, delay=0)

    assert results == []


@patch("src.extract.fetch_page", side_effect=Exception("boom"))
def test_scrape_main_catches_unexpected_exception(mock_fetch_page):
    results = scrape_main(total_pages=2, delay=0)
    assert isinstance(results, list)

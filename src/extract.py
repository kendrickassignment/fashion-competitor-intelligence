"""Bounded, polite extraction. Never publish an incomplete catalog."""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.errors import ExtractionError

BASE_URL = "https://fashion-studio.dicoding.dev"
FIELDS = ["Title", "Price", "Rating", "Colors", "Size", "Gender"]
logger = logging.getLogger(__name__)


def build_session():
    try:
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"], respect_retry_after_header=True)
        session.mount("https://", HTTPAdapter(max_retries=retry))
        session.headers.update({"User-Agent": "FashionResearchETL/2.0 (educational catalog research)"})
        return session
    except Exception as exc:
        raise ExtractionError("Cannot initialize HTTP session") from exc


def build_page_url(page_number):
    try:
        if type(page_number) is not int or not 1 <= page_number <= 50:
            raise ValueError("Page must be an integer in 1..50")
        return f"{BASE_URL}/" if page_number == 1 else f"{BASE_URL}/page{page_number}"
    except (TypeError, ValueError) as exc:
        raise ExtractionError("Invalid page number") from exc


def fetching_content(url, session):
    try:
        response = session.get(url, timeout=(10, 30))
        response.raise_for_status()
        if not response.content:
            raise ValueError("Empty response")
        return response.content
    except (requests.RequestException, ValueError) as exc:
        raise ExtractionError("HTTP request failed or returned empty content") from exc


def parse_page(html, timestamp, page_number):
    """Use labels, not paragraph positions; preserve bad values for quarantine."""
    try:
        cards = BeautifulSoup(html, "html.parser").select(".collection-card")
        if len(cards) != 20:
            raise ValueError("Expected exactly 20 product cards")
        records = []
        for card in cards:
            title, price = card.select_one(".product-title"), card.select_one(".price")
            record = dict.fromkeys(FIELDS)
            record.update(Title=title.get_text(" ", strip=True) if title else None,
                          Price=price.get_text(" ", strip=True) if price else None)
            for paragraph in card.select(".product-details p"):
                text = paragraph.get_text(" ", strip=True)
                if text.startswith("Rating:"):
                    record["Rating"] = text
                elif text.endswith((" Colors", " Color")):
                    record["Colors"] = text
                elif text.startswith("Size:"):
                    record["Size"] = text
                elif text.startswith("Gender:"):
                    record["Gender"] = text
            record.update(timestamp=timestamp, source_page=page_number,
                          source_url=build_page_url(page_number))
            records.append(record)
        return records
    except Exception as exc:
        raise ExtractionError(f"Source structure invalid on page {page_number}") from exc


def scrape_main(total_pages=50, delay=0.25, session=None):
    """Return every requested page or raise; injected sessions remain caller-owned."""
    owned = session is None
    try:
        build_page_url(total_pages)
        if delay < 0:
            raise ValueError("Delay cannot be negative")
        session = build_session() if owned else session
        records, fingerprints = [], set()
        for page in range(1, total_pages + 1):
            html = fetching_content(build_page_url(page), session)
            batch = parse_page(html, datetime.now(timezone.utc).isoformat(), page)
            content = [{field: row[field] for field in FIELDS} for row in batch]
            fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
            if fingerprint in fingerprints:
                raise ExtractionError(f"Repeated page payload on page {page}")
            fingerprints.add(fingerprint)
            records.extend(batch)
            logger.info("extracted page=%s/%s rows=%s", page, total_pages, len(records))
            if page < total_pages:
                time.sleep(delay)
        return pd.DataFrame(records)
    except Exception as exc:
        raise ExtractionError("Catalog extraction failed; no partial dataset published") from exc
    finally:
        if owned and session is not None:
            session.close()

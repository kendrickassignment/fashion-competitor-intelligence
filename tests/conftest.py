from unittest.mock import Mock

import pandas as pd
import pytest

from src.transform import transform_main


@pytest.fixture(autouse=True)
def no_external_http(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unit tests must not access external HTTP services")
    monkeypatch.setattr("requests.sessions.Session.request", blocked)
    monkeypatch.setattr("httplib2.Http.request", blocked)


@pytest.fixture
def raw_row():
    return {"Title": "T-shirt 2", "Price": "$102.15", "Rating": "Rating: ⭐ 3.9 / 5",
            "Colors": "3 Colors", "Size": "Size: M", "Gender": "Gender: Women",
            "timestamp": "2026-10-26T02:00:00+00:00", "source_page": 1,
            "source_url": "https://fashion-studio.dicoding.dev/"}


@pytest.fixture
def clean(raw_row):
    return transform_main(pd.DataFrame([raw_row])).clean


@pytest.fixture
def raw_page(raw_row):
    return pd.DataFrame([{**raw_row, "Title": f"T-shirt {i}"} for i in range(1, 21)])


@pytest.fixture
def html_page():
    def make(page=1, unavailable=False, missing_title=False, count=20):
        cards = []
        for i in range(count):
            title = "" if missing_title else f'<h3 class="product-title">T-shirt {20*(page-1)+i+1}</h3>'
            price = '<p class="price">Price Unavailable</p>' if unavailable else (
                '<div class="price-container"><span class="price">$102.15</span></div>')
            cards.append(f'''<div class="collection-card"><div class="product-details">
                {title}{price}<p>Gender: Women</p><p>Size: M</p>
                <p>Rating: ⭐ 3.9 / 5</p><p>3 Colors</p></div></div>''')
        return "".join(cards).encode()
    return make


@pytest.fixture
def sheet_service(clean):
    service = Mock()
    api = service.spreadsheets.return_value
    api.get.return_value.execute.return_value = {"sheets": []}
    api.values.return_value.get.return_value.execute.return_value = {
        "values": [list(clean.columns)] + clean.values.tolist()}
    return service

"""
test_analytics.py
------------------
Unit test untuk modul src/analytics.py.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analytics import generate_summary, save_summary


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        [
            {"Title": "T-shirt 2", "Price": 1000000.0, "Rating": 4.0, "Colors": 3,
             "Size": "M", "Gender": "Women", "timestamp": "t"},
            {"Title": "T-shirt 8", "Price": 2000000.0, "Rating": 5.0, "Colors": 3,
             "Size": "L", "Gender": "Women", "timestamp": "t"},
            {"Title": "Hoodie 3", "Price": 3000000.0, "Rating": 4.8, "Colors": 3,
             "Size": "L", "Gender": "Unisex", "timestamp": "t"},
        ]
    )


def test_generate_summary_basic_stats(sample_df):
    summary = generate_summary(sample_df)

    assert summary["total_products"] == 3
    assert summary["price_idr"]["average"] == pytest.approx(2000000.0)
    assert summary["price_idr"]["min"] == 1000000.0
    assert summary["price_idr"]["max"] == 3000000.0


def test_generate_summary_groups_by_gender_and_size(sample_df):
    summary = generate_summary(sample_df)

    assert summary["average_price_by_gender"]["Women"] == pytest.approx(1500000.0)
    assert summary["average_price_by_gender"]["Unisex"] == pytest.approx(3000000.0)
    assert summary["average_price_by_size"]["M"] == pytest.approx(1000000.0)


def test_generate_summary_rating_stats(sample_df):
    summary = generate_summary(sample_df)
    assert summary["rating"]["products_rating_4_5_or_above"] == 2


def test_generate_summary_category_breakdown(sample_df):
    summary = generate_summary(sample_df)
    assert summary["product_count_by_category"]["T-shirt"] == 2
    assert summary["product_count_by_category"]["Hoodie"] == 1


def test_generate_summary_top_rated_products(sample_df):
    summary = generate_summary(sample_df)
    top_titles = [item["Title"] for item in summary["top_5_rated_products"]]
    assert top_titles[0] == "T-shirt 8"  # rating tertinggi (5.0)


def test_generate_summary_handles_empty_dataframe():
    summary = generate_summary(pd.DataFrame())
    assert summary["total_products"] == 0


def test_generate_summary_handles_none_input():
    summary = generate_summary(None)
    assert summary["total_products"] == 0


def test_save_summary_writes_json_file(tmp_path, sample_df):
    summary = generate_summary(sample_df)
    file_path = save_summary(summary, str(tmp_path), run_date="2026-06-22")

    assert file_path is not None
    assert os.path.exists(file_path)
    assert file_path.endswith("analytics_summary_2026-06-22.json")

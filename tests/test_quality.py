"""
test_quality.py
----------------
Unit test untuk modul src/quality.py.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.quality import generate_quality_report, save_quality_report


@pytest.fixture
def raw_data():
    return [
        {"Title": "Unknown Product", "Price": "$100.00", "Rating": "Rating: ⭐ Invalid Rating / 5",
         "Colors": "5 Colors", "Size": "Size: M", "Gender": "Gender: Men", "timestamp": "t"},
        {"Title": "T-shirt 2", "Price": "$102.15", "Rating": "Rating: ⭐ 3.9 / 5",
         "Colors": "3 Colors", "Size": "Size: M", "Gender": "Gender: Women", "timestamp": "t"},
        {"Title": "Pants 16", "Price": "Price Unavailable", "Rating": "Rating: Not Rated",
         "Colors": "8 Colors", "Size": "Size: S", "Gender": "Gender: Men", "timestamp": "t"},
        {"Title": "Hoodie 3", "Price": "$496.88", "Rating": "Rating: ⭐ 4.8 / 5",
         "Colors": "3 Colors", "Size": "Size: L", "Gender": "Gender: Unisex", "timestamp": "t"},
    ]


@pytest.fixture
def clean_df():
    # Hanya 2 baris yang valid dari raw_data di atas (T-shirt 2, Hoodie 3)
    return pd.DataFrame(
        [
            {"Title": "T-shirt 2", "Price": 1634400.0, "Rating": 3.9, "Colors": 3,
             "Size": "M", "Gender": "Women", "timestamp": "t"},
            {"Title": "Hoodie 3", "Price": 7950080.0, "Rating": 4.8, "Colors": 3,
             "Size": "L", "Gender": "Unisex", "timestamp": "t"},
        ]
    )


def test_generate_quality_report_counts_correctly(raw_data, clean_df):
    report = generate_quality_report(raw_data, clean_df, run_timestamp="2026-06-22T00:00:00")

    assert report["total_raw_rows"] == 4
    assert report["total_clean_rows"] == 2
    assert report["total_dropped_rows"] == 2
    assert report["pct_dropped"] == 50.0
    assert report["invalid_breakdown"]["invalid_title_rows"] == 1
    assert report["invalid_breakdown"]["invalid_price_rows"] == 1
    assert report["invalid_breakdown"]["invalid_rating_rows"] == 2


def test_generate_quality_report_handles_empty_raw_data():
    report = generate_quality_report([], pd.DataFrame())
    assert report["total_raw_rows"] == 0
    assert report["total_clean_rows"] == 0
    assert report["pct_dropped"] == 0.0


def test_generate_quality_report_handles_none_clean_df(raw_data):
    report = generate_quality_report(raw_data, None)
    assert report["total_clean_rows"] == 0
    assert report["total_dropped_rows"] == report["total_raw_rows"]


def test_generate_quality_report_handles_malformed_input():
    # raw_data tanpa kolom yang diharapkan -> tidak boleh meledak/raise
    report = generate_quality_report([{"unexpected_column": 1}], pd.DataFrame())
    assert "generated_at" in report
    assert report["total_raw_rows"] == 1


def test_save_quality_report_writes_json_file(tmp_path, raw_data, clean_df):
    report = generate_quality_report(raw_data, clean_df, run_timestamp="20260622T000000")
    file_path = save_quality_report(report, str(tmp_path), run_timestamp="20260622T000000")

    assert file_path is not None
    assert os.path.exists(file_path)
    assert file_path.endswith("quality_report_20260622T000000.json")


def test_save_quality_report_handles_invalid_directory():
    # Path yang tidak mungkin dibuat (mengandung null byte) -> harus gagal dengan baik
    result = save_quality_report({"a": 1}, "/proc/cannot_create_here\0invalid")
    assert result is None

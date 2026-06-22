"""
test_transform.py
------------------
Unit test untuk modul utils/transform.py.
"""

import sys
import os

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.transform import (
    clean_title,
    clean_price,
    clean_rating,
    clean_colors,
    clean_size,
    clean_gender,
    remove_duplicates_and_na,
    enforce_data_types,
    transform_main,
)


def _raw_dataframe():
    return pd.DataFrame(
        [
            {
                "Title": "Unknown Product",
                "Price": "$100.00",
                "Rating": "Rating: \u2b50 Invalid Rating / 5",
                "Colors": "5 Colors",
                "Size": "Size: M",
                "Gender": "Gender: Men",
                "timestamp": "2026-06-17T00:00:00",
            },
            {
                "Title": "T-shirt 2",
                "Price": "$102.15",
                "Rating": "Rating: \u2b50 3.9 / 5",
                "Colors": "3 Colors",
                "Size": "Size: M",
                "Gender": "Gender: Women",
                "timestamp": "2026-06-17T00:00:00",
            },
            {
                "Title": "Pants 16",
                "Price": "Price Unavailable",
                "Rating": "Rating: Not Rated",
                "Colors": "8 Colors",
                "Size": "Size: S",
                "Gender": "Gender: Men",
                "timestamp": "2026-06-17T00:00:00",
            },
            {
                "Title": "T-shirt 2",
                "Price": "$102.15",
                "Rating": "Rating: \u2b50 3.9 / 5",
                "Colors": "3 Colors",
                "Size": "Size: M",
                "Gender": "Gender: Women",
                "timestamp": "2026-06-17T00:00:00",
            },
            {
                "Title": "Hoodie 3",
                "Price": "$496.88",
                "Rating": "Rating: \u2b50 4.8 / 5",
                "Colors": "3 Colors",
                "Size": "Size: L",
                "Gender": "Gender: Unisex",
                "timestamp": "2026-06-17T00:00:00",
            },
        ]
    )


# ---------------------------------------------------------------------
# clean_title
# ---------------------------------------------------------------------

def test_clean_title_removes_unknown_product():
    df = _raw_dataframe()
    result = clean_title(df)
    assert "Unknown Product" not in result["Title"].values
    assert len(result) == 4


def test_clean_title_handles_missing_column_gracefully():
    df = pd.DataFrame([{"NotTitle": "x"}])
    result = clean_title(df)
    # Tidak boleh crash; mengembalikan df apa adanya saat terjadi error.
    assert "NotTitle" in result.columns


# ---------------------------------------------------------------------
# clean_price
# ---------------------------------------------------------------------

def test_clean_price_converts_to_idr():
    df = _raw_dataframe()
    df = clean_title(df)
    result = clean_price(df)
    tshirt_row = result[result["Title"] == "T-shirt 2"].iloc[0]
    assert tshirt_row["Price"] == pytest.approx(102.15 * 16000)


def test_clean_price_removes_unavailable():
    df = _raw_dataframe()
    result = clean_price(df)
    assert "Price Unavailable" not in result["Price"].astype(str).values
    assert len(result) == 4  # baris "Pants 16" terhapus


def test_clean_price_handles_missing_column_gracefully():
    df = pd.DataFrame([{"NotPrice": "x"}])
    result = clean_price(df)
    assert "NotPrice" in result.columns


# ---------------------------------------------------------------------
# clean_rating
# ---------------------------------------------------------------------

def test_clean_rating_extracts_float_value():
    df = _raw_dataframe()
    result = clean_rating(df)
    hoodie_row = result[result["Title"] == "Hoodie 3"].iloc[0]
    assert hoodie_row["Rating"] == 4.8
    assert isinstance(hoodie_row["Rating"], float)


def test_clean_rating_removes_invalid_and_not_rated():
    df = _raw_dataframe()
    result = clean_rating(df)
    assert "Unknown Product" not in result["Title"].values
    assert "Pants 16" not in result["Title"].values


# ---------------------------------------------------------------------
# clean_colors
# ---------------------------------------------------------------------

def test_clean_colors_extracts_integer():
    df = _raw_dataframe()
    result = clean_colors(df)
    tshirt_row = result[result["Title"] == "T-shirt 2"].iloc[0]
    assert tshirt_row["Colors"] == 3
    assert isinstance(int(tshirt_row["Colors"]), int)


# ---------------------------------------------------------------------
# clean_size / clean_gender
# ---------------------------------------------------------------------

def test_clean_size_strips_prefix():
    df = _raw_dataframe()
    result = clean_size(df)
    assert (result["Size"] == "Size:").sum() == 0
    assert "M" in result["Size"].values


def test_clean_gender_strips_prefix():
    df = _raw_dataframe()
    result = clean_gender(df)
    assert "Women" in result["Gender"].values
    assert all(not g.startswith("Gender:") for g in result["Gender"])


# ---------------------------------------------------------------------
# remove_duplicates_and_na
# ---------------------------------------------------------------------

def test_remove_duplicates_and_na_drops_duplicate_rows():
    df = _raw_dataframe()
    result = remove_duplicates_and_na(df)
    tshirt_rows = result[result["Title"] == "T-shirt 2"]
    assert len(tshirt_rows) == 1


def test_remove_duplicates_and_na_drops_null_rows():
    df = _raw_dataframe()
    df.loc[0, "Price"] = None
    result = remove_duplicates_and_na(df)
    assert result["Price"].isna().sum() == 0


# ---------------------------------------------------------------------
# enforce_data_types
# ---------------------------------------------------------------------

def test_enforce_data_types_sets_correct_dtypes():
    df = pd.DataFrame(
        [
            {
                "Title": "T-shirt 2",
                "Price": 1634400.0,
                "Rating": 3.9,
                "Colors": 3,
                "Size": "M",
                "Gender": "Women",
                "timestamp": "2026-06-17T00:00:00",
            }
        ]
    )
    result = enforce_data_types(df)
    assert result["Price"].dtype == float
    assert result["Rating"].dtype == float
    assert pd.api.types.is_integer_dtype(result["Colors"])
    assert result["Size"].dtype == object


# ---------------------------------------------------------------------
# transform_main (end-to-end)
# ---------------------------------------------------------------------

def test_transform_main_end_to_end_cleans_all_issues():
    raw = _raw_dataframe().to_dict("records")
    result = transform_main(raw)

    assert "Unknown Product" not in result["Title"].values
    assert "Pants 16" not in result["Title"].values
    assert len(result) == 2  # T-shirt 2 (deduped) + Hoodie 3
    assert result["Price"].dtype == float
    assert result["Rating"].dtype == float
    assert pd.api.types.is_integer_dtype(result["Colors"])
    assert result.duplicated().sum() == 0
    assert result.isna().sum().sum() == 0


def test_transform_main_handles_empty_input():
    result = transform_main([])
    assert result.empty


def test_transform_main_handles_none_input():
    result = transform_main(None)
    assert result.empty


def test_transform_main_handles_missing_required_columns():
    result = transform_main([{"Title": "Only Title"}])
    assert result.empty

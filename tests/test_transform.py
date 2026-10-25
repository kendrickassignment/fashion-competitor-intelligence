import numpy as np
import pandas as pd
import pytest

from src.errors import QualityError
from src.transform import COLUMNS, transform_main, validate_clean_data


def test_expected_values_and_dtypes(raw_row):
    raw = pd.DataFrame([raw_row])
    before = raw.copy(deep=True)
    result = transform_main(raw)
    row = result.clean.iloc[0]
    assert row.to_dict() == {"Title": "T-shirt 2", "Price": 1634400.0, "Rating": 3.9,
                             "Colors": 3, "Size": "M", "Gender": "Women",
                             "timestamp": "2026-10-26T02:00:00.000000Z"}
    assert list(result.clean.columns) == COLUMNS
    assert result.clean.dtypes.astype(str).tolist() == ["object", "float64", "float64", "int64",
                                                       "object", "object", "object"]
    pd.testing.assert_frame_equal(raw, before)


@pytest.mark.parametrize("column,value,reason", [
    ("Title", "Unknown Product", "invalid_title"), ("Title", None, "invalid_title"),
    ("Title", "  ", "invalid_title"), ("Price", "Price Unavailable", "invalid_price"),
    ("Price", "$0.00", "invalid_price"), ("Price", "$-2", "invalid_price"),
    ("Price", "$1.001", "invalid_price"), ("Price", "$inf", "invalid_price"),
    ("Rating", "Rating: Not Rated", "invalid_rating"),
    ("Rating", "Rating: ⭐ Invalid Rating / 5", "invalid_rating"),
    ("Rating", "Rating: 5.1 / 5", "invalid_rating"),
    ("Colors", "0 Colors", "invalid_colors"), ("Colors", "3.5 Colors", "invalid_colors"),
    ("Colors", "101 Colors", "invalid_colors"), ("Size", "Size: gigantic", "invalid_size"),
    ("Gender", "Gender: Unknown", "invalid_gender"), ("timestamp", "yesterday", "invalid_timestamp"),
])
def test_quarantine_reason_and_accounting(raw_row, column, value, reason):
    bad = {**raw_row, "Title": "Hoodie 3", column: value}
    result = transform_main(pd.DataFrame([raw_row, bad]))
    assert len(result.clean) == 1
    assert result.rejected.iloc[0].rejection_reason == reason
    assert result.rejected.iloc[0][column] == value or pd.isna(value)
    assert result.metrics["raw_rows"] == result.metrics["clean_rows"] + result.metrics["rejected_rows"]
    assert sum(result.metrics["rejection_reasons"].values()) == 1


def test_deduplicate_ignores_timestamp_and_first_error_wins(raw_row):
    duplicate = {**raw_row, "timestamp": "2026-10-27T02:00:00Z"}
    bad = {**raw_row, "Title": "Unknown Product", "Price": "Price Unavailable"}
    result = transform_main(pd.DataFrame([raw_row, duplicate, bad]))
    assert len(result.clean) == 1
    assert result.metrics["rejection_reasons"] == {"duplicate_product": 1, "invalid_title": 1}


@pytest.mark.parametrize("value", [None, pd.DataFrame(), pd.DataFrame({"Title": ["a"]})])
def test_invalid_transform_input(value):
    with pytest.raises(QualityError):
        transform_main(value)


def test_all_invalid_fails_instead_of_publishing_empty(raw_row):
    with pytest.raises(QualityError):
        transform_main(pd.DataFrame([{**raw_row, "Title": "Unknown Product"}]))


@pytest.mark.parametrize("column,value", [
    ("Title", "Unknown Product"), ("Title", 42), ("Title", ""), ("Price", -1.0),
    ("Price", float("inf")), ("Rating", 9.0), ("Colors", 0), ("Size", "Size: M"),
    ("Gender", "Gender: Women"), ("timestamp", "not-a-date"),
    ("timestamp", "2026-99-26T02:00:00.000000Z"),
])
def test_contract_rejects_invalid_clean_value(clean, column, value):
    clean.loc[0, column] = value
    with pytest.raises(QualityError):
        validate_clean_data(clean)


def test_contract_null_duplicate_dtype_and_columns(clean):
    with pytest.raises(QualityError):
        validate_clean_data(clean.assign(Price=np.nan))
    with pytest.raises(QualityError):
        validate_clean_data(pd.concat([clean, clean]))
    with pytest.raises(QualityError):
        validate_clean_data(clean.astype({"Price": object}))
    with pytest.raises(QualityError):
        validate_clean_data(clean.drop(columns="timestamp"))


def test_zero_rating_is_valid_and_conversion_happens_once(raw_row):
    result = transform_main(pd.DataFrame([{**raw_row, "Price": "$0.01", "Rating": "Rating: 0 / 5"}]))
    assert result.clean.Price.iloc[0] == 160.0
    assert result.clean.Rating.iloc[0] == 0.0
    with pytest.raises(QualityError):
        transform_main(result.clean)

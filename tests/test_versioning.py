"""
test_versioning.py
-------------------
Unit test untuk modul src/versioning.py (incremental load & data
versioning simulation).
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.versioning import (
    save_silver_snapshot,
    load_previous_snapshot,
    detect_changes,
    save_change_log,
)


@pytest.fixture
def previous_df():
    return pd.DataFrame(
        [
            {"Title": "T-shirt 2", "Price": 1634400.0, "Rating": 3.9, "Colors": 3,
             "Size": "M", "Gender": "Women", "timestamp": "t1"},
            {"Title": "Hoodie 3", "Price": 7950080.0, "Rating": 4.8, "Colors": 3,
             "Size": "L", "Gender": "Unisex", "timestamp": "t1"},
        ]
    )


@pytest.fixture
def current_df():
    return pd.DataFrame(
        [
            # Harga berubah dibanding previous_df
            {"Title": "T-shirt 2", "Price": 1700000.0, "Rating": 3.9, "Colors": 3,
             "Size": "M", "Gender": "Women", "timestamp": "t2"},
            # Tidak berubah
            {"Title": "Hoodie 3", "Price": 7950080.0, "Rating": 4.8, "Colors": 3,
             "Size": "L", "Gender": "Unisex", "timestamp": "t2"},
            # Produk baru
            {"Title": "Jacket 6", "Price": 2453920.0, "Rating": 3.3, "Colors": 3,
             "Size": "S", "Gender": "Unisex", "timestamp": "t2"},
        ]
    )


def test_save_silver_snapshot_creates_history_and_latest(tmp_path, current_df):
    history_path, latest_path = save_silver_snapshot(current_df, str(tmp_path), run_date="2026-06-22")

    assert history_path is not None
    assert latest_path is not None
    assert os.path.exists(history_path)
    assert os.path.exists(latest_path)
    assert "history" in history_path
    assert latest_path.endswith("latest.csv")

    saved = pd.read_csv(latest_path)
    assert len(saved) == 3


def test_load_previous_snapshot_returns_none_when_no_file(tmp_path):
    result = load_previous_snapshot(str(tmp_path / "does_not_exist.csv"))
    assert result is None


def test_load_previous_snapshot_reads_existing_file(tmp_path, previous_df):
    path = tmp_path / "latest.csv"
    previous_df.to_csv(path, index=False)

    result = load_previous_snapshot(str(path))
    assert result is not None
    assert len(result) == 2


def test_detect_changes_identifies_new_products(previous_df, current_df):
    changes = detect_changes(previous_df, current_df)
    new_titles = set(changes["new_products"]["Title"])
    assert new_titles == {"Jacket 6"}


def test_detect_changes_identifies_price_changes(previous_df, current_df):
    changes = detect_changes(previous_df, current_df)
    price_change_titles = set(changes["price_changes"]["Title"])
    assert price_change_titles == {"T-shirt 2"}

    row = changes["price_changes"].iloc[0]
    assert row["old_price"] == 1634400.0
    assert row["new_price"] == 1700000.0
    assert row["delta_price"] == pytest.approx(65600.0)


def test_detect_changes_first_run_treats_everything_as_new(current_df):
    changes = detect_changes(None, current_df)
    assert len(changes["new_products"]) == len(current_df)
    assert changes["price_changes"].empty


def test_detect_changes_handles_empty_current_df(previous_df):
    changes = detect_changes(previous_df, pd.DataFrame())
    assert changes["new_products"].empty
    assert changes["price_changes"].empty


def test_save_change_log_writes_both_files(tmp_path, previous_df, current_df):
    changes = detect_changes(previous_df, current_df)
    new_path, price_path = save_change_log(changes, str(tmp_path), run_date="2026-06-22")

    assert os.path.exists(new_path)
    assert os.path.exists(price_path)

    saved_new = pd.read_csv(new_path)
    saved_price = pd.read_csv(price_path)
    assert len(saved_new) == 1
    assert len(saved_price) == 1

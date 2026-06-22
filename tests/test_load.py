"""
test_load.py
------------
Unit test untuk modul utils/load.py.

Seluruh interaksi dengan PostgreSQL dan Google Sheets API di-mock
sehingga pengujian tidak memerlukan database maupun kredensial
sungguhan.
"""

import sys
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.load import (
    save_to_csv,
    get_postgresql_engine,
    save_to_postgresql,
    get_google_sheets_service,
    save_to_google_sheets,
    save_summary_to_google_sheets,
    load_main,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame(
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


# ---------------------------------------------------------------------
# save_to_csv
# ---------------------------------------------------------------------

def test_save_to_csv_success(sample_df, tmp_path):
    file_path = tmp_path / "products.csv"
    result = save_to_csv(sample_df, str(file_path))

    assert result is True
    assert file_path.exists()
    content = file_path.read_text()
    assert "T-shirt 2" in content


def test_save_to_csv_failure_returns_false(sample_df):
    # Path direktori yang tidak ada dan tidak dapat dibuat otomatis oleh pandas.
    result = save_to_csv(sample_df, "/path/does/not/exist/products.csv")
    assert result is False


# ---------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------

@patch("sqlalchemy.create_engine")
def test_get_postgresql_engine_success(mock_create_engine):
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    engine = get_postgresql_engine("postgresql+psycopg2://user:pass@localhost:5432/db")

    assert engine is mock_engine
    mock_create_engine.assert_called_once()


@patch("sqlalchemy.create_engine", side_effect=Exception("connection refused"))
def test_get_postgresql_engine_failure_returns_none(mock_create_engine):
    engine = get_postgresql_engine("postgresql+psycopg2://bad-url")
    assert engine is None


@patch("src.load.get_postgresql_engine")
def test_save_to_postgresql_success(mock_get_engine, sample_df):
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    with patch.object(pd.DataFrame, "to_sql") as mock_to_sql:
        result = save_to_postgresql(sample_df, "postgresql+psycopg2://user:pass@localhost/db")

    assert result is True
    mock_to_sql.assert_called_once()
    mock_engine.dispose.assert_called_once()


@patch("src.load.get_postgresql_engine")
def test_save_to_postgresql_handles_none_engine(mock_get_engine, sample_df):
    mock_get_engine.return_value = None

    result = save_to_postgresql(sample_df, "postgresql+psycopg2://user:pass@localhost/db")

    assert result is False


@patch("src.load.get_postgresql_engine")
def test_save_to_postgresql_handles_to_sql_exception(mock_get_engine, sample_df):
    mock_engine = MagicMock()
    mock_get_engine.return_value = mock_engine

    with patch.object(pd.DataFrame, "to_sql", side_effect=Exception("insert failed")):
        result = save_to_postgresql(sample_df, "postgresql+psycopg2://user:pass@localhost/db")

    assert result is False
    mock_engine.dispose.assert_called_once()


# ---------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------

@patch("googleapiclient.discovery.build")
@patch("google.oauth2.service_account.Credentials.from_service_account_file")
def test_get_google_sheets_service_success(mock_from_file, mock_build):
    mock_creds = MagicMock()
    mock_from_file.return_value = mock_creds
    mock_service = MagicMock()
    mock_build.return_value = mock_service

    service = get_google_sheets_service("fake-credentials.json")

    assert service is mock_service
    mock_from_file.assert_called_once()
    mock_build.assert_called_once_with("sheets", "v4", credentials=mock_creds)


@patch(
    "google.oauth2.service_account.Credentials.from_service_account_file",
    side_effect=FileNotFoundError("credentials file not found"),
)
def test_get_google_sheets_service_handles_missing_file(mock_from_file):
    service = get_google_sheets_service("does-not-exist.json")
    assert service is None


@patch("src.load.get_google_sheets_service")
def test_save_to_google_sheets_success(mock_get_service, sample_df):
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service

    result = save_to_google_sheets(sample_df, "fake-spreadsheet-id")

    assert result is True
    mock_service.spreadsheets.return_value.values.return_value.update.assert_called_once()


@patch("src.load.get_google_sheets_service")
def test_save_to_google_sheets_handles_none_service(mock_get_service, sample_df):
    mock_get_service.return_value = None

    result = save_to_google_sheets(sample_df, "fake-spreadsheet-id")

    assert result is False


@patch("src.load.get_google_sheets_service")
def test_save_to_google_sheets_handles_api_exception(mock_get_service, sample_df):
    mock_service = MagicMock()
    mock_service.spreadsheets.side_effect = Exception("API quota exceeded")
    mock_get_service.return_value = mock_service

    result = save_to_google_sheets(sample_df, "fake-spreadsheet-id")

    assert result is False


@patch("src.load.get_google_sheets_service")
def test_save_summary_to_google_sheets_success(mock_get_service):
    mock_service = MagicMock()
    mock_get_service.return_value = mock_service

    summary = {"total_products": 867, "average_price": 4804335.32}
    result = save_summary_to_google_sheets(summary, "fake-spreadsheet-id")

    assert result is True
    mock_service.spreadsheets.return_value.values.return_value.update.assert_called_once()


@patch("src.load.get_google_sheets_service")
def test_save_summary_to_google_sheets_handles_none_service(mock_get_service):
    mock_get_service.return_value = None

    result = save_summary_to_google_sheets({"total_products": 867}, "fake-spreadsheet-id")

    assert result is False


@patch("src.load.get_google_sheets_service")
def test_save_summary_to_google_sheets_handles_api_exception(mock_get_service):
    mock_service = MagicMock()
    mock_service.spreadsheets.side_effect = Exception("API quota exceeded")
    mock_get_service.return_value = mock_service

    result = save_summary_to_google_sheets({"total_products": 867}, "fake-spreadsheet-id")

    assert result is False


# ---------------------------------------------------------------------
# load_main
# ---------------------------------------------------------------------

@patch("src.load.save_to_google_sheets", return_value=True)
@patch("src.load.save_to_postgresql", return_value=True)
@patch("src.load.save_to_csv", return_value=True)
def test_load_main_saves_to_all_three_repositories(mock_csv, mock_pg, mock_gsheet, sample_df):
    results = load_main(
        sample_df,
        csv_path="products.csv",
        db_url="postgresql+psycopg2://user:pass@localhost/db",
        spreadsheet_id="fake-id",
    )

    assert results["csv"] is True
    assert results["postgresql"] is True
    assert results["google_sheets"] is True
    mock_csv.assert_called_once()
    mock_pg.assert_called_once()
    mock_gsheet.assert_called_once()


@patch("src.load.save_summary_to_google_sheets", return_value=True)
@patch("src.load.save_to_google_sheets", return_value=True)
@patch("src.load.save_to_postgresql", return_value=True)
@patch("src.load.save_to_csv", return_value=True)
def test_load_main_pushes_summary_to_google_sheets_when_provided(
    mock_csv, mock_pg, mock_gsheet, mock_gsheet_summary, sample_df
):
    results = load_main(
        sample_df,
        csv_path="products.csv",
        spreadsheet_id="fake-id",
        summary={"total_products": 867},
    )

    assert results["google_sheets_summary"] is True
    mock_gsheet_summary.assert_called_once()


@patch("src.load.save_to_csv", return_value=True)
def test_load_main_only_saves_csv_when_no_other_config_given(mock_csv, sample_df):
    results = load_main(sample_df, csv_path="products.csv")

    assert results["csv"] is True
    assert results["postgresql"] is None
    assert results["google_sheets"] is None


@patch("src.load.save_to_csv", side_effect=Exception("unexpected failure"))
def test_load_main_handles_unexpected_exception(mock_csv, sample_df):
    results = load_main(sample_df, csv_path="products.csv")
    assert isinstance(results, dict)

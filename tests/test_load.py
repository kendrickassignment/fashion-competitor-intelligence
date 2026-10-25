from unittest.mock import Mock

import pandas as pd
import pytest
from sqlalchemy import create_engine

from config import Settings
from src import io, load, load_csv, load_postgres, load_sheets
from src.errors import LoadError


def test_atomic_csv_roundtrip(clean, tmp_path):
    path = tmp_path / "nested" / "products.csv"
    assert load_csv.save_to_csv(clean, path)["rows"] == 1
    pd.testing.assert_frame_equal(pd.read_csv(path), clean)
    with pytest.raises(LoadError):
        load_csv.save_to_csv(clean, tmp_path / "wrong.json")
    with pytest.raises(LoadError):
        load_csv.save_to_csv(pd.DataFrame(), path)


def test_failed_replace_preserves_old_file_and_cleans_temp(tmp_path, monkeypatch):
    path = tmp_path / "products.csv"
    path.write_text("last good", encoding="utf-8")
    monkeypatch.setattr(io.os, "replace", Mock(side_effect=PermissionError))
    with pytest.raises(LoadError):
        io.atomic_write(path, "new")
    assert path.read_text() == "last good"
    assert list(tmp_path.iterdir()) == [path]
    with pytest.raises(LoadError):
        io.write_json(path, {"invalid": float("nan")})


def test_json_write(tmp_path):
    io.write_json(tmp_path / "report.json", {"rows": 1})
    assert '"rows": 1' in (tmp_path / "report.json").read_text()


def test_unwritable_parent_is_a_load_error(tmp_path):
    parent = tmp_path / "a-file"
    parent.write_text("occupied")
    with pytest.raises(LoadError):
        io.atomic_write(parent / "child.csv", "data")


def test_postgresql_transaction_and_readback(clean, monkeypatch):
    engine = Mock()
    engine.dialect.name = "postgresql"
    connection = engine.begin.return_value.__enter__.return_value if hasattr(
        engine.begin.return_value, "__enter__") else Mock()
    from unittest.mock import MagicMock
    engine.begin.return_value = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    connection.scalar.return_value = len(clean)
    monkeypatch.setattr(load_postgres, "create_engine", Mock(return_value=engine))
    monkeypatch.setattr(load_postgres.MetaData, "create_all", Mock())
    result = load_postgres.save_to_postgresql(clean, "postgresql://unused")
    assert result["rows"] == 1
    assert connection.execute.call_count == 6
    engine.dispose.assert_called_once()
    connection.scalar.return_value = 0
    with pytest.raises(LoadError):
        load_postgres.save_to_postgresql(clean, engine=engine)


def test_postgres_rejects_other_repository_and_connect_failure(clean, monkeypatch):
    engine = create_engine("sqlite://")
    with pytest.raises(LoadError):
        load_postgres.save_to_postgresql(clean, engine=engine)
    monkeypatch.setattr(load_postgres, "create_engine", Mock(side_effect=OSError("secret")))
    with pytest.raises(LoadError, match="PostgreSQL load failed"):
        load_postgres.save_to_postgresql(clean, "postgresql://unused")
    monkeypatch.setattr(load_postgres, "MetaData", Mock(side_effect=ValueError))
    with pytest.raises(LoadError):
        load_postgres.product_tables()


def test_sheet_create_update_literal_types_and_no_clear(clean, sheet_service):
    result = load_sheets.save_to_google_sheets(clean, "id", service=sheet_service)
    assert result["verified"] == "all cells"
    body = sheet_service.spreadsheets().batchUpdate.call_args.kwargs["body"]
    assert "addSheet" in body["requests"][0]
    cells = body["requests"][1]["updateCells"]["rows"][1]["values"]
    assert cells[1]["userEnteredValue"] == {"numberValue": 1634400.0}
    assert cells[0]["userEnteredValue"] == {"stringValue": "T-shirt 2"}
    metadata = {"sheets": [{"properties": {"sheetId": 7, "title": "Products"}}]}
    requests, _ = load_sheets.build_sheet_requests(clean, metadata)
    assert requests[0]["updateSheetProperties"]["properties"]["gridProperties"]["rowCount"] == 2
    assert not any("clear" in str(request).lower() for request in requests)
    sheet_service.close.assert_not_called()


@pytest.mark.parametrize("failure", ["write", "readback", "missing_id", "credentials"])
def test_sheet_failure(clean, sheet_service, failure):
    api = sheet_service.spreadsheets()
    if failure == "write":
        api.batchUpdate.return_value.execute.side_effect = RuntimeError("503")
    elif failure == "readback":
        api.values.return_value.get.return_value.execute.return_value = {"values": []}
    with pytest.raises(LoadError):
        load_sheets.save_to_google_sheets(clean, "" if failure == "missing_id" else "id",
                                         credentials_file="absent.json",
                                         service=None if failure == "credentials" else sheet_service)


def test_sheet_real_client_lifecycle_is_mocked(clean, sheet_service, monkeypatch):
    monkeypatch.setattr(load_sheets.service_account.Credentials, "from_service_account_file", Mock())
    monkeypatch.setattr(load_sheets, "build", Mock(return_value=sheet_service))
    load_sheets.save_to_google_sheets(clean, "id", "local-key.json")
    sheet_service.close.assert_called_once()
    with pytest.raises(LoadError):
        load_sheets.build_sheet_requests(clean, {}, tab_name="")


def test_dispatch_attempts_all_targets_and_redacts_error(clean, monkeypatch, tmp_path):
    monkeypatch.setattr(load, "save_to_postgresql", Mock(side_effect=RuntimeError("password=secret")))
    monkeypatch.setattr(load, "save_to_google_sheets", Mock(return_value={"status": "success"}))
    settings = Settings(targets=("csv", "postgresql", "google_sheets"))
    result = load.load_main(clean, settings, tmp_path / "out.csv")
    assert result["postgresql"] == {"status": "failed", "error_type": "RuntimeError"}
    assert result["google_sheets"]["status"] == "success"
    assert "secret" not in str(result)
    with pytest.raises(LoadError):
        load.load_main(clean, None, tmp_path / "out.csv")

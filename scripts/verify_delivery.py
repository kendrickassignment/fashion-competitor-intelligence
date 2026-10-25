"""Independently verify a completed run against CSV, PostgreSQL, and Google Sheets."""

import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import httplib2
import pandas as pd
from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.transform import validate_clean_data  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = json.loads((args.run / "run.json").read_text(encoding="utf-8"))
    assert report["status"] == "success" and report["mode"] == "live"
    frame = pd.read_csv(args.run / "clean.csv")
    raw = pd.read_csv(args.run / "raw.csv")
    validate_clean_data(frame)
    valid_raw = raw.loc[raw.Title.isin(frame.Title), ["Title", "Price"]]
    joined = frame.merge(valid_raw, on="Title", suffixes=("_idr", "_usd"), validate="one_to_one")
    converted = joined.Price_usd.str.removeprefix("$").astype(float).mul(16000).round(2)
    assert converted.eq(joined.Price_idr).all()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            version = connection.scalar(text("SHOW server_version"))
            database = pd.read_sql_query(text('SELECT * FROM fashion_products ORDER BY "Title"'), connection)
            history = connection.scalar(text("SELECT count(*) FROM fashion_observations"))
        database["timestamp"] = pd.to_datetime(database["timestamp"], utc=True).dt.strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ")
        expected = frame.sort_values("Title").reset_index(drop=True)
        pd.testing.assert_frame_equal(database[frame.columns], expected)
    finally:
        engine.dispose()
    credentials = service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.metadata.readonly"])
    auth_http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=30))
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    with build("sheets", "v4", http=auth_http, cache_discovery=False) as service:
        actual = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,
            range=f"'Products'!A1:G{len(frame)+1}", valueRenderOption="UNFORMATTED_VALUE").execute()["values"]
        assert actual == [list(frame.columns)] + frame.values.tolist()
    # Use a separate HTTP object because closing the Sheets client closes its transport.
    with build("drive", "v3", http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=30)),
               cache_discovery=False) as drive:
        permissions = drive.permissions().list(fileId=spreadsheet_id, fields="permissions(type,role)").execute()
        assert any(p["type"] == "anyone" and p["role"] == "writer" for p in permissions["permissions"])
    evidence = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(), "run_id": report["run_id"],
        "python": platform.python_version(), "raw_rows": len(raw), "clean_rows": len(frame),
        "source_pages": int(raw.source_page.nunique()), "all_pages_have_20_rows": bool(raw.groupby("source_page").size().eq(20).all()),
        "null_cells": int(frame.isna().sum().sum()), "duplicate_titles": int(frame.Title.duplicated().sum()),
        "currency_conversion": "all clean prices equal raw USD price * 16000",
        "pandas_dtypes": frame.dtypes.astype(str).to_dict(),
        "clean_csv_sha256": hashlib.sha256((args.run / "clean.csv").read_bytes()).hexdigest(),
        "postgresql": {"server_version": version, "current_rows": len(database), "history_rows": history,
                       "verification": "all columns and rows match clean CSV", "deployment": "isolated local server"},
        "google_sheets": {"spreadsheet_id": spreadsheet_id, "rows": len(actual)-1,
                          "verification": "all cells match clean CSV", "public_access": "anyone / writer"},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Verified all destinations: {len(frame)} clean rows; no nulls or duplicates.")


if __name__ == "__main__":
    main()

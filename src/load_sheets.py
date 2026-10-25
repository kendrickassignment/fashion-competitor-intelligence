"""Atomic Google Sheets snapshot refresh with literal cells and full read-back."""

import numbers

import httplib2
from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build

from src.errors import LoadError
from src.transform import validate_clean_data


def build_sheet_requests(frame, metadata, tab_name="Products"):
    """One batch resizes, writes, and formats; no destructive clear before a write."""
    try:
        validate_clean_data(frame)
        if not tab_name or len(tab_name) > 100:
            raise ValueError("Invalid tab name")
        properties = [sheet["properties"] for sheet in metadata.get("sheets", [])]
        found = next((item for item in properties if item["title"] == tab_name), None)
        sheet_id = found["sheetId"] if found else max([p["sheetId"] for p in properties] + [0]) + 1
        grid = {"rowCount": len(frame) + 1, "columnCount": len(frame.columns), "frozenRowCount": 1}
        requests = []
        if found is None:
            requests.append({"addSheet": {"properties": {
                "sheetId": sheet_id, "title": tab_name, "gridProperties": grid}}})
        else:
            requests.append({"updateSheetProperties": {"properties": {
                "sheetId": sheet_id, "gridProperties": grid}, "fields": "gridProperties"}})
        values = [frame.columns.tolist()] + frame.values.tolist()
        rows = [{"values": [{"userEnteredValue": {
            "numberValue" if isinstance(value, numbers.Real) else "stringValue": value}}
            for value in row]} for row in values]
        requests.extend([
            {"updateCells": {"start": {"sheetId": sheet_id, "rowIndex": 0, "columnIndex": 0},
                             "rows": rows, "fields": "userEnteredValue"}},
            {"repeatCell": {"range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {
                                "backgroundColor": {"red": 0.06, "green": 0.16, "blue": 0.21},
                                "textFormat": {"bold": True, "foregroundColor": {
                                    "red": 1, "green": 1, "blue": 1}}}},
                            "fields": "userEnteredFormat"}},
            {"autoResizeDimensions": {"dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS",
                                                       "startIndex": 0, "endIndex": 7}}},
        ])
        return requests, values
    except Exception as exc:
        raise LoadError("Cannot construct Sheets snapshot request") from exc


def save_to_google_sheets(frame, spreadsheet_id, credentials_file=None, service=None, tab_name="Products"):
    """Use injected services for tests; real service-account credentials for live runs."""
    owned = service is None
    try:
        validate_clean_data(frame)
        if not spreadsheet_id:
            raise ValueError("Missing spreadsheet ID")
        if owned:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            service = build("sheets", "v4", http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=30)),
                            cache_discovery=False)
        api = service.spreadsheets()
        metadata = api.get(spreadsheetId=spreadsheet_id, fields="sheets.properties").execute()
        requests, expected = build_sheet_requests(frame, metadata, tab_name)
        api.batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()
        escaped_tab = tab_name.replace("'", "''")
        actual = api.values().get(spreadsheetId=spreadsheet_id,
                                  range=f"'{escaped_tab}'!A1:G{len(frame) + 1}",
                                  valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
        if actual != expected:
            raise ValueError("Read-back values differ")
        return {"status": "success", "rows": len(frame), "spreadsheet_id": spreadsheet_id,
                "tab": tab_name, "verified": "all cells"}
    except Exception as exc:
        raise LoadError("Google Sheets load or read-back verification failed") from exc
    finally:
        if owned and service is not None:
            service.close()

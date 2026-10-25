"""Independent sink outcomes; configured failures are never skipped successes."""

from src.errors import LoadError
from src.load_csv import save_to_csv
from src.load_postgres import save_to_postgresql
from src.load_sheets import save_to_google_sheets


def load_main(frame, settings, csv_path):
    try:
        results = {}
        loaders = {
            "csv": lambda: save_to_csv(frame, csv_path),
            "postgresql": lambda: save_to_postgresql(frame, settings.database_url),
            "google_sheets": lambda: save_to_google_sheets(
                frame, settings.spreadsheet_id, settings.credentials_file),
        }
        for target in settings.targets:
            try:
                results[target] = loaders[target]()
            except Exception as exc:
                results[target] = {"status": "failed", "error_type": type(exc).__name__}
        return results
    except Exception as exc:
        raise LoadError("Cannot dispatch data loads") from exc

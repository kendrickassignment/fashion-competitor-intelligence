"""Validated atomic CSV sink."""

from pathlib import Path

from src.errors import LoadError
from src.io import atomic_write
from src.transform import validate_clean_data


def save_to_csv(frame, path):
    try:
        validate_clean_data(frame)
        if Path(path).suffix.lower() != ".csv":
            raise ValueError("CSV destination requires .csv extension")
        atomic_write(path, frame.to_csv(index=False, lineterminator="\n"))
        return {"status": "success", "rows": len(frame), "file": Path(path).name}
    except Exception as exc:
        raise LoadError("CSV load failed") from exc

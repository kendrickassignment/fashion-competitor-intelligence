"""Crash-resistant writes; JSON is operational metadata, product data stays CSV."""

import json
import os
import tempfile
from pathlib import Path

from src.errors import LoadError


def atomic_write(path, content):
    temp = None
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                         dir=path.parent, delete=False) as handle:
            temp = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except Exception as exc:
        raise LoadError("Local artifact could not be committed") from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def write_json(path, payload):
    try:
        atomic_write(path, json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    except Exception as exc:
        raise LoadError("Audit report could not be written") from exc

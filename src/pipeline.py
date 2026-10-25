"""Audited orchestration with a local writer lock and explicit publication boundary."""

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from src.analytics import category_metrics, detect_changes
from src.errors import PipelineError, QualityError
from src.extract import scrape_main
from src.io import atomic_write, write_json
from src.load import load_main
from src.transform import transform_main, validate_clean_data

logger = logging.getLogger(__name__)


def run_pipeline(settings):
    settings.validate()
    root = Path(settings.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".pipeline.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise PipelineError("Another run holds .pipeline.lock; see runbook before removing it") from exc
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8]
    run_dir = root / "data" / "runs" / run_id
    report = {"run_id": run_id, "started_at": datetime.now(timezone.utc).isoformat(),
              "status": "running", "mode": "replay" if settings.replay else "live",
              "requested_pages": settings.pages, "requested_targets": list(settings.targets),
              "destinations": {name: {"status": "not_attempted"} for name in settings.targets}}
    started = time.monotonic()
    stage = "extract"
    try:
        with handle:
            handle.write(run_id)
        run_dir.mkdir(parents=True, exist_ok=False)
        raw = pd.read_csv(settings.replay, keep_default_na=False) if settings.replay else scrape_main(
            total_pages=settings.pages, delay=settings.delay)
        if len(raw) != settings.pages * 20:
            raise QualityError("Raw row count does not match requested page count")
        if "source_page" not in raw or set(raw["source_page"]) != set(range(1, settings.pages + 1)):
            raise QualityError("Missing source-page lineage")
        if not raw.groupby("source_page").size().eq(20).all():
            raise QualityError("Each source page must contain 20 rows")
        atomic_write(run_dir / "raw.csv", raw.to_csv(index=False, lineterminator="\n"))
        report["raw_sha256"] = hashlib.sha256((run_dir / "raw.csv").read_bytes()).hexdigest()
        stage = "transform"
        result = transform_main(raw)
        atomic_write(run_dir / "quarantine.csv", result.rejected.to_csv(index=False, lineterminator="\n"))
        write_json(run_dir / "quality.json", result.metrics)
        report["quality"] = result.metrics
        if result.metrics["yield_ratio"] < settings.min_yield:
            raise QualityError("Clean yield below configured quality gate")
        previous_path = root / "data" / "latest.csv"
        previous = pd.read_csv(previous_path) if previous_path.exists() else None
        if previous is not None:
            previous = previous.astype({"Title": object, "Size": object, "Gender": object, "timestamp": object,
                                        "Price": "float64", "Rating": "float64", "Colors": "int64"})
            validate_clean_data(previous)
        atomic_write(run_dir / "category_metrics.csv", category_metrics(result.clean).to_csv(index=False))
        atomic_write(run_dir / "changes.csv", detect_changes(previous, result.clean).to_csv(index=False))
        stage = "load"
        report["destinations"] = load_main(result.clean, settings, run_dir / "clean.csv")
        if any(value["status"] != "success" for value in report["destinations"].values()):
            raise PipelineError("One or more requested destinations failed; inspect run.json")
        stage = "publish"
        content = (run_dir / "clean.csv").read_text(encoding="utf-8")
        atomic_write(root / "products.csv", content)
        atomic_write(previous_path, content)
        report["clean_sha256"] = hashlib.sha256((root / "products.csv").read_bytes()).hexdigest()
        report["status"] = "success"
        logger.info("run=%s success raw=%s clean=%s", run_id, len(raw), len(result.clean))
        return report
    except Exception as exc:
        report.update(status="failed", failed_stage=stage, error_type=type(exc).__name__)
        raise PipelineError(f"Run failed at {stage}; audit: data/runs/{run_id}/run.json") from exc
    finally:
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        try:
            write_json(run_dir / "run.json", report)
        finally:
            lock.unlink(missing_ok=True)

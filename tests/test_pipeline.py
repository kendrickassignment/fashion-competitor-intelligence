import argparse
import json
from dataclasses import replace
from unittest.mock import Mock

import pandas as pd
import pytest

import main
from config import Settings, from_args
from src import pipeline
from src.analytics import category_metrics, detect_changes
from src.errors import PipelineError, QualityError


def test_analytics_price_movements_and_observation_gaps(clean):
    assert category_metrics(clean).iloc[0].median_price_idr == 1634400.0
    assert detect_changes(None, clean).iloc[0].change_type == "first_observed"
    assert detect_changes(clean, clean).empty
    previous = pd.concat([clean, clean.assign(Title="Pants 3")], ignore_index=True)
    current = pd.concat([clean.assign(Price=1500000.0), clean.assign(Title="Hoodie 4")], ignore_index=True)
    changes = detect_changes(previous, current).set_index("Title")
    assert changes.loc["T-shirt 2", "price_delta_idr"] == -134400.0
    assert changes.loc["Pants 3", "change_type"] == "not_observed_clean"
    assert changes.loc["Hoodie 4", "change_type"] == "first_observed"
    with pytest.raises(QualityError):
        category_metrics(pd.DataFrame())
    with pytest.raises(QualityError):
        detect_changes(pd.DataFrame(), clean)


def test_full_orchestration_replay_and_report(raw_page, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "scrape_main", Mock(return_value=raw_page))
    settings = Settings(output_dir=tmp_path, pages=1, delay=0)
    first = pipeline.run_pipeline(settings)
    assert first["status"] == "success" and first["mode"] == "live"
    assert first["destinations"]["csv"]["rows"] == 20
    run_dir = tmp_path / "data" / "runs" / first["run_id"]
    assert len(pd.read_csv(run_dir / "raw.csv")) == 20
    assert len(pd.read_csv(run_dir / "clean.csv")) == 20
    assert not (tmp_path / ".pipeline.lock").exists()
    second = pipeline.run_pipeline(replace(settings, replay=run_dir / "raw.csv"))
    assert second["mode"] == "replay" and first["clean_sha256"] == second["clean_sha256"]
    assert first["run_id"] != second["run_id"]
    assert pd.read_csv(tmp_path / "data" / "runs" / second["run_id"] / "changes.csv").empty
    assert json.loads((run_dir / "run.json").read_text())["status"] == "success"


@pytest.mark.parametrize("failure", ["extract", "row_count", "lineage", "page_count", "yield", "sink"])
def test_failure_preserves_last_published_snapshot(raw_page, tmp_path, monkeypatch, failure):
    settings = Settings(output_dir=tmp_path, pages=1)
    (tmp_path / "products.csv").write_text("last-good", encoding="utf-8")
    raw = raw_page.copy()
    if failure == "row_count":
        raw = raw.iloc[:19]
    elif failure == "lineage":
        raw["source_page"] = 2
    elif failure == "page_count":
        settings = replace(settings, pages=2)
        raw = pd.concat([raw, raw], ignore_index=True)
        raw.loc[raw.index[-1], "source_page"] = 2
    elif failure == "yield":
        raw.loc[:9, "Title"] = "Unknown Product"
    monkeypatch.setattr(pipeline, "scrape_main", Mock(return_value=raw))
    if failure == "extract":
        monkeypatch.setattr(pipeline, "scrape_main", Mock(side_effect=PipelineError("secret")))
    elif failure == "sink":
        monkeypatch.setattr(pipeline, "load_main", Mock(return_value={"csv": {"status": "failed"}}))
    with pytest.raises(PipelineError):
        pipeline.run_pipeline(settings)
    assert (tmp_path / "products.csv").read_text() == "last-good"
    report = json.loads(next((tmp_path / "data" / "runs").glob("*/run.json")).read_text())
    assert report["status"] == "failed" and "secret" not in str(report)
    assert not (tmp_path / ".pipeline.lock").exists()


def test_writer_lock_and_cli_failure(tmp_path, monkeypatch):
    (tmp_path / ".pipeline.lock").write_text("other-run")
    with pytest.raises(PipelineError, match="Another run"):
        pipeline.run_pipeline(Settings(output_dir=tmp_path))
    assert (tmp_path / ".pipeline.lock").read_text() == "other-run"
    monkeypatch.setattr(main, "run_pipeline", Mock(side_effect=PipelineError("safe error")))
    assert main.main(["--output-dir", str(tmp_path)]) == 1


def test_cli_success(monkeypatch):
    monkeypatch.setattr(main, "run_pipeline", Mock(return_value={"run_id": "test", "quality": {"clean_rows": 20}}))
    assert main.main([]) == 0


@pytest.mark.parametrize("changes", [
    {"pages": 0}, {"pages": 51}, {"delay": -1}, {"min_yield": 0}, {"min_yield": 1.1},
    {"targets": ()}, {"targets": ("sqlite",)}, {"targets": ("csv", "csv")},
    {"targets": ("csv", "postgresql")}, {"targets": ("csv", "google_sheets")},
])
def test_invalid_configuration(changes):
    with pytest.raises(PipelineError):
        replace(Settings(), **changes).validate()


def test_env_and_submission_validation(tmp_path, monkeypatch):
    key = tmp_path / "key.json"
    key.write_text("{}")
    monkeypatch.setenv("DATABASE_URL", "postgresql://placeholder")
    monkeypatch.setenv("SPREADSHEET_ID", "id")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(key))
    args = argparse.Namespace(output_dir=str(tmp_path), pages=50, delay=0, min_yield=0.8,
                              submission=True, targets="csv", replay=None)
    settings = from_args(args)
    assert settings.targets == ("csv", "postgresql", "google_sheets")
    args.pages = 1
    with pytest.raises(PipelineError, match="50 pages"):
        from_args(args)


def test_config_aliases(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SPREADSHEET_ID", raising=False)
    monkeypatch.setenv("PEMDA_DB_URL", "postgresql://alias")
    monkeypatch.setenv("PEMDA_SPREADSHEET_ID", "alias-id")
    args = argparse.Namespace(output_dir=".", pages=50, delay=0.25, min_yield=0.8,
                              submission=False, targets="csv", replay="raw.csv")
    settings = from_args(args)
    assert settings.database_url == "postgresql://alias" and settings.spreadsheet_id == "alias-id"
    assert settings.replay.name == "raw.csv"

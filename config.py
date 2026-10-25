"""Validated environment configuration. No credentials or URLs are logged."""

import os
from dataclasses import dataclass
from pathlib import Path

from src.errors import PipelineError


@dataclass(frozen=True)
class Settings:
    output_dir: Path = Path(".")
    pages: int = 50
    delay: float = 0.25
    min_yield: float = 0.80
    targets: tuple = ("csv",)
    database_url: str | None = None
    spreadsheet_id: str | None = None
    credentials_file: str | None = None
    replay: Path | None = None

    def validate(self):
        if type(self.pages) is not int or not 1 <= self.pages <= 50:
            raise PipelineError("pages must be in 1..50")
        if self.delay < 0 or not 0 < self.min_yield <= 1:
            raise PipelineError("Invalid delay or minimum yield")
        allowed = {"csv", "postgresql", "google_sheets"}
        if not self.targets or set(self.targets) - allowed or "csv" not in self.targets:
            raise PipelineError("Targets must include csv and only supported repositories")
        if len(set(self.targets)) != len(self.targets):
            raise PipelineError("Duplicate load targets")
        if "postgresql" in self.targets and not self.database_url:
            raise PipelineError("Set DATABASE_URL for PostgreSQL")
        if "google_sheets" in self.targets and (not self.spreadsheet_id or not self.credentials_file
                                               or not Path(self.credentials_file).is_file()):
            raise PipelineError("Set SPREADSHEET_ID and a valid GOOGLE_APPLICATION_CREDENTIALS file")


def from_args(args):
    settings = Settings(
        output_dir=Path(args.output_dir), pages=args.pages, delay=args.delay, min_yield=args.min_yield,
        targets=("csv", "postgresql", "google_sheets") if args.submission else tuple(args.targets.split(",")),
        database_url=os.getenv("DATABASE_URL") or os.getenv("PEMDA_DB_URL"),
        spreadsheet_id=os.getenv("SPREADSHEET_ID") or os.getenv("PEMDA_SPREADSHEET_ID"),
        credentials_file=os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        replay=Path(args.replay) if args.replay else None,
    )
    settings.validate()
    if args.submission and settings.pages != 50:
        raise PipelineError("Submission mode requires all 50 pages")
    return settings

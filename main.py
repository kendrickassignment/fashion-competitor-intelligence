"""CLI: python main.py [--submission] [--replay path/to/raw.csv]."""

import argparse
import logging

from config import from_args
from src.errors import PipelineError
from src.pipeline import run_pipeline


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fashion competitor intelligence ETL")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--targets", default="csv", help="csv,postgresql,google_sheets")
    parser.add_argument("--submission", action="store_true", help="Require all 50 pages and all three sinks")
    parser.add_argument("--pages", type=int, default=50, help="1..50; partial runs are development only")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--min-yield", type=float, default=0.80)
    parser.add_argument("--replay", help="Replay raw CSV without network extraction; keeps extraction timestamps")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        report = run_pipeline(from_args(args))
        print(f"SUCCESS run={report['run_id']} rows={report['quality']['clean_rows']}")
        return 0
    except (PipelineError, OSError) as exc:
        print(f"FAILED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

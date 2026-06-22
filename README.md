# 🛍️ Fashion Competitor Intelligence Pipeline

**A daily Bronze → Silver → Gold data pipeline that turns a competitor's product catalog into pricing and assortment intelligence.**

> Built as a self-contained simulation of a real competitor-monitoring system: same engineering patterns (layered storage, incremental detection, data quality gates, observability) you'd find on a retail analytics team — running against a live e-commerce catalog as the data source.

---

## 🚀 Project Overview

Retailers in fast-moving categories like fashion don't set prices in a vacuum — they react to what competitors are charging, how their assortment shifts, and where the market is heading. The teams that do this well don't refresh a competitor's website by hand; they run a pipeline.

This project simulates that pipeline end-to-end: it scrapes a full product catalog (1,000 SKUs across 50 pages), cleans and validates it against real-world messiness, tracks how the catalog changes from one run to the next, and serves the result as both a queryable dataset and a stakeholder-ready summary.

**What it answers, automatically, every run:**
- What's the current price landscape across the catalog?
- Which products are new since yesterday?
- Which products changed price — and by how much?
- How much of the raw data was even trustworthy?

## 🧠 Problem Statement

In a real pricing-intelligence team, the hard part is rarely "can we scrape the page." It's everything around it:

- **Trust** — source pages return malformed cards, missing prices, and placeholder ratings constantly. A pipeline that doesn't quarantine bad data silently corrupts every downstream price model.
- **Change, not snapshots** — a single CSV dump tells you today's prices. It can't tell you *what moved*. Competitor intelligence is fundamentally a diffing problem.
- **Multiple consumers** — a data analyst wants a database table; a category manager wants a spreadsheet they can open in five seconds. Serving both from one pipeline run is a design decision, not an afterthought.

This project is structured around solving those three problems specifically, not just "get the data into a CSV."

## 🏗️ Architecture

```
                                    ┌─────────────────────┐
   fashion-studio.dicoding.dev ───▶│      EXTRACT         │
   (50 pages, 1000 SKUs)           │  requests + BeautifulSoup
                                    └──────────┬───────────┘
                                               ▼
                                    ┌─────────────────────┐
                                    │   BRONZE  (raw)       │  data/bronze/raw_snapshot_<run>.csv
                                    │  immutable, append-only│  — never overwritten, full reprocessing
                                    └──────────┬───────────┘  source if cleaning logic ever needs a redo
                                               ▼
                                    ┌─────────────────────┐
                                    │     TRANSFORM         │  USD→IDR, dtype enforcement,
                                    │  + DATA QUALITY GATE  │  null/duplicate/invalid removal,
                                    └──────────┬───────────┘  % dropped + reason breakdown
                                               ▼
                                    ┌─────────────────────┐
                                    │   SILVER  (clean)      │  data/silver/history/products_<date>.csv
                                    │  versioned, typed      │  + data/silver/latest.csv (pointer)
                                    └──────┬────────┬───────┘
                                           ▼         ▼
                              ┌─────────────────┐ ┌─────────────────────┐
                              │   VERSIONING     │ │     ANALYTICS         │
                              │ new SKUs +        │ │ avg price, rating      │
                              │ price-change diff │ │ distribution, top SKUs │
                              └────────┬─────────┘ └──────────┬──────────┘
                                       ▼                      ▼
                              ┌──────────────────────────────────────┐
                              │              GOLD (serving)            │
                              │  change_log + analytics_summary (JSON) │
                              └──────────────────┬─────────────────────┘
                                                  ▼
                                    ┌──────────────────────────┐
                                    │           LOAD              │
                                    │  PostgreSQL (processed layer)│
                                    │  Google Sheets (serving layer)│
                                    └──────────────────────────┘
```

**Why three layers instead of one table?** Because each layer answers a different failure mode:
- **Bronze** exists so a transform bug never means re-scraping. Replay it from raw.
- **Silver** exists so every consumer works off one validated, typed, deduplicated source of truth — not five different "almost clean" CSVs.
- **Gold** exists because raw cleaned data and business insight are different products. A category manager should never have to `GROUP BY` anything themselves.

## ⚙️ Pipeline Features

| Practice | Where it lives |
|---|---|
| Modular ETL (single-responsibility files) | `src/extract.py`, `src/transform.py`, `src/load.py` |
| Error handling on every function, isolated failures | every module — one bad card/row never kills the run |
| Centralized logging (console + per-run log file) | `main.py::setup_logging()`, `logs/pipeline_<run>.log` |
| Run-level success/failure summary | printed at the end of every `main.py` run |
| Config separated from code | `config.py` (env-var overridable) |
| Multi-layer storage (file + warehouse + spreadsheet) | `data/`, PostgreSQL, Google Sheets |
| 77 unit tests, 88% coverage on `src/` | `tests/` |

## 📊 Data Quality Handling

Every run produces a `quality_report_<run>.json` in the Gold layer, generated by `src/quality.py`, before any cleaned data is trusted downstream. Example structure (illustrative — field names and shape, not a specific run's exact figures):

```json
{
  "total_raw_rows": 1000,
  "total_clean_rows": 867,
  "total_dropped_rows": 133,
  "pct_dropped": 13.3,
  "invalid_breakdown": {
    "invalid_title_rows": "<count>",
    "invalid_price_rows": "<count>",
    "invalid_rating_rows": "<count>"
  }
}
```
The top-level totals shown (1000 → 867, 13.3% dropped) match an actual full 50-page run against the live source — see Sample Insights below.

This isn't a vanity metric. A sudden jump in `pct_dropped` on a future run is the signal that the source site changed its HTML structure before a single bad row reaches the database.

## 🔄 Incremental & Historical Tracking

Because the source is a static catalog without a real change-data-capture feed, incremental load is simulated honestly rather than faked:

1. Every Silver run is saved **both** to a dated history file (`data/silver/history/products_<date>.csv`, never overwritten) **and** to `data/silver/latest.csv` (a pointer to the most recent state).
2. Before `latest.csv` is overwritten, the **previous** version is loaded and diffed against the new one in `src/versioning.py`, keyed on `Title` (the catalog's de facto stable identifier).
3. The diff produces two Gold artifacts every run: `new_products_<date>.csv` and `price_changes_<date>.csv` (with `old_price`, `new_price`, `delta_price`).

**Design caveat, stated plainly:** this source occasionally randomizes whether a row is valid (e.g. a real product temporarily shows "Price Unavailable"). When that product becomes valid again on a later run, it's correctly flagged as "new" relative to the last *clean* snapshot — which is the right behavior for a catalog without real product IDs, but worth knowing if you extend this to a source with a real primary key.

## 🛠️ Tech Stack

- **Extraction:** `requests`, `BeautifulSoup4`
- **Transformation/Analytics:** `pandas`
- **Storage:** CSV (Bronze/Silver), `PostgreSQL` via `SQLAlchemy` (processed layer), `Google Sheets API` (serving layer)
- **Testing:** `pytest`, `pytest-cov`, `pytest-mock`
- **Scheduling (simulated):** `cron` and an illustrative Apache Airflow DAG (`scheduling/`)

## ▶️ How to Run

```bash
pip install -r requirements.txt

# optional: configure PostgreSQL / Google Sheets
export PEMDA_DB_URL="postgresql+psycopg2://user:pass@host:5432/db"
export PEMDA_SPREADSHEET_ID="your-spreadsheet-id"
# and replace google-sheets-api.json with a real service account key

python main.py          # runs the full Bronze -> Silver -> Gold pipeline

pytest tests/ -v                              # 77 tests
pytest tests/ --cov=src --cov-report=term-missing   # coverage report
```

Each run writes a timestamped log to `logs/pipeline_<run_id>.log` and prints a step-by-step OK/FAILED summary to the console.

## 📈 Sample Insights

From a full production run against the live 50-page catalog (1,000 raw SKUs):

- **867 clean SKUs** survived validation (86.7% yield) — 133 dropped across invalid titles, missing prices, and unrated/invalid ratings.
- **0 nulls, 0 duplicates** in the final Silver dataset — `enforce_data_types` + `remove_duplicates_and_na` hold up against the real site, not just fixtures.
- Analytics summary (`src/analytics.py`) ships: average/median/min/max price, average price by Gender and by Size, rating distribution (incl. count of SKUs rated 4.5+), product count by category, and the top 5 rated SKUs — all auto-generated, zero manual `groupby`.

**Dashboard idea (not built, but the data is shaped for it):** a single-page Looker Studio / Streamlit dashboard reading directly from the Google Sheets serving layer — price distribution histogram, a "moved this week" table sourced straight from `price_changes_<date>.csv`, and a category mix donut chart from `product_count_by_category`.

## 💡 Future Improvements

- Replace `Title`-based versioning with a real composite key once/if the source exposes stable product IDs.
- Move Bronze/Silver storage from local CSV to object storage (S3/GCS) with partitioning by run date.
- Add a `dbt` layer on top of the PostgreSQL processed table for SQL-native transformations and tests.
- Wire the illustrative Airflow DAG (`scheduling/airflow_dag_example.py`) into a real Airflow instance with SLA alerting on `pct_dropped`.
- Add anomaly detection on `price_changes` (e.g. flag any `delta_price` beyond N standard deviations) instead of just logging every change equally.

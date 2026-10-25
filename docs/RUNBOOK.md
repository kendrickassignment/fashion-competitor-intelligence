# Operations runbook

## Profiles

`python main.py` scrapes all 50 pages and loads CSV. `--submission` requires CSV, PostgreSQL, and Google Sheets. For two destinations, pass `--targets csv,postgresql` or `--targets csv,google_sheets`. Set environment variables as shown in the README. Credential paths must exist; they are not embedded in source code.

`--pages N` supports local development only. A full submission requires 50 pages. Keep development and review output directories separate with `--output-dir` so a small test catalog does not replace the full catalog.

## Inspect a failure

1. Find the `run.json` path printed by the CLI.
2. Inspect `failed_stage`, destination statuses, and `quality.json` if available.
3. For extraction errors, verify source availability and the HTML contract. No partial raw snapshot is published by extraction.
4. For quality errors, inspect `quarantine.csv`, primary reasons, and source lineage. Do not lower thresholds merely to obtain a green result.
5. For PostgreSQL, check connectivity, privileges, schema compatibility, and locks. Both managed tables roll back together on transaction failure.
6. For Sheets, check API enablement, credential validity, spreadsheet access, and concurrent manual edits. A committed update followed by failed read-back still produces a failed run.
7. Retry from a saved raw CSV after fixing a load failure. If extraction itself failed before raw data could be saved, scrape again.

Driver errors are intentionally sanitized in operational reports. Diagnose connection problems with provider tools using the configured private credentials, not by printing secrets into pipeline logs.

## Replay and verification

```bash
python main.py --submission --replay data/runs/<failed-run>/raw.csv
```

A replay keeps extraction timestamps and does not duplicate PostgreSQL observations. Snapshot tables and the Sheets `Products` tab are refreshed with the replayed dataset. Replaying an older raw snapshot intentionally replaces the current snapshot with that older observation; inspect the selected file before running.

`products.csv` and `data/latest.csv` are promoted only after every requested sink succeeds. If a remote sink already committed before another failed, replay the same raw file to converge all destinations. Local file promotion is atomic per file, not across multiple files.

## Stale local lock

`.pipeline.lock` contains the run ID of the writer. First confirm no process is running against the same output directory. Inspect its run artifacts. Only then remove that exact lock file and retry. Never automatically delete a lock based solely on age. Separate hosts require an external coordination mechanism; the local lock cannot coordinate them.

## PostgreSQL reproduction

The Docker Compose database is persistent in a named volume and binds to loopback. It is separate from the disposable CI database. Start it with `docker compose up -d --wait`. Change the development password through `POSTGRES_PASSWORD` before using a different trust boundary.

For integration tests, create a separate database named `fashion_test` and set `TEST_DATABASE_URL` to it. The integration test creates and removes `fashion_products` and `fashion_observations`. Never point that variable to a database holding valuable tables with those names.

The evidence folder includes query results from a real local PostgreSQL server and a portable SQL dump. Recreate the dataset using the pipeline or restore that dump into an empty PostgreSQL database. Live runs were verified locally; this repository does not provision a publicly hosted database.

## Google Sheets review access

Normal operation needs the Sheets API and editor permission for the service account. For the assignment's public review requirement, enable the Drive API and run:

```bash
python scripts/prepare_review_access.py
```

This explicitly grants `anyone` the `writer` role on the configured spreadsheet and verifies the resulting permission. It is intended for the fictional review dataset. The general loader does not modify sharing permissions.

## Scheduling

The catalog workflow runs daily at 01:17 UTC (08:17 Asia/Jakarta) and can also be dispatched manually in GitHub Actions. It starts in CSV mode unless all three remote secrets are configured. It uploads operational artifacts even on failure. Hosted schedules can be delayed, and public-repository inactivity can disable schedules; inspect GitHub Actions when freshness matters.

The checked-out baseline, not the previous artifact, is used for local change detection in a fresh hosted runner. Persisting cross-run baselines and sending alerts are future deployment tasks. The code does not pretend that an uploaded Actions artifact is a durable warehouse.

## Private submission packaging

Run `scripts/build_submission.py` after committing the public project. Supply the service-account file through `--credentials` only when building the private reviewer archive. The archive includes `google-sheets-api.json`; it must not be uploaded to the public repository. `submission.txt` explains environment setup and links to the review spreadsheet. Replace an expired reviewer key with a current dedicated key before sharing the private package.

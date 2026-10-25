# Design decisions

## Fail closed on incomplete extraction

The source contract is 50 pages with 20 cards on each page. A successful run must observe that shape before transformation. Missing fields on an individual card are retained as null raw attributes and quarantined by transformation; missing cards or repeated page payloads fail extraction. The latter is a catalog-level failure, not permission to publish a smaller catalog.

The default scraper is sequential and waits 250 ms between pages. A single reused session provides connection pooling. HTTP 429 and transient 5xx responses are retried with exponential backoff; persistent failures stop the run. This favors predictable load and auditability over unnecessary concurrent scraping.

## Product identity

The educational source has numbered titles but no trustworthy exposed SKU key. This implementation treats the cleaned title as the product identity, including for deduplication and database keys. The first valid observation of a repeated title wins within a run. Conflicting variants with the same title are quarantined as duplicates. A real retailer should replace this rule with stable product/variant identifiers.

Timestamps describe extraction, so they must not defeat duplicate detection. A replay preserves timestamps. PostgreSQL history has the composite key `(Title, timestamp)`, making a replay idempotent at the observation level.

## Contracts and money

The expected pandas dtypes match the assignment, including float64 price and rating. The source prices have at most two decimal places, and the required conversion uses a fixed factor of 16,000. Values are rounded to two decimal places after conversion. This is a research dataset, not a financial ledger; an accounting system should use decimal money types and a documented rate source.

Timestamps are normalized to UTC ISO strings in CSV and Sheets, and stored as timezone-aware PostgreSQL timestamps. The source page and URL remain in the raw layer rather than changing the required clean schema.

## Rejection accounting

Rules run in the order title, price, rating, colors, size, gender, timestamp, then duplicate identity. Only the first failing reason is assigned to each rejected row. For the recorded catalog, 100 invalid-title rows and 33 invalid-price rows explain all 133 rejections. Some rows also have bad ratings; adding overlapping rule counts would overstate the number of rejected rows.

The minimum clean yield is 80% by default. That threshold is deliberately configurable and checked on every requested extract. It detects large changes but is not a statistically calibrated anomaly detector. There is no hardcoded expectation of 867 output rows.

## Commit and recovery boundaries

PostgreSQL uses one transaction for the current snapshot and observation history. A transaction-level advisory lock serializes cooperating pipeline writers. It does not coordinate unrelated applications. Schema creation requires privileges to create the two tables; managed production deployments should use migrations and a narrower runtime role.

Sheets uses a dedicated `Products` tab, with one batch that resizes and writes the complete grid. Existing unrelated tabs remain available. New values are typed literal cells; titles beginning with `=` cannot become formulas. Full read-back verifies data delivery, although a concurrent human editor can cause verification failure.

CSV writes use `fsync` and atomic replacement on the same filesystem. The exclusive local lock scopes to an output directory and survives a process crash, requiring operator inspection. The two local publication files and the remote repositories do not share one transaction. A partial remote delivery is visible in `run.json`; replay can converge the sinks.

## Observability and access

Each run has a UTC timestamp plus random suffix to avoid collisions. Raw and clean hashes connect evidence to the underlying files. A unique directory retains successful and failed attempts, and the CLI returns a failing exit code when any requested sink fails. Reports expose error classes, not driver exception strings or connection URLs.

Public spreadsheet editor access is an assignment review requirement for fictional data. The normal loader needs only the Sheets API scope; the separate access-preparation script temporarily uses a Drive scope. Credentials are supplied at runtime and excluded from Git. The private review archive is a separate artifact that explicitly includes the reviewer credential.

## Storage scope

Product records, quarantine rows, change events, and analytical aggregates are stored as CSV, PostgreSQL tables, or Sheets cells. JSON is limited to operational metadata and test evidence. No SQLite, Parquet, object-store dataset, or JSON product repository is used.

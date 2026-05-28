# Tradeoffs

Three things I deliberately did not build, and why.

---

## 1. Async task queue (Celery + Redis)

**What this would do**: Move CSV parsing and normalization out of the HTTP request cycle into background workers. The upload endpoint would return immediately with a job ID; the client would poll for status.

**Why I did not build it**: Celery requires Redis as a broker, a separate worker process, deployment configuration for both, job status tracking, and error handling for failed jobs. That's roughly a week of infrastructure work that does not change what the prototype demonstrates — the normalization logic, the data model, or the analyst review workflow. For files up to a few thousand rows, synchronous processing completes within Django's 30-second request timeout.

**What breaks without it**: Files with more than ~5,000 rows will time out. In production, any realistic full-year ingestion from an enterprise client would be larger than this. The fix is well-understood; it just requires time I prioritised elsewhere.

**What I'd build next**: A Celery task per ingestion step, Redis on Railway/Render, and a polling endpoint. The existing `/api/ingest/{id}/status/` endpoint already has the right shape for this.

---

## 2. Airport coordinate lookup for flight distances

**What this would do**: When a travel CSV row has `Origin_IATA=BOM` and `Destination_IATA=DEL` but no `Distance_km` column, automatically look up the great-circle distance using an embedded airport coordinate database (IATA publishes this; open datasets like OpenFlights have ~7,000 airports with lat/lon).

**Why I did not build it**: The Concur export format for this client does include `Distance_km` — the field exists in the sample data. Building the fallback lookup requires embedding a ~2MB airport database, implementing Haversine distance calculation, and handling edge cases (same origin/destination, unknown IATA codes, multi-leg itineraries). This is not hard, but it's work that doesn't add to what the prototype demonstrates about the core ingestion and review workflow.

**What breaks without it**: If a client's Concur export does not include distances (which happens — Concur only calculates distance for mileage-reimbursement expense types, not always for flight bookings), those FLIGHT rows will generate validation errors and cannot have emissions calculated. Analysts would need to manually enter distances or reject those rows.

**What I'd build next**: An `airport_codes` table with lat/lon, a `distance_from_iata_codes(origin, dest)` utility function, and use it as a fallback when `Distance_km` is blank.

---

## 3. Emission factor versioning and a configurable factor table

**What this would do**: Store emission factors in a database table with effective dates instead of hardcoding them in `normalization.py`. Each factor row would have a source type, fuel/activity type, value, unit, effective from/to dates, and a source reference (e.g. "CEA India 2022-23"). Historical recalculations would use the factor that was valid at the time the data was reported.

**Why I did not build it**: Emission factors are published annually and change by a few percent per year. For a 4-day prototype covering one client's FY2023 data, using the latest published factor is acceptable. Factor versioning matters when you need to retroactively recalculate emissions for prior years using the factor that was current then — a requirement that comes up in year-over-year variance reporting and regulatory re-submissions. That use case is real but not in the PM's immediate brief.

**What breaks without it**: If CEA publishes a revised 2022-23 factor (they sometimes do in corrections), you'd need to change the code rather than just updating a database row. More importantly, if this platform is used to report multiple years, the FY2022 data and FY2023 data would both use the same factor even if different factors were current in those years. This is an accuracy problem for multi-year trend reporting.

**What I'd build next**: A `EmissionFactor` model with `source_type`, `activity_type`, `value`, `unit`, `valid_from`, `valid_to`, `reference_url`. The normalization functions would query the appropriate factor for the record's reporting year.

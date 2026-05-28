# Decisions

Every ambiguity I resolved, what I chose, and why.

---

## SAP: Flat-file export, not IDoc or OData

**The options**: IDoc (XML/flat file interchange), OData (REST-like HTTP service), BAPI (programmatic RFC calls), or a plain flat-file ALV export.

**What I chose**: Flat-file ALV export (semicolon-delimited CSV).

**Why**: The PM said "fuel and procurement data sitting in SAP." This implies the data already exists in SAP and needs to be extracted once for ingestion — not a live API integration. The realistic path for a one-time or periodic extract is an ABAP report (custom or standard like MB51) exported from SAP's ALV Grid to a file. SAP teams export this as a tab- or semicolon-delimited TXT file routinely.

IDoc is designed for transactional EDI exchange between SAP systems, not for extracting analytical datasets. OData and BAPI require a live SAP connection, API credentials, and SAP basis team involvement — that's a multi-week integration project, not what a "we need to ingest this data" PM message implies.

The tradeoff: flat-file export means a human has to run the SAP report and upload the file. A real-time OData pull would eliminate that manual step. I'd flag this to the PM: "Should we automate this or is a monthly manual export acceptable?"

**Realistic elements in the sample data**:
- Semicolon delimiter (standard in European SAP, where comma is the decimal separator)
- German column names (`Werks`, `Werksname`, `Buchungsjahr`, `Bericht_Datum`)
- Numeric plant codes (`1001`, `2001`) alongside human names — the code comes from SAP's T001W plant master, the name is a lookup
- Date in DD.MM.YYYY format (German locale)
- Values in `tCO2e` not `mtCO2e` — same unit, different notation, real source of confusion

---

## SAP: Pre-calculated CO2e, not raw fuel quantities

**The ambiguity**: SAP MB51 exports material quantities (litres of diesel, m3 of gas). To get CO2e you need to multiply by an emission factor. Do I store raw quantities and apply factors here, or expect CO2e to already be in the file?

**What I chose**: Pre-calculated CO2e from SAP's Environmental Compliance module.

**Why**: Many enterprise clients running SAP at this scale have SAP's sustainability add-on (SAP Product Footprint Management or older Environmental Compliance). These modules store emission factors in a Z-table and output CO2e directly on reports. An enterprise onboarding client likely has this configured.

The alternative — raw fuel quantities — would require us to maintain a fuel-type-to-emission-factor lookup table, handle different fuels (diesel, natural gas, LPG, coal) with different units, and deal with regional factor variations. That's a reasonable next step but out of scope for a 4-day prototype.

**What I'd ask the PM**: "Does the client's SAP system have the Environmental Compliance module configured? If yes, can they export CO2e directly? If not, what fuel types and units does their MB51 export use?"

---

## Utility: Portal CSV export, not PDF bill or API

**The options**: Portal CSV download, PDF bill parsing, or utility API (if available).

**What I chose**: Portal CSV export.

**Why**: Most commercial/industrial electricity customers in India have access to their utility provider's web portal (MSEDCL, TATA Power, BSES, Adani Electricity). These portals have a "Download billing history" function that exports a CSV or Excel file. This is what a facilities team actually uses — they log in monthly, download the file, and send it to whoever needs it.

PDF parsing would require a PDF parsing library, is fragile (bills change layout between utilities), and requires significant engineering for every new utility. Utility APIs exist in some countries (Green Button in the US, some DISCOM APIs in India) but adoption is patchy and requires separate integration per utility.

**Realistic elements in the sample data**:
- Billing periods do not align with calendar months (meter reads happen every 30 days from installation date, not on the 1st)
- Multiple meters per site (Server Hall and Office Block on the same campus have separate meters)
- Rate codes (HT-1 for high-tension industrial, LT-2 for low-tension commercial)
- Peak demand recorded in kW (demand charges are a significant part of commercial bills)
- No CO2e column — the portal gives you kWh and you apply the grid factor yourself

**The emission factor decision**: I used CEA (Central Electricity Authority) India 2022-23 baseline: 0.716 kgCO2e/kWh. This is the government-published national grid average. The PM's client is an enterprise with facilities across Mumbai, Delhi, Bangalore — all on the same national grid. Using the national average is standard GHG Protocol practice for Indian companies unless they have a market-based Renewable Energy Certificate (REC) arrangement, which would justify a lower factor. I'd ask the PM whether any sites have REC agreements.

**Billing period attribution**: When a billing period spans a year boundary (e.g. Dec 15 – Jan 14), I attribute the full period to the year of Billing_Start. GHG Protocol recommends using the period consumption occurred rather than when billed. This loses some precision at year boundaries but is operationally simpler and consistent with how most companies report.

---

## Travel: Concur CSV export, not API

**The options**: Concur/Navan API pull, CSV export from the platform.

**What I chose**: CSV export from SAP Concur.

**Why**: Concur does have an API, but accessing it requires OAuth setup, IT involvement at the client, and Concur admin credentials. For a prototype ingesting historical data, the simpler path is the CSV export that any Concur administrator can generate from Reports → Export. This is a one-time or quarterly operation.

Navan (formerly TripActions) has a more modern API but the client's system is described as "a corporate travel platform" — Concur is the dominant enterprise choice.

**Realistic elements in the sample data**:
- One row per expense line item, not one row per trip (a single trip generates multiple rows: flight out, hotel, taxi, flight back)
- IATA airport codes for origin and destination (`BOM`, `DEL`, `LHR`) not city names
- Distance in km is included — in real Concur exports this is sometimes present (Concur calculates it for mileage reimbursement) and sometimes not
- Multiple employees, multiple cost centers
- International trips with amounts in INR (converted by the expense system at time of booking)
- Business purpose field (used to filter out personal travel if employees mix personal trips)

**The distance problem**: Concur does not always export distance. For flight segments, if `Distance_km` is missing, we flag the record as a data quality error and cannot calculate emissions. In a production system, we'd look up the great-circle distance from the IATA airport coordinate database. I've documented this as a known gap.

**Emission factor choices**:
- ICAO Carbon Offset and Reduction Scheme (CORSIA) 2023 methodology for flights, with a radiative forcing multiplier of 1.9 (ICAO guidance). Short-haul and long-haul have different factors because aircraft fuel efficiency per seat-km varies significantly with route length.
- DEFRA 2023 conversion factors for hotels and cars (the UK government's published factors are widely used as a global default in the absence of country-specific equivalents for India).

**What I'd ask the PM**: "Does the client's Concur configuration export flight distances? Do they use Concur's built-in sustainability module, or do we need to calculate CO2e ourselves?"

---

## Review workflow: analyst approves all records, not just flagged ones

**The ambiguity**: Should analysts only review records with errors, or everything?

**What I chose**: Create a ReviewTask for every NormalizedRecord. Priority is HIGH for validation errors, MEDIUM for low data quality score (< 70), LOW for clean records.

**Why**: The assignment says "let our analysts review and sign off before it goes to auditors." "Sign off" implies all data, not just problematic data. Auditors expect a complete approval chain. If only flagged records are approved, auditors will ask who approved the clean records, and the answer ("nobody, they were auto-approved") is not audit-ready.

The tradeoff: this creates more work for analysts. For a large ingestion (10,000 rows), reviewing every row is impractical. A production system would add batch-approve for clean records, tiered review (AUTO_APPROVE if score ≥ 95, SAMPLE_REVIEW if score 70-95, FULL_REVIEW if score < 70). I've noted this in TRADEOFFS.md.

---

## Synchronous processing, no task queue

**The ambiguity**: Should parse/normalize run synchronously in the HTTP request, or be queued (Celery, Redis)?

**What I chose**: Synchronous, in-request processing.

**Why**: For a prototype with sample files of 10-50 rows, this is fine. Adding Celery requires Redis, a separate worker process, deployment configuration for both, and handling job status polling. That's a week of engineering for infrastructure that doesn't improve correctness in the prototype.

The HTTP request will time out at around 30 seconds. For files up to ~5,000 rows the normalization completes well within that. I'd switch to async before production.

---

## JWT stored in localStorage, not httpOnly cookie

**The ambiguity**: Where to store the JWT access token in the frontend.

**What I chose**: localStorage.

**Why**: Simpler to implement in the prototype. httpOnly cookies require configuring SameSite, CSRF protection, and coordinating the cookie domain between the frontend origin and the API — additional complexity that doesn't affect correctness.

The security tradeoff: localStorage is accessible to JavaScript, making it vulnerable to XSS. httpOnly cookies are not. I know this is the wrong answer for production. It's the right answer for a prototype where the first priority is getting the thing working.

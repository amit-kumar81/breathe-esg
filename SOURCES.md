# Sources

For each of the three data sources: the real-world format I researched, what I learned, what my sample data looks like and why, and what would break in a real deployment.

---

## Source 1: SAP, Fuel and Procurement Data

### What real-world SAP exports look like

SAP has several ways to get data out: IDoc (XML interchange for EDI), OData (REST service via SAP Gateway), BAPI (RFC function calls), and flat-file exports from the ALV Grid reporting interface.

For fuel and procurement consumption, the relevant standard SAP transactions are:
- **MB51** (Material Documents List): shows all goods movements by material, plant, posting date, movement type. Movement type 261 = goods issue to production order; 201 = goods issue to cost center. These two movement types cover most fuel consumption.
- **ME2M** (Purchase Orders by Material): covers procurement spend.

When a business analyst runs MB51 and clicks "Export → Spreadsheet (TXT)", SAP produces a semicolon-delimited text file. In European SAP installations (which Indian multinationals often use because their ERP was implemented by a German or European consulting firm), the column headers appear in German because they come from SAP's data dictionary, which defaults to German unless explicitly translated.

The columns are SAP technical field names or their German labels:
- `WERKS` → Werk (Plant code, e.g. "1001") — meaningless without the T001W plant master table
- `WERKSNAME` / `Werksname` → Plant name from T001W lookup
- `BUDAT` → Buchungsdatum (Posting date, in YYYYMMDD format internally, DD.MM.YYYY in ALV output)
- `GJAHR` / `Buchungsjahr` → Fiscal year
- `MENGE` → Quantity consumed
- `MEINS` → Unit of measure (L = litres, M3 = cubic metres, KG = kilograms, ST = pieces)
- `MATNR` / `Stoff-Nr` → Material number (SAP's 18-character material ID)
- `MAKTX` / `Bezeichnung` → Material description (can be in German: "Dieselkraftstoff", "Erdgas")

Companies running SAP's Environmental Compliance or SAP Product Footprint Management module can also output CO2e directly. These modules store emission factors in customising tables (Z-tables) and apply them to material movements automatically. The output adds columns like `Scope1_tCO2e`, `Scope2_tCO2e`.

### What I learned

The hardest part of SAP data is not the format — it's the plant codes. `WERKS = 1001` tells you nothing without SAP access to look up the plant name in T001W. Many real SAP exports do not include plant names, only codes. You need a separate plant master extract to join against.

German column headers are common even in Indian subsidiaries because the SAP system was implemented by a German/European integrator who left the defaults. Data teams sometimes get mixed exports where some columns are in German and others in English depending on which user exported the file and what their SAP language setting is.

Dates in ALV exports come out as DD.MM.YYYY in the display, but in underlying ABAP programs they're stored as YYYYMMDD. The ALV export format depends on the user's SAP date format setting. Our parser handles both.

The "inconsistent units" the assignment mentions is real: the same material category might be measured in litres at one plant and kilograms at another, depending on how the plant configured their material master. Normalising across units requires the emission factor to handle multiple input units for the same fuel type — we did not implement this since our sample data uses a summary report with CO2e already calculated.

### What my sample data looks like and why

Three files, representing a half-year extract (Q1+Q2 2023), a half-year extract (Q3+Q4 2023), and a full-year extract for the prior year (FY2022). This is a realistic pattern — companies often run half-year or quarterly extracts for interim reporting, plus a year-end full export.

Format: semicolon-delimited, German column names (`Werks`, `Werksname`, `Buchungsjahr`, `Bericht_Datum`, `Scope1_tCO2e`, `Scope2_tCO2e`, `Scope3_tCO2e`). One row per plant per reporting period. Values in tCO2e (pre-calculated by SAP Environmental Compliance module).

Emissions values are modelled on published GHG disclosures from large Indian industrial companies (refinery and petrochemical operations in the 4,000–8,000 tCO2e/year range for individual plants, IT campuses below 500 tCO2e Scope 1 with significant Scope 2 from power consumption).

### What would break in a real deployment

1. **Plant codes without names**: If the client's SAP doesn't include `Werksname` and only exports `Werks = 1001`, our `facility_name` field is a numeric code. We'd need a separate plant master CSV to resolve it.

2. **Raw fuel quantities instead of CO2e**: If the client doesn't have SAP Environmental Compliance, the export has `MENGE` (quantity in litres) not CO2e. Our normalizer would need to apply emission factors per material and unit — a significant addition.

3. **Multiple materials per plant per year**: The realistic MB51 output has one row per material per goods movement. A single plant might have 500 rows per month. Our field mapping assumes one row per plant per reporting period (the summary view). We'd need to aggregate.

4. **Date format variations**: Different SAP language settings produce different date formats. We handle DD.MM.YYYY and YYYYMMDD. Other formats (MM/DD/YYYY, YYYY.MM.DD) would need parser additions.

5. **Unicode and encoding**: SAP exports from some systems come in Windows-1252 or ISO-8859-1 encoding, not UTF-8. German characters like ä, ö, ü would corrupt if decoded as UTF-8. The upload endpoint assumes UTF-8.

---

## Source 2: Utility Data, Electricity

### What real-world utility portal exports look like

Commercial and industrial electricity customers in India access their billing history through utility web portals. The major utilities with significant commercial customer bases in our sample's locations:
- **Mumbai**: MSEDCL (Maharashtra State Electricity Distribution), Adani Electricity, Tata Power
- **Delhi**: BSES Rajdhani, BSES Yamuna, Tata Power Delhi
- **Bangalore**: BESCOM (Bangalore Electricity Supply Company)

Each portal's "Download billing history" function produces a CSV or Excel file. The column structure varies by utility but common elements are:

- **Account/Consumer Number**: The utility's identifier for the connection
- **Service Address**: The physical address of the meter
- **Billing Period**: Start and end date of the billing cycle
- **Meter Reading**: Opening and closing meter reads in kWh
- **Consumption**: kWh used in the period (closing − opening read)
- **Peak Demand**: Maximum 15-minute demand in kW (relevant for high-tension connections)
- **Rate Schedule / Tariff**: The tariff code (HT-1 = High Tension Industrial, LT-2 = Low Tension Commercial, etc.)
- **Total Charges**: Billed amount in INR

Key real-world characteristics:
- **Billing period ≠ calendar month**: Meters are read every 30 days from the connection date, not on the 1st of each month. A meter installed on the 15th reads on the 15th of each month. This means the "October" bill might cover Oct 15 – Nov 14.
- **Multiple meters per site**: Large campuses have separate connections for different loads (server hall, office block, chiller plant). Each appears as a separate row with its own meter ID.
- **Demand charges**: HT connections (industrial) are billed for both energy (kWh) and peak demand (kW). Both columns appear in the export.
- **No CO2e column**: Utility bills do not include carbon calculations. That is always done by the company or their ESG software.

### What I learned

The billing period misalignment is the most significant data quality issue for annual reporting. A company reporting calendar-year emissions (Jan 1 – Dec 31) using utility billing data will always have partial periods at each boundary: the bill that covers Dec 15 – Jan 14 straddles the year boundary. The GHG Protocol guidance (Chapter 4, Scope 2) says to use the period in which energy was consumed, and to use pro-rating if necessary. In practice, most companies attribute the full billing period to the year of the billing start date, which is what we do.

The India-specific factor is significant: India's grid is dirtier than the US or EU average. At 0.716 kgCO2e/kWh (CEA 2022-23), it's roughly double the US national average and 4× the French grid (which is mostly nuclear). This makes electricity Scope 2 a large contributor for Indian companies — data centers with 100,000+ kWh monthly consumption generate significant Scope 2 emissions.

### What my sample data looks like and why

Three files: Mumbai (data center and admin offices), Delhi (office tower, cold storage, processing plant), Bangalore (two IT campuses, each with separate server hall and office block meters).

Each row is one billing period for one meter. Multiple rows per site per file — two or three billing periods covering Q3-Q4 2023. This reflects the real pattern: a quarterly download of billing history returns 3 rows per meter (3 billing cycles).

Values: Data center meters at 40,000-200,000 kWh per billing period (realistic for a medium-to-large enterprise data center). Office buildings at 7,000-15,000 kWh per period (realistic for a 3-5 floor commercial office). All billing charges calculated at approximate MSEDCL/BESCOM 2023 commercial tariff rates.

### What would break in a real deployment

1. **Multiple utility formats**: If the client has meters from 5 different utilities (MSEDCL, Adani, BESCOM, BSES, TATA), each portal exports in a slightly different column format. We'd need a DataSource configuration per utility, not per client.

2. **Excel format**: Most utility portals actually export as .xlsx (Excel), not .csv. Our upload endpoint only handles CSV. We'd need Excel parsing (openpyxl) as a pre-processing step.

3. **Demand charges in the emissions calculation**: We only use kWh for the emission calculation, ignoring peak demand (kW). This is correct — you pay for demand but it doesn't directly map to additional energy consumed. But the demand column is in the data and some analysts expect it to factor in somehow.

4. **Market-based vs location-based Scope 2**: We use the location-based grid factor (CEA national average). Companies with Renewable Energy Certificate (REC) agreements or direct renewable power purchase agreements can use a market-based factor (potentially zero for certified green power). We have no mechanism to override the factor per meter.

5. **Net metering / on-site generation**: Some facilities have rooftop solar and export surplus to the grid. Utility exports for net-metered connections show negative consumption values in some months. Our validator would reject negative kWh as invalid.

---

## Source 3: Corporate Travel, Flights, Hotels, Ground Transport

### What real-world Concur/Navan exports look like

SAP Concur is the dominant corporate travel and expense management platform for large enterprises. Navan (formerly TripActions) is the main challenger. Both allow expense report administrators to export data as CSV.

In Concur, the export path is: Reports → Expense → Export Data. This produces a flat CSV with one row per expense line item. A single business trip generates multiple rows: one for each flight segment, one for each hotel night (or a single row for the full hotel stay), one for each ground transport.

Typical columns in a Concur expense export:
- `Report Name`: The expense report title (usually "Q4 2023 Travel" or similar)
- `Employee ID` / `Employee Name`
- `Transaction Date`: Date of the expense
- `Expense Type`: Category — Airfare, Hotel, Car Rental, Taxi/Uber, Train, Meals, etc.
- `Vendor`: Airline, hotel chain, car rental company name
- `Amount`: Cost in the transaction currency
- `Currency`
- `Exchange Rate`, `Amount in Reimbursement Currency`: For international trips
- `Business Purpose`: Free text field for justification
- `Cost Center`

For travel-specific fields (present in some Concur configurations):
- `Origin City` / `Destination City`: Or IATA codes if the Concur admin has enabled flight booking integration
- `Distance` / `Miles`: Present for car rental and personal vehicle mileage claims; sometimes for flights if Concur's trip booking tool calculated it
- `Number of Nights`: For hotel expense types

What's absent: CO2e is not in a standard Concur export unless the company has purchased Concur's separate sustainability reporting module (SAP Concur Sustainability), which is an add-on that costs extra. Most companies don't have it.

### What I learned

The expense type problem is the central challenge. "Airfare" in Concur is a catch-all. It might be a domestic flight, an international business-class flight, or a train ticket that someone miscategorised. The emission factor differences are significant: domestic short-haul has a factor almost 2× higher per passenger-km than long-haul, and business class has a factor 2.5–3× higher than economy class. Without seat class information (which Concur doesn't reliably export), you're forced to use economy class as a default assumption.

Distances are missing more often than present. Concur calculates distances for car mileage reimbursement (company car or personal vehicle claims) but not always for flight segments. The IATA airport codes are present in some Concur configurations (where the booking was made through Concur Travel) but not for expenses entered manually by employees.

Navan exports are structured differently — they have a separate trip booking export and an expense export, and matching flight bookings to expense claims requires a join on trip ID. I designed the sample data to match Concur's single flat export, which is what most enterprises use.

### What my sample data looks like and why

Two files: Q3 2023 and Q4 2023 expense reports. Each file has one row per expense line item across several employees. Expense types include FLIGHT, HOTEL, TAXI, and CAR_RENTAL.

Destinations and airline choices are realistic for an Indian company with headquarters in Mumbai:
- Domestic routes: BOM-DEL (1148 km), BLR-BOM (984 km), MAA-DEL (1760 km) — actual great-circle distances for those city pairs
- International routes: DEL-LHR (6700 km, British Airways), BOM-SIN (5280 km, Air India), DEL-DXB (2200 km), BOM-FRA (7280 km)
- Hotels at destinations, not origin cities
- Taxi distances for local transport (18-60 km, realistic for city airport transfers)

IATA codes are correct: BOM = Mumbai, DEL = Delhi, BLR = Bangalore, MAA = Chennai, HYD = Hyderabad, SIN = Singapore, LHR = London Heathrow, DXB = Dubai, FRA = Frankfurt, AMD = Ahmedabad.

### What would break in a real deployment

1. **Missing distances for flights**: If the client's Concur configuration doesn't export `Distance_km`, all FLIGHT rows generate validation errors. We'd need the IATA airport coordinate lookup (see TRADEOFFS.md).

2. **Seat class**: We assume economy class for all flights. Business class has a factor approximately 2.5× higher. If expense reports show business class bookings (identified by the higher fare), we're significantly underestimating Scope 3.

3. **Expense type categorisation inconsistency**: Employees mis-categorise expenses. A train ticket might be coded as "Airfare" because the employee chose the wrong category. We'd need validation rules or a mapping from merchant names to correct expense types.

4. **Multi-currency**: International trips have amounts in foreign currency. We store the INR amount (as converted by Concur) but the original currency column is ignored. If Concur's exchange rate was applied on the transaction date but reporting uses a different rate, there's a reconciliation issue (though this affects the financial amount, not the emissions calculation).

5. **Hotel nights from line-item dates**: In some Concur exports, a 3-night hotel stay appears as a single row with amount for all 3 nights, and the night count must be inferred from the check-in/check-out dates rather than a dedicated column. We use an explicit `Hotel_Nights` column, which requires the Concur export to be configured to include it.

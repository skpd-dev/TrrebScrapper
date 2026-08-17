# TRREB Rental Data Pipeline

An incremental Python data pipeline that collects publicly available Toronto rental listings, tracks listing lifecycle changes, geocodes properties, and enriches them with public-transit accessibility data using OpenTripPlanner.

## What it does

```text
TRREB Search
     │
     ▼
Listing Discovery
     │
     ├── New ──────► Extract + Enrich
     │
     ├── Existing ─► Keep Live
     │
     └── Missing ──► Move to Lost
                         │
                         ▼
                  Historical Record
```

The pipeline maintains two datasets:

* **Live** — listings currently appearing in the configured TRREB search
* **Lost** — listings previously observed but no longer appearing in the search

This makes the dataset incremental and preserves listing lifecycle history instead of simply deleting disappeared records.

## Key Features

* Async HTTP ingestion with `asyncio` + `httpx`
* Bounded concurrency for listing requests
* Pagination and URL-based deduplication
* Incremental new/listing detection
* Live → Lost lifecycle tracking
* Address normalization and unit/floor extraction
* Geocoding with OpenStreetMap Nominatim
* Transit routing through OpenTripPlanner GraphQL
* Transit optimization by:

  * Minimum transfers
  * Shortest duration
* Approximate transit headway/frequency calculation
* Excel output with `Live` and `Lost` sheets
* CSV export for downstream analytics

## Architecture

```text
                 TRREB
                   │
                   ▼
            Async Ingestion
                   │
                   ▼
          Address Normalization
                   │
             ┌─────┴─────┐
             ▼           ▼
         Geocoding    State Check
             │           │
             ▼           ▼
      OpenTripPlanner  Live/Lost
             │
             ▼
       Transit Metrics
             │
             ▼
        Excel / CSV
```

## Repository Structure

```text
├── main.py       # Pipeline orchestration and lifecycle management
├── scraper.py    # TRREB pagination and listing extraction
├── transit.py    # Geocoding and OpenTripPlanner enrichment
├── utils.py      # Address normalization and data cleaning
├── config.py     # Search parameters and service configuration
└── README.md
```

## Listing Lifecycle

Each execution compares the current TRREB search snapshot with the previous `Live` dataset.

```python
new  = current_urls - previous_live_urls
lost = previous_live_urls - current_urls
```

Listings that disappear are moved to `Lost` rather than permanently deleted.

If a previously lost listing appears again, it can return to `Live`.

This provides a lightweight historical state model:

```text
NEW → LIVE → LOST
          ↑
          └── REAPPEARED
```

## Data Enrichment

Each new listing is normalized and geocoded before being sent to OpenTripPlanner.

Example:

```text
4 Wild Rose Gdns Upper
          │
          ▼
4 Wild Rose Gardens
          │
          ▼
Latitude / Longitude
          │
          ▼
Transit itineraries
```

The pipeline separates unit/floor annotations from the physical address to improve geocoding reliability.

Transit enrichment produces metrics including:

* Total duration
* Number of transfers
* Transit routes
* Approximate route frequency

Two optimization strategies are retained:

**Minimum transfers**

> Fastest itinerary among options with the fewest transfers.

**Shortest duration**

> Fastest available itinerary regardless of transfer count.

## Output

The pipeline generates:

```text
trreb_listings.xlsx
```

### Live

Current listings matching the configured search.

### Lost

Previously observed listings that are no longer present in the current search.

It also exports the current live dataset to CSV for downstream processing.

## Technology

* Python
* asyncio
* httpx
* BeautifulSoup
* Pandas
* OpenPyXL
* OpenStreetMap Nominatim
* OpenTripPlanner
* GraphQL

## Responsible Data Collection

The project works with information exposed through publicly accessible listing pages and does not attempt to bypass authentication, CAPTCHAs, access controls, or other technical protections.

Request concurrency is bounded and incremental processing avoids repeatedly requesting listings that have already been processed.

Automated access policies and website terms can change, so users should review the applicable terms and restrictions before operating the pipeline.

## Why I Built It

This project started as a rental-listing scraper but evolved into an end-to-end data engineering workflow involving:

**ingestion → incremental processing → data quality → geospatial enrichment → API integration → historical state → analytics.**

It demonstrates how semi-structured external data can be transformed into a structured, continuously maintained analytical dataset.

## Future Improvements

* PostgreSQL / Parquet storage
* Automated scheduling
* Retry and exponential backoff
* Data-quality tests
* Structured logging and monitoring
* Historical price tracking
* Dockerized OpenTripPlanner
* Power BI analytics
* Listing lifetime and rental-market analysis

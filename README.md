# TRREB Rental Data & Transit Intelligence Pipeline

An end-to-end Python data engineering pipeline for collecting, cleaning, tracking, and enriching Toronto rental listings with public-transit accessibility data.

The pipeline turns semi-structured rental listing data into a continuously maintained dataset containing:

* Rental property information
* Listing lifecycle history
* Normalized addresses
* Geographic coordinates
* Transit routes
* Travel times
* Transfer counts
* Approximate transit frequency

```text id="9b7h3n"
                 TRREB
                   │
                   ▼
          Rental Listing Search
                   │
                   ▼
        Pagination + URL Discovery
                   │
          ┌────────┴────────┐
          ▼                 ▼
        NEW              EXISTING
          │                 │
          ▼                 ▼
   Listing Extraction     LIVE
          │
          ▼
   Address Normalization
          │
          ▼
       Geocoding
          │
          ▼
 OpenTripPlanner / GraphQL
          │
          ▼
     Transit Enrichment
          │
          ▼
       Live Dataset
          │
          └──────► Lost Listing Detection
```

---

## What It Does

### Rental Data Collection

The pipeline discovers rental listings from a configured TRREB search and extracts structured property information from individual listing pages.

The scraper handles:

* Search pagination
* Listing URL discovery
* Duplicate detection
* New listing detection
* Asynchronous listing requests
* HTML parsing
* Rental price extraction
* Square footage extraction
* Included amenities/items
* Address extraction
* Unit/floor information

Typical listing fields include:

```text id="j3e6c5"
Raw_Address
Address
Unit_Details
Price
SqFt
Included
Included_Count
URL
```

---

# Incremental Listing Tracking

The pipeline does not treat every execution as a completely new scrape.

Instead, the current TRREB search is compared with the previous dataset.

```python id="h9p7mk"
new = current_urls - previous_live_urls

lost = previous_live_urls - current_urls
```

This creates a simple listing lifecycle:

```text id="19x3fq"
             NEW
              │
              ▼
             LIVE
              │
       disappears from
       current search
              │
              ▼
             LOST
              │
       appears again
              │
              ▼
             LIVE
```

### Live

Listings currently appearing in the configured TRREB search.

### Lost

Listings that were previously observed but are no longer found in the current search.

Lost listings are **not deleted**. They are retained as historical records.

This allows the dataset to eventually answer questions such as:

* How many listings appeared each week?
* How long did listings remain active?
* Which neighborhoods have the highest turnover?
* How quickly do listings disappear?
* What prices were listings advertised at before disappearing?
* Which listings reappeared?

`Lost` does not necessarily mean "rented." A listing can disappear because it expired, changed status, was removed, or no longer matches the configured search criteria.

---

# Rental Listing Extraction

Listing detail pages are parsed using BeautifulSoup and transformed into structured records.

The scraper converts semi-structured HTML into tabular data suitable for Pandas and downstream analytics.

Example:

```text id="u6y0gh"
TRREB HTML
    │
    ▼
BeautifulSoup
    │
    ▼
Structured Python record
    │
    ▼
Pandas DataFrame
```

This separates **web acquisition** from the downstream transformation and enrichment stages.

---

# Address Normalization

Real-estate data contains many inconsistent address formats.

Examples include:

```text id="d0a7mx"
4 Wild Rose Gdns Upper
123 Main St 2F
55 King St Main Floor
100 Queen St (2nd bedroom)
```

The pipeline cleans these into geocodable physical addresses while preserving useful listing metadata separately.

For example:

```text id="hx5jcf"
Raw_Address:
4 Wild Rose Gdns Upper

Address:
4 Wild Rose Gardens

Unit_Details:
Gdns Upper
```

The normalization layer handles common abbreviations and listing annotations such as:

```text
Gdns       → Gardens
Gdn        → Garden
Crt        → Court
Terr       → Terrace
Ave        → Avenue
St         → Street
Rd         → Road
Cres       → Crescent
2F         → Unit/floor metadata
Main Floor → Unit/floor metadata
(2nd bedroom) → Listing metadata
```

Separating these values improves geocoding reliability without discarding the original listing information.

---

# Geospatial & Transit Enrichment

Once a property has a clean physical address, the pipeline enriches it with geographic and transit information.

```text id="a5v5xb"
Rental Address
      │
      ▼
OpenStreetMap Nominatim
      │
      ▼
Latitude / Longitude
      │
      ▼
OpenTripPlanner
      │
      ▼
Transit Itineraries
```

This turns a rental listing into a location-aware record.

---

# OpenStreetMap Geocoding

The pipeline uses OpenStreetMap Nominatim to convert normalized addresses into:

```text id="9ddw8f"
Latitude
Longitude
```

Because real-world addresses are messy, geocoding can fail even when an address is valid.

The enrichment layer is therefore designed to support address normalization and fallback strategies rather than treating the first failed lookup as proof that an address is invalid.

---

# OpenTripPlanner Transit Routing

The coordinates generated by geocoding are passed to a locally hosted OpenTripPlanner instance.

The pipeline communicates with OpenTripPlanner through its GraphQL interface.

For each property, the routing query can return multiple itinerary alternatives containing information such as:

* Total duration
* Start time
* End time
* Transit modes
* Route names
* Route numbers
* Number of transfers

```text id="m1z7ph"
Property Coordinates
        │
        ▼
OpenTripPlanner
        │
        ▼
GraphQL Query
        │
        ▼
Multiple Itineraries
```

This allows the pipeline to analyze transit options instead of simply storing a single route.

---

# Transit Analysis

The pipeline evaluates the returned itineraries using two different strategies.

## Minimum Transfers

Prioritizes:

```text id="6hfl9v"
Transfers
    ↓
Duration
```

This identifies the fastest itinerary among options with the fewest transfers.

Useful when route simplicity is more important than absolute travel time.

## Shortest Duration

Prioritizes:

```text id="0xw8d6"
Duration
    ↓
Transfers
```

This identifies the fastest available itinerary.

The two metrics are intentionally kept separate because the fastest route is not necessarily the most convenient route.

Example:

```text id="r40f3h"
Option A
40 minutes
0 transfers

Option B
31 minutes
2 transfers
```

The dataset preserves both possibilities.

---

# Transit Frequency

The pipeline also derives an approximate transit frequency/headway from itinerary departure times.

For example:

```text id="b5z7tq"
08:00
08:12
08:24
08:36
```

can produce an estimated:

```text id="b6a9pm"
~12 minute headway
```

This provides another property-level accessibility metric beyond travel time.

The frequency value is an analytical estimate based on returned itinerary data and should not be interpreted as an official transit-service guarantee.

---

# Asynchronous Processing

The rental ingestion layer uses:

* `asyncio`
* `httpx.AsyncClient`
* `asyncio.gather()`
* `asyncio.Semaphore`

Listing detail pages are network-bound, so asynchronous I/O allows multiple requests to progress concurrently without creating an unrestricted number of simultaneous connections.

The pipeline also uses incremental processing so that listings already present in the dataset do not need to be repeatedly scraped and enriched.

---

# Output

The main output is:

```text id="lzz4bf"
trreb_listings.xlsx
```

## Live

Contains currently active listings matching the configured TRREB search.

Includes rental information and, where successfully enriched, transit information.

## Lost

Contains previously discovered listings that are no longer present in the current search.

Historical fields such as:

```text id="6o7w4q"
First_Seen
Lost_Date
Status
```

can be used for lifecycle analysis.

The current Live dataset is also exported to CSV for downstream processing.

---

# Repository Structure

```text id="s7t7cg"
TrrebScrapper/
│
├── main.py
│   └── Pipeline orchestration,
│       Live/Lost lifecycle management,
│       Excel/CSV output
│
├── scraper.py
│   └── TRREB pagination,
│       URL discovery,
│       asynchronous listing extraction
│
├── transit.py
│   └── Geocoding,
│       OpenTripPlanner GraphQL,
│       transit analysis
│
├── utils.py
│   └── Address normalization,
│       unit/floor extraction,
│       data cleaning
│
├── config.py
│   └── Search parameters,
│       endpoints and configuration
│
└── README.md
```

---

# Technology Stack

| Technology                  | Purpose                        |
| --------------------------- | ------------------------------ |
| **Python**                  | Pipeline implementation        |
| **asyncio**                 | Asynchronous I/O               |
| **httpx**                   | Async HTTP requests            |
| **BeautifulSoup**           | HTML parsing                   |
| **Pandas**                  | Data transformation            |
| **OpenPyXL**                | Excel output                   |
| **Requests**                | Geocoding/routing HTTP session |
| **OpenStreetMap Nominatim** | Address geocoding              |
| **OpenTripPlanner**         | Transit routing                |
| **GraphQL**                 | Transit API interface          |
| **CSV / Excel**             | Data persistence               |

---

# Data Engineering Architecture

The project can be viewed as an end-to-end ETL/ELT-style workflow:

```text id="q8j7na"
             EXTRACT
                │
                ▼
         TRREB Rental Data
                │
                ▼
        HTML → Structured Data
                │
                ▼
             TRANSFORM
                │
                ▼
       Address Normalization
                │
                ▼
              ENRICH
                │
       ┌────────┴────────┐
       ▼                 ▼
   Geocoding        Transit Routing
       │                 │
       └────────┬────────┘
                ▼
             ANALYZE
                │
       ┌────────┴────────┐
       ▼                 ▼
 Rental Attributes   Transit Metrics
       │                 │
       └────────┬────────┘
                ▼
              LOAD
                │
       ┌────────┴────────┐
       ▼                 ▼
      Live              Lost
     Excel              Excel
```

---

# Responsible Data Collection

The project works with information exposed through publicly accessible listing pages.

It does not attempt to bypass:

* Authentication
* CAPTCHAs
* Access controls
* Technical protections

The scraper uses incremental processing, connection reuse, and bounded concurrency to avoid unnecessary repeated requests.

No automated system can guarantee that a website will never rate-limit or block requests. Users should review applicable website terms and access policies before operating the pipeline.

---

# Why This Project

This project demonstrates more than web scraping.

It combines:

**Web Data Engineering**

* Pagination
* Async ingestion
* HTML parsing
* Deduplication
* Incremental processing

**Data Quality**

* Address normalization
* Unit/floor extraction
* Geocoding fallbacks

**Data Integration**

* OpenStreetMap
* OpenTripPlanner
* GraphQL

**Analytics**

* Transit duration
* Transfer complexity
* Route selection
* Approximate frequency
* Listing lifecycle

**Data Persistence**

* Live state
* Historical lost listings
* Excel
* CSV

The result is a property-level dataset combining **rental-market data and transit accessibility**.

---

# Future Improvements

* PostgreSQL / Parquet storage
* Historical price tracking
* Listing-level change detection
* Automated scheduling
* Retry and exponential backoff
* Structured logging
* Data-quality tests
* Dockerized OpenTripPlanner
* Transit accessibility scoring
* Historical commute analysis
* Power BI dashboard
* Rental-market time-series analysis

# TRREB Rental & Transit Intelligence Pipeline

An incremental Python data engineering pipeline that collects publicly available Toronto rental listings and enriches each property with **multimodal public-transit accessibility data using OpenTripPlanner and GraphQL**.

The project combines web ingestion, address normalization, geospatial processing, transit routing, itinerary analysis, and historical listing lifecycle tracking.

## What It Does

```text
                 TRREB
                   │
                   ▼
          Rental Listing Discovery
                   │
                   ▼
          Address Normalization
                   │
                   ▼
              Geocoding
                   │
                   ▼
        Latitude / Longitude
                   │
                   ▼
        OpenTripPlanner GraphQL
                   │
                   ▼
          Transit Itineraries
                   │
          ┌────────┴────────┐
          ▼                 ▼
   Min Transfers      Shortest Time
          │                 │
          └────────┬────────┘
                   ▼
          Transit Analytics
                   │
                   ▼
             Live / Lost
              Dataset
```

---

## Transit Intelligence

The main purpose of the enrichment layer is to answer:

> **"Given this rental property's location, how accessible is my target destination by public transit?"**

Instead of simply calculating straight-line distance or attaching a transit link, the pipeline queries a locally hosted **OpenTripPlanner** instance through its GraphQL API and analyzes the returned itineraries.

For each property, the system can extract:

* Total travel duration
* Departure time
* Arrival time
* Number of transfers
* Transit modes
* Transit routes
* Route short names
* Route long names
* Approximate route frequency/headway

### Routing Flow

```text
Rental Address
      │
      ▼
Nominatim Geocoder
      │
      ▼
Latitude / Longitude
      │
      ▼
OpenTripPlanner
      │
      ▼
GraphQL Itinerary Query
      │
      ▼
Multiple Candidate Routes
      │
      ├──────────────┐
      ▼              ▼
Transfer Analysis   Duration Analysis
      │              │
      ▼              ▼
Minimum Transfers   Shortest Duration
      │              │
      └───────┬──────┘
              ▼
       Property Metrics
```

The routing layer requests multiple itinerary alternatives rather than assuming that the first returned route is automatically the best option.

---

## Two Transit Optimization Strategies

Transit "best" is subjective, so the pipeline preserves two different optimization strategies.

### 1. Minimum Transfers

Prioritizes:

```text
Number of transfers
        ↓
Travel duration
```

This answers:

> **What is the fastest itinerary among the options requiring the fewest transfers?**

Useful for commuters who prioritize simplicity and reliability over absolute travel time.

Example:

```text
42 minutes
0 transfers
```

may be preferable to:

```text
31 minutes
2 transfers
```

### 2. Shortest Duration

Prioritizes:

```text
Travel duration
        ↓
Number of transfers
```

This answers:

> **What is the fastest available itinerary?**

Example:

```text
31 minutes
2 transfers
```

The pipeline therefore preserves both perspectives instead of reducing transit accessibility to a single number.

---

## Transit Frequency / Headway

The pipeline also derives an approximate transit frequency from departure times returned by OpenTripPlanner.

For example:

```text
08:00
08:12
08:24
08:36
```

produces an approximate:

```text
12 minute headway
```

This gives the rental dataset another useful dimension beyond journey time:

```text
Property
   │
   ├── Travel Time
   ├── Transfers
   ├── Routes
   └── Approximate Frequency
```

This is an analytical estimate based on the returned itinerary data, not an official transit-frequency guarantee.

---

## Listing Lifecycle

The pipeline also maintains an incremental view of the rental market.

Each run compares the current TRREB search snapshot with the previous `Live` dataset.

```python
new = current_urls - previous_live_urls
lost = previous_live_urls - current_urls
```

Listings are classified as:

```text
NEW → LIVE → LOST
          ↑
          │
      REAPPEARED
```

### `Live`

Listings currently appearing in the configured search.

### `Lost`

Listings previously observed but no longer appearing in the current search.

A listing being `Lost` does **not** automatically mean it was rented. It may have expired, changed status, been removed, or stopped matching the configured search criteria.

Historical `Lost` records are retained rather than deleted.

---

## Async Data Ingestion

Listing pages are I/O-bound, so the scraper uses:

* `asyncio`
* `httpx.AsyncClient`
* `asyncio.gather`
* bounded concurrency with `asyncio.Semaphore`

This allows multiple listing requests to be processed concurrently while preventing an unrestricted number of simultaneous requests.

Only newly discovered listings need detailed extraction and transit enrichment, reducing unnecessary downstream API work.

---

## Address Normalization

Real-estate listing addresses often contain unit and floor information that can interfere with geocoding.

Examples:

```text
4 Wild Rose Gdns Upper
123 Main St 2F
55 King St Main Floor
100 Queen St (2nd bedroom)
```

The pipeline separates the physical address from listing-specific annotations:

```text
Raw:
4 Wild Rose Gdns Upper

Address:
4 Wild Rose Gardens

Unit_Details:
Gdns Upper
```

This normalized address is then used for geocoding.

Fallback geocoding strategies can handle variations such as:

```text
Gdns ↔ Gardens
St ↔ Street
Ave ↔ Avenue
Cres ↔ Crescent
```

---

## Output

The primary output is:

```text
trreb_listings.xlsx
```

### Live

Current rental listings with their property and transit information.

### Lost

Previously observed listings that are no longer present in the current search.

The pipeline also exports the current live dataset as CSV for downstream analysis.

---

## Repository Structure

```text
TrrebScrapper/
│
├── main.py
│   └── Pipeline orchestration,
│       lifecycle tracking and output
│
├── scraper.py
│   └── TRREB pagination,
│       URL discovery and listing extraction
│
├── transit.py
│   └── Geocoding + OpenTripPlanner
│       GraphQL transit enrichment
│
├── utils.py
│   └── Address normalization
│       and data cleaning
│
├── config.py
│   └── Search and service configuration
│
└── README.md
```

---

## Technology Stack

| Technology                | Purpose                    |
| ------------------------- | -------------------------- |
| Python                    | Pipeline implementation    |
| asyncio                   | Concurrent I/O             |
| httpx                     | Async HTTP ingestion       |
| BeautifulSoup             | HTML parsing               |
| Pandas                    | Data transformation        |
| OpenPyXL                  | Excel output               |
| Nominatim / OpenStreetMap | Geocoding                  |
| OpenTripPlanner           | Multimodal transit routing |
| GraphQL                   | Transit data interface     |
| Excel / CSV               | Data persistence           |

---

## Responsible Data Collection

The ingestion layer works with information exposed through publicly accessible listing pages.

It does not attempt to bypass:

* Authentication
* CAPTCHAs
* Access controls
* Technical protections

The scraper uses incremental processing, connection reuse, and bounded concurrency to avoid unnecessarily repeating requests.

No automated system can guarantee that a website will never rate-limit or block requests. Users should review applicable website terms and access policies before operating the pipeline.

---

## Why This Project?

The project evolved beyond a traditional web scraper into an end-to-end data engineering pipeline:

```text
Public Web Data
      ↓
Async Ingestion
      ↓
Incremental State
      ↓
Data Normalization
      ↓
Geospatial Enrichment
      ↓
GraphQL API Integration
      ↓
Transit Routing
      ↓
Itinerary Optimization
      ↓
Historical Analytics
```

The result is a property-level dataset that combines **rental-market information with real-world transit accessibility**.

This creates opportunities for analysis such as:

* Rental price vs. commute time
* Rental price vs. transit accessibility
* Transfer complexity by neighborhood
* Transit frequency vs. rental price
* Listing lifetime by neighborhood
* Best rental locations for a specific destination

---

## Future Improvements

* Historical rental-price tracking
* PostgreSQL / Parquet storage
* Automated scheduling
* Retry and exponential backoff
* Structured logging and monitoring
* Transit accessibility scoring
* Historical commute-time analysis
* Dockerized OpenTripPlanner
* Power BI dashboard
* Automated data-quality testing

import asyncio
from urllib.parse import urlencode

import bs4
import httpx
import pandas as pd

from config import BASE_SEARCH_URL, BASE_URL, HEADERS
from utils import clean_address_and_extract_unit


def build_paginated_url(base_url: str, params: dict, skip: int) -> str:
    """
    Build a TRREB search URL for a specific pagination offset.
    """
    current_params = params.copy()
    current_params["$skip"] = skip

    query_string = urlencode(current_params, doseq=True)

    return f"{base_url}?{query_string}"


async def fetch_listing_details(
    client: httpx.AsyncClient,
    listing_path: str
) -> dict | None:
    """
    Fetch and parse a single TRREB listing page.
    """

    url = (
        f"{BASE_URL}{listing_path}"
        if not listing_path.startswith("http")
        else listing_path
    )

    try:
        response = await client.get(url)

        # Do not parse failed HTTP responses as listings.
        response.raise_for_status()

        soup = bs4.BeautifulSoup(response.text, "html.parser")

        # -----------------------------
        # ADDRESS
        # -----------------------------

        addr_el = soup.select_one(".addr h1")

        raw_address = (
            addr_el.get_text(strip=True)
            if addr_el
            else "N/A"
        )

        clean_addr, unit_details = clean_address_and_extract_unit(
            raw_address
        )

        # -----------------------------
        # PRICE
        # -----------------------------

        price_el = soup.select_one(".price h1 span")

        price = (
            price_el.get_text(strip=True)
            if price_el
            else "N/A"
        )

        # -----------------------------
        # SQFT
        # -----------------------------

        sqft = "N/A"

        for td in soup.select(".short-details td, td"):

            if "SqFt" in td.get_text():

                small_tag = td.find("small")

                if small_tag:
                    sqft = small_tag.get_text(strip=True)

                break

        # -----------------------------
        # INCLUDED ITEMS
        # -----------------------------

        included_items = []

        included_span = soup.find(
            lambda tag:
            tag.name == "span"
            and "section-title" in tag.get("class", [])
            and tag.get_text(strip=True).upper() == "INCLUDED"
        )

        if included_span:

            container = (
                included_span.find_parent(["div", "section"])
                or included_span.parent
            )

            included_items = [
                li.get_text(strip=True)
                for li in container.find_all("li")
                if li.get_text(strip=True)
            ]

        included_count = len(included_items)

        return {
            "Raw_Address": raw_address,
            "Address": clean_addr,
            "Unit_Details": unit_details,
            "Price": price,
            "SqFt": sqft,
            "Included": (
                ", ".join(included_items)
                if included_items
                else "None listed"
            ),
            "Included_Count": included_count,
            "URL": url,
        }

    except Exception as e:

        print(f"⚠️ Error scraping {url}: {e}")

        return None


async def discover_all_listing_urls(
    base_search_url: str,
    search_params: dict,
    limit: int = 100
) -> set[str]:
    """
    Scan the complete TRREB search result.

    Returns:
        set[str]: every listing URL currently visible
        in the configured search.
    """

    discovered_urls = set()

    skip = 0

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=15.0,
        follow_redirects=True,
    ) as client:

        while True:

            paginated_url = build_paginated_url(
                base_search_url,
                search_params,
                skip,
            )

            print(
                f"🔍 Scanning TRREB results "
                f"(skip={skip})..."
            )

            try:

                response = await client.get(
                    paginated_url
                )

                response.raise_for_status()

            except Exception as e:

                print(
                    f"❌ Failed to scan "
                    f"skip={skip}: {e}"
                )

                break

            soup = bs4.BeautifulSoup(
                response.text,
                "html.parser",
            )

            page_urls = set()

            for a in soup.find_all(
                "a",
                href=True
            ):

                href = a["href"]

                if "/listings/TREB-" not in href:
                    continue

                full_url = (
                    f"{BASE_URL}{href}"
                    if not href.startswith("http")
                    else href
                )

                page_urls.add(full_url)

            if not page_urls:

                print(
                    f"📄 End of pagination "
                    f"at skip={skip}."
                )

                break

            before = len(discovered_urls)

            discovered_urls.update(page_urls)

            newly_found = (
                len(discovered_urls) - before
            )

            print(
                f"  ↳ Page listings: "
                f"{len(page_urls)}"
            )

            print(
                f"  ↳ New unique listings: "
                f"{newly_found}"
            )

            print(
                f"  ↳ Total discovered: "
                f"{len(discovered_urls)}"
            )

            skip += limit

    print(
        f"\n✅ Current TRREB snapshot: "
        f"{len(discovered_urls)} listings"
    )

    return discovered_urls


async def fetch_new_listings(
    urls: set[str],
    concurrency: int = 5
) -> pd.DataFrame:
    """
    Fetch listing details for a set of new URLs.

    Uses bounded concurrency so we don't create
    an unrestricted number of simultaneous requests.
    """

    if not urls:
        return pd.DataFrame()

    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=15.0,
        follow_redirects=True,
    ) as client:

        async def fetch_one(url):

            async with semaphore:

                return await fetch_listing_details(
                    client,
                    url,
                )

        tasks = [
            fetch_one(url)
            for url in urls
        ]

        results = await asyncio.gather(
            *tasks
        )

    clean_results = [
        result
        for result in results
        if result is not None
    ]

    return pd.DataFrame(clean_results)

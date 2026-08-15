import asyncio
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import bs4
import httpx
import pandas as pd

from config import BASE_SEARCH_URL, BASE_URL, HEADERS, SEARCH_PARAMS
from utils import clean_address_and_extract_unit


def build_paginated_url(base_url: str, params: dict, skip: int) -> str:
    """Builds the search URL while updating the $skip parameter."""
    current_params = params.copy()
    current_params["$skip"] = skip
    query_string = urlencode(current_params, doseq=True)
    return f"{base_url}?{query_string}"


async def fetch_listing_details(
    client: httpx.AsyncClient, listing_path: str
) -> dict | None:
    """Fetches details for a single listing."""
    url = (
        f"{BASE_URL}{listing_path}"
        if not listing_path.startswith("http")
        else listing_path
    )
    try:
        response = await client.get(url)
        soup = bs4.BeautifulSoup(response.text, "html.parser")

        addr_el = soup.select_one(".addr h1")
        raw_address = addr_el.get_text(strip=True) if addr_el else "N/A"
        clean_addr, unit_details = clean_address_and_extract_unit(raw_address)

        price_el = soup.select_one(".price h1 span")
        price = price_el.get_text(strip=True) if price_el else "N/A"

        sqft = "N/A"
        for td in soup.select(".short-details td, td"):
            if "SqFt" in td.get_text():
                small_tag = td.find("small")
                if small_tag:
                    sqft = small_tag.get_text(strip=True)
                break

        included_items = []
        included_span = soup.find(
            lambda tag: tag.name == "span"
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

        # Calculate the count based on scraped items list
        included_count = len(included_items)

        return {
            "Raw_Address": raw_address,
            "Address": clean_addr,
            "Unit_Details": unit_details,
            "Price": price,
            "SqFt": sqft,
            "Included": (
                ", ".join(included_items) if included_items else "None listed"
            ),
            "Included_Count": included_count,  # New column added here
            "URL": url,
        }

    except Exception as e:
        print(f"⚠️ Error scraping {url}: {e}")
        return None


async def scrape_trreb_search_page(
    base_search_url: str, search_params: dict, existing_urls: set, limit: int = 100
) -> pd.DataFrame:
    """Loops through paginated search results using $skip until no new links are found."""
    all_discovered_paths = []
    skip = 0

    async with httpx.AsyncClient(
        headers=HEADERS, timeout=15.0, follow_redirects=True
    ) as client:
        while True:
            paginated_url = build_paginated_url(
                base_search_url, search_params, skip
            )
            print(
                f"🔍 Fetching page results offset (skip={skip}): {paginated_url}"
            )

            response = await client.get(paginated_url)
            soup = bs4.BeautifulSoup(response.text, "html.parser")

            page_paths = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/listings/TREB-" in href and href not in page_paths:
                    page_paths.append(href)

            # Break loop if no listings found on this page
            if not page_paths:
                print(
                    f"📄 Reached end of pagination (No listings at skip={skip})."
                )
                break

            # Append only non-duplicate paths
            for path in page_paths:
                if path not in all_discovered_paths:
                    all_discovered_paths.append(path)

            print(
                f"  ↳ Found {len(page_paths)} listings on offset skip={skip}."
            )

            # Move to next page offset
            skip += limit

        # Filter out existing URLs already present in CSV state
        new_paths = []
        for path in all_discovered_paths:
            full_url = (
                f"{BASE_URL}{path}" if not path.startswith("http") else path
            )
            if full_url not in existing_urls:
                new_paths.append(path)

        print(
            f"\nℹ️ Total Unique Listings Found Across All Pages: {len(all_discovered_paths)}"
        )
        print(
            f"ℹ️ Already in dataset: {len(all_discovered_paths) - len(new_paths)}"
        )

        if not new_paths:
            print("✨ No new listings found. Everything is up to date!")
            return pd.DataFrame()

        print(
            f"🚀 Processing {len(new_paths)} NEW listings in parallel batch..."
        )
        tasks = [fetch_listing_details(client, path) for path in new_paths]
        results = await asyncio.gather(*tasks)

    clean_results = [r for r in results if r is not None]
    return pd.DataFrame(clean_results)
# Make sure to import HEADERS at the top of your script if it's in another file
# from config import HEADERS 
async def is_listing_active(client: httpx.AsyncClient, url: str) -> bool:
    """Checks if a listing URL is still active with soft fallback rules."""
    try:
        response = await client.get(url, headers=HEADERS, timeout=12.0)
        
        if response.status_code != 200:
            return False
            
        soup = bs4.BeautifulSoup(response.text, "html.parser")
        
        # FIX 1: Look for multiple possible clues that the page is a valid listing
        has_primary_clue = soup.select_one(".addr h1") is not None
        has_backup_clue = "listing" in response.text.lower() and "price" in response.text.lower()
        
        # If it has the main header OR looks like a valid property page, keep it!
        return has_primary_clue or has_backup_clue
        
    except Exception:
        return False

async def check_active_listings(urls: list[str]) -> set[str]:
    """Checks a list of URLs with a safer concurrency limit."""
    if not urls:
        return set()
        
    print(f"🔍 Checking active status for {len(urls)} saved listings...")
    
    # FIX 2: Drop connections down so TRREB doesn't freak out and serve blank pages
    limits = httpx.Limits(max_keepalive_connections=3, max_connections=5)
    
    async with httpx.AsyncClient(limits=limits, headers=HEADERS, follow_redirects=True) as client:
        tasks = [is_listing_active(client, url) for url in urls]
        results = await asyncio.gather(*tasks)
        
    active_urls = {url for url, is_active in zip(urls, results) if is_active}
    removed_count = len(urls) - len(active_urls)
    
    print(f"🧹 Status check complete: {len(active_urls)} active | {removed_count} inactive/removed.")
    return active_urls

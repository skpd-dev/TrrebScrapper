import asyncio
import os
import time
import nest_asyncio
import pandas as pd

from config import BASE_SEARCH_URL, CSV_FILENAME, DEST_LAT, DEST_LON, SEARCH_PARAMS
from scraper import check_active_listings, scrape_trreb_search_page
from transit import geocode_address, get_transit_info
from utils import load_existing_urls

nest_asyncio.apply()


async def main():
    existing_urls = load_existing_urls(CSV_FILENAME)
    print(f"📂 Loaded {len(existing_urls)} existing listing URLs from local state.")

    # === CLEANUP DEAD LISTINGS ===
    if existing_urls:
        active_urls = await check_active_listings(list(existing_urls))

        if len(active_urls) < len(existing_urls):
            print("💾 Updating CSV file to remove dead listings...")
            df_current = pd.read_csv(CSV_FILENAME)
            df_cleaned = df_current[df_current["URL"].isin(active_urls)]
            df_cleaned.to_csv(CSV_FILENAME, index=False)
            existing_urls = active_urls

    # === SCRAPE NEW LISTINGS ===
    df_new = await scrape_trreb_search_page(
        BASE_SEARCH_URL, SEARCH_PARAMS, existing_urls
    )

    if df_new.empty:
        print("✅ Finished. No new listings to process.")
        return

    print(f"\nStarting transit analysis on {len(df_new)} NEW listings...\n")

    # Accumulators for Min Transfers route metrics
    min_dur_list, min_trans_list, min_routes_list, min_freq_list = [], [], [], []
    # Accumulators for Shortest Duration route metrics
    short_dur_list, short_trans_list, short_routes_list, short_freq_list = [], [], [], []

    for idx, row in df_new.iterrows():
        address = row["Address"]
        print(
            f"Processing NEW ({idx + 1}/{len(df_new)}): Cleaned='{address}' | Unit='{row['Unit_Details']}'"
        )

        lat, lon = geocode_address(address)
        if lat and lon:
            # Unpack the updated 8-tuple from transit.py
            (
                m_dur,
                m_trans,
                m_routes,
                m_freq,
                s_dur,
                s_trans,
                s_routes,
                s_freq,
            ) = get_transit_info(lat, lon, DEST_LAT, DEST_LON)

            min_dur_list.append(m_dur)
            min_trans_list.append(m_trans)
            min_routes_list.append(m_routes)
            min_freq_list.append(m_freq)

            short_dur_list.append(s_dur)
            short_trans_list.append(s_trans)
            short_routes_list.append(s_routes)
            short_freq_list.append(s_freq)
        else:
            min_dur_list.append("Geocode Fail")
            min_trans_list.append("N/A")
            min_routes_list.append("N/A")
            min_freq_list.append("N/A")

            short_dur_list.append("Geocode Fail")
            short_trans_list.append("N/A")
            short_routes_list.append("N/A")
            short_freq_list.append("N/A")

        time.sleep(1)

    # Assign transit metrics to dataframe columns
    df_new["MinTransfers_Duration"] = min_dur_list
    df_new["MinTransfers_Count"] = min_trans_list
    df_new["MinTransfers_Routes"] = min_routes_list
    df_new["MinTransfers_Frequency"] = min_freq_list

    df_new["Shortest_Duration"] = short_dur_list
    df_new["Shortest_Transfers"] = short_trans_list
    df_new["Shortest_Routes"] = short_routes_list
    df_new["Shortest_Frequency"] = short_freq_list

    # === SAVE RESULTS ===
    if os.path.exists(CSV_FILENAME):
        df_new.to_csv(CSV_FILENAME, mode="a", header=False, index=False)
        print(f"\n✅ Appended {len(df_new)} new listings to '{CSV_FILENAME}'!")
    else:
        df_new.to_csv(CSV_FILENAME, index=False)
        print(f"\n✅ Created '{CSV_FILENAME}' with {len(df_new)} listings!")


if __name__ == "__main__":
    asyncio.run(main())
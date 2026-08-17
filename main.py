
import asyncio
import os
from datetime import datetime

import nest_asyncio
import pandas as pd

from config import (
    BASE_SEARCH_URL,
    CSV_FILENAME,
    DEST_LAT,
    DEST_LON,
    SEARCH_PARAMS,
)

from scraper import (
    discover_all_listing_urls,
    fetch_new_listings,
)

from transit import (
    geocode_address,
    get_transit_info,
)


nest_asyncio.apply()


# ============================================================
# FILES
# ============================================================

EXCEL_FILENAME = "trreb_listings.xlsx"

LIVE_SHEET = "Live"
LOST_SHEET = "Lost"


# ============================================================
# LOAD EXISTING DATA
# ============================================================

def load_existing_excel():
    """
    Load the previous Live and Lost sheets.

    Returns:
        live_df
        lost_df
    """

    if not os.path.exists(EXCEL_FILENAME):

        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )

    try:

        excel_file = pd.ExcelFile(
            EXCEL_FILENAME
        )

        live_df = (
            pd.read_excel(
                EXCEL_FILENAME,
                sheet_name=LIVE_SHEET,
            )
            if LIVE_SHEET in excel_file.sheet_names
            else pd.DataFrame()
        )

        lost_df = (
            pd.read_excel(
                EXCEL_FILENAME,
                sheet_name=LOST_SHEET,
            )
            if LOST_SHEET in excel_file.sheet_names
            else pd.DataFrame()
        )

        return live_df, lost_df

    except Exception as e:

        print(
            f"⚠️ Could not load existing Excel: {e}"
        )

        return (
            pd.DataFrame(),
            pd.DataFrame(),
        )


# ============================================================
# TRANSIT ENRICHMENT
# ============================================================

def enrich_transit(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add geocoding and transit information
    to newly discovered listings.
    """

    if df.empty:
        return df

    min_dur_list = []
    min_trans_list = []
    min_routes_list = []
    min_freq_list = []

    short_dur_list = []
    short_trans_list = []
    short_routes_list = []
    short_freq_list = []

    total = len(df)

    for idx, row in df.iterrows():

        address = row["Address"]

        print(
            f"\n🚇 Transit "
            f"{idx + 1}/{total}: "
            f"{address}"
        )

        try:

            lat, lon = geocode_address(
                address
            )

            if lat is not None and lon is not None:

                (
                    m_dur,
                    m_trans,
                    m_routes,
                    m_freq,
                    s_dur,
                    s_trans,
                    s_routes,
                    s_freq,
                ) = get_transit_info(
                    lat,
                    lon,
                    DEST_LAT,
                    DEST_LON,
                )

                min_dur_list.append(m_dur)
                min_trans_list.append(m_trans)
                min_routes_list.append(m_routes)
                min_freq_list.append(m_freq)

                short_dur_list.append(s_dur)
                short_trans_list.append(s_trans)
                short_routes_list.append(s_routes)
                short_freq_list.append(s_freq)

            else:

                print(
                    "⚠️ Geocoding failed."
                )

                min_dur_list.append(
                    "Geocode Fail"
                )
                min_trans_list.append("N/A")
                min_routes_list.append("N/A")
                min_freq_list.append("N/A")

                short_dur_list.append(
                    "Geocode Fail"
                )
                short_trans_list.append("N/A")
                short_routes_list.append("N/A")
                short_freq_list.append("N/A")

        except Exception as e:

            print(
                f"⚠️ Transit error: {e}"
            )

            min_dur_list.append("Transit Fail")
            min_trans_list.append("N/A")
            min_routes_list.append("N/A")
            min_freq_list.append("N/A")

            short_dur_list.append("Transit Fail")
            short_trans_list.append("N/A")
            short_routes_list.append("N/A")
            short_freq_list.append("N/A")

    df["MinTransfers_Duration"] = min_dur_list
    df["MinTransfers_Count"] = min_trans_list
    df["MinTransfers_Routes"] = min_routes_list
    df["MinTransfers_Frequency"] = min_freq_list

    df["Shortest_Duration"] = short_dur_list
    df["Shortest_Transfers"] = short_trans_list
    df["Shortest_Routes"] = short_routes_list
    df["Shortest_Frequency"] = short_freq_list

    return df


# ============================================================
# EXCEL OUTPUT
# ============================================================

def save_excel(
    live_df: pd.DataFrame,
    lost_df: pd.DataFrame,
):
    """
    Write the complete current state to Excel.

    Sheet 1:
        Live

    Sheet 2:
        Lost
    """

    with pd.ExcelWriter(
        EXCEL_FILENAME,
        engine="openpyxl",
    ) as writer:

        live_df.to_excel(
            writer,
            sheet_name=LIVE_SHEET,
            index=False,
        )

        lost_df.to_excel(
            writer,
            sheet_name=LOST_SHEET,
            index=False,
        )

    print(
        f"\n💾 Saved Excel workbook: "
        f"{EXCEL_FILENAME}"
    )

    print(
        f"   Live: {len(live_df)}"
    )

    print(
        f"   Lost: {len(lost_df)}"
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

async def main():

    print(
        "\n"
        "==================================================\n"
        "TRREB INCREMENTAL LISTING PIPELINE\n"
        "==================================================\n"
    )

    # --------------------------------------------------------
    # 1. LOAD PREVIOUS STATE
    # --------------------------------------------------------

    live_old, lost_old = load_existing_excel()

    print(
        f"📂 Previous Live: "
        f"{len(live_old)}"
    )

    print(
        f"📂 Previous Lost: "
        f"{len(lost_old)}"
    )

    old_live_urls = set()

    if (
        not live_old.empty
        and "URL" in live_old.columns
    ):

        old_live_urls = set(
            live_old["URL"]
            .dropna()
            .astype(str)
        )

    # --------------------------------------------------------
    # 2. DISCOVER CURRENT WEBSITE SNAPSHOT
    # --------------------------------------------------------

    current_urls = (
        await discover_all_listing_urls(
            BASE_SEARCH_URL,
            SEARCH_PARAMS,
        )
    )

    print(
        f"\n🌐 Current website listings: "
        f"{len(current_urls)}"
    )

    # --------------------------------------------------------
    # 3. FIND NEW LISTINGS
    # --------------------------------------------------------

    new_urls = (
        current_urls
        - old_live_urls
    )

    print(
        f"🆕 New listings: "
        f"{len(new_urls)}"
    )

    # --------------------------------------------------------
    # 4. FIND LOST LISTINGS
    # --------------------------------------------------------

    lost_urls = (
        old_live_urls
        - current_urls
    )

    print(
        f"❌ Listings no longer found: "
        f"{len(lost_urls)}"
    )

    # --------------------------------------------------------
    # 5. FETCH NEW LISTING DETAILS
    # --------------------------------------------------------

    if new_urls:

        print(
            f"\n🚀 Fetching "
            f"{len(new_urls)} new listings..."
        )

        new_df = await fetch_new_listings(
            new_urls,
            concurrency=5,
        )

        # Add discovery timestamp
        new_df["First_Seen"] = (
            datetime.now()
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        # Transit enrichment
        print(
            "\n🚇 Starting transit enrichment..."
        )

        new_df = enrich_transit(
            new_df
        )

    else:

        new_df = pd.DataFrame()

        print(
            "\n✨ No new listings."
        )

    # --------------------------------------------------------
    # 6. BUILD CURRENT LIVE DATASET
    # --------------------------------------------------------

    # Existing listings that are still live
    if not live_old.empty:

        live_existing = live_old[
            live_old["URL"].isin(
                current_urls
            )
        ].copy()

    else:

        live_existing = pd.DataFrame()

    # Add new listings
    if not new_df.empty:

        live_df = pd.concat(
            [
                live_existing,
                new_df,
            ],
            ignore_index=True,
        )

    else:

        live_df = live_existing.copy()

    # Remove duplicate URLs just in case
    if (
        not live_df.empty
        and "URL" in live_df.columns
    ):

        live_df = (
            live_df
            .drop_duplicates(
                subset=["URL"],
                keep="last",
            )
        )

    # --------------------------------------------------------
    # 7. BUILD LOST DATASET
    # --------------------------------------------------------

    lost_new = pd.DataFrame()

    if lost_urls and not live_old.empty:

        lost_new = live_old[
            live_old["URL"].isin(
                lost_urls
            )
        ].copy()

        lost_new["Lost_Date"] = (
            datetime.now()
            .strftime("%Y-%m-%d %H:%M:%S")
        )

        lost_new["Status"] = (
            "No longer found in current TRREB search"
        )

    # --------------------------------------------------------
    # 8. MERGE WITH PREVIOUS LOST HISTORY
    # --------------------------------------------------------

    if not lost_old.empty:

        lost_df = pd.concat(
            [
                lost_old,
                lost_new,
            ],
            ignore_index=True,
        )

    else:

        lost_df = lost_new.copy()

    # --------------------------------------------------------
    # 9. IF A LOST LISTING REAPPEARS,
    #    REMOVE IT FROM LOST
    # --------------------------------------------------------

    if (
        not lost_df.empty
        and "URL" in lost_df.columns
    ):

        lost_df = lost_df[
            ~lost_df["URL"].isin(
                current_urls
            )
        ].copy()

    # Remove duplicates
    if (
        not lost_df.empty
        and "URL" in lost_df.columns
    ):

        lost_df = (
            lost_df
            .drop_duplicates(
                subset=["URL"],
                keep="last",
            )
        )

    # --------------------------------------------------------
    # 10. SAVE EXCEL
    # --------------------------------------------------------

    save_excel(
        live_df,
        lost_df,
    )

    # --------------------------------------------------------
    # 11. OPTIONAL CSV OUTPUT
    # --------------------------------------------------------

    if not live_df.empty:

        live_df.to_csv(
            CSV_FILENAME,
            index=False,
        )

        print(
            f"📄 Updated live CSV: "
            f"{CSV_FILENAME}"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print(
        "\n"
        "==================================================\n"
        "RUN SUMMARY\n"
        "=================================================="
    )

    print(
        f"🌐 Website snapshot : "
        f"{len(current_urls)}"
    )

    print(
        f"🟢 Live              : "
        f"{len(live_df)}"
    )

    print(
        f"🆕 New               : "
        f"{len(new_df)}"
    )

    print(
        f"🔴 Lost              : "
        f"{len(lost_new)}"
    )

    print(
        f"📚 Lost history      : "
        f"{len(lost_df)}"
    )

    print(
        "\n✅ Pipeline complete."
    )


if __name__ == "__main__":

    asyncio.run(main())
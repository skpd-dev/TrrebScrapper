import os
import re
import pandas as pd


def load_existing_urls(filepath: str) -> set:
    """Loads existing URLs from CSV into a set for O(1) lookups."""
    if os.path.exists(filepath):
        try:
            df = pd.read_csv(filepath)
            if "URL" in df.columns:
                return set(df["URL"].dropna().unique())
        except Exception as e:
            print(f"⚠️ Warning loading existing CSV: {e}")
    return set()


def clean_address_and_extract_unit(raw_address: str) -> tuple[str, str]:
    """Cleans a raw TRREB street address and extracts unit numbers."""
    if not raw_address or raw_address == "N/A":
        return "N/A", "N/A"

    working_addr = raw_address.strip()
    street_abbrev_map = {
        r"\bGdns\b": "Gardens",
        r"\bGdn\b": "Gardens",
        r"\bCrt\b": "Court",
        r"\bTerr\b": "Terrace",
        r"\bBsmnt\b": "Basement",
        r"\bBsmt\b": "Basement",
    }

    unit_found = []
    explicit_unit_pattern = re.compile(
        r"(?i)(?:-?\s*)?\b(?:Basement(?:\s+Apartment)?|Main\s+Flr(?:\s*&\s*Bsmt)?|[1-3](?:st|nd|rd|th)?\s+Fl(?:oor)?|Apt(?:\s*[\w\d-]+)?|Unit(?:\s*[\w\d-]+)?|Suite(?:\s*[\w\d-]+)?|Ste(?:\s*[\w\d-]+)?|Lower|Upper|Bsmt|Bsmnt)\b"
    )

    matches = explicit_unit_pattern.findall(working_addr)
    if matches:
        for m in matches:
            cleaned_m = m.strip(" -")
            if cleaned_m:
                unit_found.append(cleaned_m)
        working_addr = explicit_unit_pattern.sub("", working_addr)

    trailing_unit_pattern = re.compile(
        r"(?i)^(\d+\s+[A-Za-z0-9\s.]+?\b(?:Rd|St|Ave|Blvd|Dr|Crt|Court|Cres|Gdns|Gardens|Sq|Pl|Terr|Terrace|Way|Line|Pkwy))\s+([A-Z0-9]+|\b[E|W]\s+\d+)\s*(?:,\s*Toronto.*)?$"
    )

    match = trailing_unit_pattern.match(working_addr)
    if match:
        base_street = match.group(1).strip()
        extracted_unit = match.group(2).strip()
        if extracted_unit not in unit_found:
            unit_found.append(extracted_unit)
        working_addr = base_street + ", Toronto"

    working_addr = re.sub(r"\s+", " ", working_addr)
    working_addr = re.sub(r"\s*,\s*", ", ", working_addr)
    working_addr = re.sub(r",\s*,", ",", working_addr)

    for abbrev, full_word in street_abbrev_map.items():
        working_addr = re.sub(
            abbrev, full_word, working_addr, flags=re.IGNORECASE
        )

    if "Toronto" in working_addr:
        working_addr = re.sub(r" Toronto.*", "", working_addr).strip(" ,")

    cleaned_address = f"{working_addr}, Toronto, ON"
    unit_str = ", ".join(unit_found) if unit_found else "N/A"

    return cleaned_address, unit_str
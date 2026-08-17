import re


# ============================================================
# ADDRESS CLEANING / UNIT EXTRACTION
# ============================================================

def clean_address_and_extract_unit(raw_address: str):
    """
    Clean a TRREB address for geocoding while preserving
    unit/floor information separately.

    Returns:
        clean_address
        unit_details
    """

    if not raw_address:
        return "", ""

    original = raw_address.strip()

    # Normalize whitespace
    address = re.sub(
        r"\s+",
        " ",
        original
    ).strip()

    unit_parts = []

    # ========================================================
    # PARENTHESIZED INFORMATION
    #
    # Examples:
    #   (2nd bedroom)
    #   (3rd bedroom)
    #   (main floor)
    # ========================================================

    parenthetical = re.findall(
        r"\([^)]*\)",
        address,
        flags=re.IGNORECASE,
    )

    for item in parenthetical:

        unit_parts.append(
            item.strip()
        )

    address = re.sub(
        r"\([^)]*\)",
        " ",
        address,
    )

    # ========================================================
    # FLOOR / UNIT PATTERNS
    # ========================================================

    patterns = [

        # ----------------------------------------------------
        # Numeric floors
        # ----------------------------------------------------

        r"\b\d+(?:st|nd|rd|th)\s+floor\b",
        r"\b\d+(?:st|nd|rd|th)\s+fl\b",

        # Examples:
        # 2F
        # 3F
        # 10F
        r"\b\d+F\b",

        # ----------------------------------------------------
        # Named floors
        # ----------------------------------------------------

        r"\bmain\s+floor\b",
        r"\bmain\s+fl\b",
        r"\bupper\s+floor\b",
        r"\blower\s+floor\b",
        r"\bupper\b",
        r"\blower\b",

        # ----------------------------------------------------
        # Garden / basement variants
        # ----------------------------------------------------

        r"\bgdns?\s+upper\b",
        r"\bgdns?\s+lower\b",
        r"\bgardens?\s+upper\b",
        r"\bgardens?\s+lower\b",

        r"\bbsmnt\b",
        r"\bbsmt\b",
        r"\bbasement\b",

        # ----------------------------------------------------
        # Unit / apartment identifiers
        # ----------------------------------------------------

        r"\bunit\s*#?\s*[A-Za-z0-9-]+\b",
        r"\bapt\.?\s*#?\s*[A-Za-z0-9-]+\b",

        # #123
        r"#\s*[A-Za-z0-9-]+",

        # ----------------------------------------------------
        # Bedroom annotations
        # ----------------------------------------------------

        r"\b\d+(?:st|nd|rd|th)\s+bedroom\b",

        # bedroom 2
        r"\bbedroom\s+\d+\b",
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            address,
            flags=re.IGNORECASE,
        )

        for match in matches:

            unit_parts.append(
                match.strip()
            )

        address = re.sub(
            pattern,
            " ",
            address,
            flags=re.IGNORECASE,
        )

    # ========================================================
    # TRREB ABBREVIATIONS
    # ========================================================

    replacements = {

        r"\bGdns\b": "Gardens",
        r"\bGdn\b": "Garden",

        r"\bCrt\b": "Court",
        r"\bCt\b": "Court",

        r"\bTerr\b": "Terrace",
        r"\bTer\b": "Terrace",

        r"\bAve\b": "Avenue",
        r"\bAv\b": "Avenue",

        r"\bRd\b": "Road",

        r"\bSt\b": "Street",

        r"\bDr\b": "Drive",

        r"\bBlvd\b": "Boulevard",

        r"\bCres\b": "Crescent",

        r"\bLn\b": "Lane",

        r"\bPl\b": "Place",

        r"\bPky\b": "Parkway",

        r"\bHwy\b": "Highway",

    }

    for pattern, replacement in replacements.items():

        address = re.sub(
            pattern,
            replacement,
            address,
            flags=re.IGNORECASE,
        )

    # ========================================================
    # CLEAN UP WHITESPACE / PUNCTUATION
    # ========================================================

    address = re.sub(
        r"\s+",
        " ",
        address,
    ).strip()

    address = re.sub(
        r"\s+,",
        ",",
        address,
    )

    address = re.sub(
        r",\s*,+",
        ",",
        address,
    )

    # ========================================================
    # UNIT DETAILS
    # ========================================================

    # Remove duplicates while preserving order
    seen = set()
    clean_units = []

    for item in unit_parts:

        normalized = item.strip()

        key = normalized.lower()

        if (
            normalized
            and key not in seen
        ):

            seen.add(key)

            clean_units.append(
                normalized
            )

    unit_details = ", ".join(
        clean_units
    )

    return (
        address,
        unit_details,
    )
"""
Known Turkish hospitality equipment brands.

Used for product matching and categorization.
"""

# Major international brands available in Turkish market
INTERNATIONAL_BRANDS = {
    "Bosch",
    "Siemens",
    "Electrolux",
    "Whirlpool",
    "Samsung",
    "LG",
    "Beko",
    "Arçelik",
    "Arcelik",
    "Miele",
    "Fagor",
    "Dito",
    "Sanyo",
    "Brema",
    "Perry",
    "Hicold",
    "Giox",
    "Makt",
    "Vestel",
    "Altus",
    "Regal",
    "Simfer",
    "Karcher",
    "Kärcher",
    "Robot",
    "Coupe",
    "Rational",
    "Comenda",
    "Winterhalter",
    "Meiko",
    "Indesit",
    "Hotpoint",
    "Candy",
    "Hoover",
    "Smeg",
    "Gorenje",
    "Bertazzoni",
    "Fisher",
    "Paykel",
    "Neff",
    "AEG",
    "Zanussi",
    "Indesit",
    "Bauknecht",
    "Lacanche",
    "Falcon",
    "Moffat",
    "Convotherm",
    "Eloma",
    "Sousvide",
    "Polycook",
    "Abat",
    "Retigo",
    "Unox",
    "Schaerer",
    "Franke",
    "Brema",
    "Scotsman",
    "Hoshizaki",
    "Manitowoc",
    "Ice-O-Matic",
    "Cornelius",
    "Kulinariska",
    "Lainox",
    "Admiral",
    "Zanussi",
    "Gram",
    "Fosters",
    "Foster",
    "Williams",
    "True",
    "Frigor",
    "Hicold",
    "Irinox",
    "Brema",
    "Carpigiani",
    "Nemox",
    "Gelato",
    "Taylor",
    "Witt",
    "Bunn",
    "Grindmaster",
    "Hario",
    "Chemex",
    "Aeropress",
    "Jura",
    "Saeco",
    "DeLonghi",
    "Gaggia",
    "La Marzocco",
    "Nuova Simonelli",
    "Rancilio",
    "Expobar",
    "Bezzera",
    "Astoria",
    "Victoria Arduino",
    "Rocket",
    "Profitec",
    "ECM",
    "Quick Mill",
    "Ascaso",
    "Solis",
    "Melitta",
    "Moccamaster",
    "Bodum",
    "Krups",
    "Kenwood",
    "KitchenAid",
    "Hamilton Beach",
    "Waring",
    "Vitamix",
    "Blendtec",
    "Robot Coupe",
    "Dynamic",
    "Hallde",
    "Santos",
    "Fimaco",
    "Anvil",
    "Parry",
    "Lincat",
    "Buffalo",
    "Winterhalter",
    "Meiko",
    "Hobart",
    "Miele",
    "Winterhalter",
    "Rational",
    "Comenda",
    "Smeg",
    "Mareno",
    "Williams",
    "Admiral",
    "Frimair",
    "Foster",
    "Gram",
    "True",
    "Hicold",
    "Irinox",
    "Abat",
    "Retigo",
    "Unox",
    "Convotherm",
    "Eloma",
    "Roller Grill",
    "Schaerer",
    "Franke",
    "Brema",
    "Scotsman",
    "Hoshizaki",
    "Manitowoc",
    "Ice-O-Matic",
    "Cornelius",
}

# Turkish domestic brands
TURKISH_BRANDS = {
    "Öztiryakiler",
    "Oztiryakiler",
    "Özdilek",
    "Ozdilek",
    "Kutlutaş",
    "Kutlutas",
    "Gören",
    "Goren",
    "Fakir",
    "Arnika",
    "Rowenta",
    "Tefal",
    "Arzum",
    "Braun",
    "Remington",
    "Babyliss",
    "Sinbo",
    "Felix",
    "Kumtel",
    "Servis",
    "Regal",
    "Altus",
    "Vestel",
    "Beko",
    "Arçelik",
    "Arcelik",
    "Beykent",
    "Elica",
    "Franke",
    "Artema",
    "Grohe",
    "Hansgrohe",
    "Vitra",
    "Eczacıbaşı",
    "Bemis",
    "Pera",
    "Serel",
    "Kutahya",
    "Kutahya Seramik",
    "Canakkale",
    "Çanakkale",
    "Kalesinterflex",
    "Ege",
    "Yurtbay",
    "Kutahya",
    "Pehlivan",
    "Alpemix",
    "İberon",
    "Iberon",
    "Ferrol",
    "Vaillant",
    "Demirdöküm",
    "Eca",
    "Protherm",
    "Viessmann",
    "Buderus",
    "Wolf",
    "Airfel",
    "Termoteknik",
    "Auer",
    "Immergas",
    "Baymak",
    "Ferroli",
}

# Commercial kitchen equipment brands
KITCHEN_EQUIPMENT_BRANDS = {
    "Öztiryakiler",
    "Oztiryakiler",
    "Kutlutaş",
    "Kutlutas",
    "Makt",
    "Robot Coupe",
    "Winterhalter",
    "Meiko",
    "Rational",
    "Comenda",
    "Hobart",
    "Eloma",
    "Convotherm",
    "Unox",
    "Retigo",
    "Abat",
    "Lainox",
    "Foinox",
    "Mareno",
    "Olis",
    "Inoks",
    "Tekno",
    "Endustri",
    "Endüstri",
    "Profi",
    "Heavy Duty",
    "Light Duty",
    "Grand Chef",
    "Master",
    "Chef",
    "King",
    "Queen",
    "Royal",
    "Premium",
    "Standard",
    "Economy",
}

# Coffee equipment brands
COFFEE_BRANDS = {
    "La Marzocco",
    "Nuova Simonelli",
    "Rancilio",
    "Expobar",
    "Bezzera",
    "Astoria",
    "Victoria Arduino",
    "Rocket",
    "Profitec",
    "ECM",
    "Quick Mill",
    "Ascaso",
    "Solis",
    "Jura",
    "Saeco",
    "DeLonghi",
    "Gaggia",
    "Bunn",
    "Grindmaster",
    "Hario",
    "Chemex",
    "Aeropress",
    "Mazzer",
    "Compak",
    "Mahlkönig",
    "Ditting",
    "Anfim",
    "Fiorenzato",
    "Macap",
    "Santos",
    "Cunill",
    "Astoria",
    "Wega",
    " Elektra",
    "Faema",
    "Cimbali",
    "Spazio",
    "Rancilio",
    "Synchro",
    "Victoria Arduino",
}

# Refrigeration brands
REFRIGERATION_BRANDS = {
    "Foster",
    "Fosters",
    "Williams",
    "True",
    "Frigor",
    "Hicold",
    "Irinox",
    "Gram",
    "Admiral",
    "Frimair",
    "Scotsman",
    "Brema",
    "Hoshizaki",
    "Manitowoc",
    "Ice-O-Matic",
    "Cornelius",
}

# Combined all brands for easy lookup
ALL_BRANDS = INTERNATIONAL_BRANDS | TURKISH_BRANDS | KITCHEN_EQUIPMENT_BRANDS | COFFEE_BRANDS | REFRIGERATION_BRANDS

# Brand aliases for fuzzy matching
# Some sites use different names for the same brand
BRAND_ALIASES = {
    "ozer": "Öztiryakiler",
    "ozti": "Öztiryakiler",
    "oztiri": "Öztiryakiler",
    "arc": "Arçelik",
    "arcelik": "Arçelik",
    "agv": "Arçelik",
    "reg": "Regal",
    "vest": "Vestel",
    "alt": "Altus",
    "bek": "Beko",
    "fak": "Fakir",
    "arn": "Arnika",
    "row": "Rowenta",
    "tef": "Tefal",
    "arz": "Arzum",
    "sin": "Sinbo",
    "kum": "Kumtel",
}

# Common brand name prefixes in product titles
BRAND_PREFIXES = [
    "Endüstriyel",
    "Endustriyel",
    "Endustri",
    "Industrial",
    "Profesyonel",
    "Professional",
    "Ticari",
    "Commercial",
]

# Brand variations to normalize
BRAND_NORMALIZATION = {
    "oztiryakiler": "Öztiryakiler",
    "ozti": "Öztiryakiler",
    "ozer": "Öztiryakiler",
    "arc": "Arçelik",
    "arcelik": "Arçelik",
    "agv": "Arçelik",
    "vest": "Vestel",
    "altus": "Altus",
    "beko": "Beko",
    "fakir": "Fakir",
    "arnika": "Arnika",
    "rowenta": "Rowenta",
    "tefal": "Tefal",
    "arzum": "Arzum",
    "sinbo": "Sinbo",
    "kumtel": "Kumtel",
    "goren": "Gören",
    "gorenje": "Gorenje",
    "fakir": "Fakir",
    "kutlutas": "Kutlutaş",
    "ozdilek": "Özdilek",
    "karcher": "Kärcher",
}


def get_brand_variants(brand: str) -> set:
    """Get all known variants of a brand name.

    Args:
        brand: Brand name to get variants for

    Returns:
        Set of brand name variants
    """
    variants = {brand.lower()}
    for alias, canonical in BRAND_ALIASES.items():
        if canonical.lower() == brand.lower():
            variants.add(alias)
    return variants


def normalize_brand(brand: str) -> str | None:
    """Normalize brand name to canonical form.

    Args:
        brand: Raw brand name

    Returns:
        Canonical brand name or None if not recognized
    """
    if not brand:
        return None

    normalized = brand.strip().lower()

    # Check normalization map
    if normalized in BRAND_NORMALIZATION:
        return BRAND_NORMALIZATION[normalized]

    # Check exact match in all brands
    for known_brand in ALL_BRANDS:
        if known_brand.lower() == normalized:
            return known_brand

    # Try fuzzy match for very close matches
    from thefuzz import fuzz

    for known_brand in ALL_BRANDS:
        if fuzz.ratio(normalized, known_brand.lower()) >= 90:
            return known_brand

    return None


def is_brand(word: str) -> bool:
    """Check if a word is a known brand.

    Args:
        word: Word to check

    Returns:
        True if word matches a known brand
    """
    if not word:
        return False

    word_lower = word.lower()

    # Direct match
    if word_lower in {b.lower() for b in ALL_BRANDS}:
        return True

    # Check normalization map
    if word_lower in BRAND_NORMALIZATION:
        return True

    return False

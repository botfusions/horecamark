"""
Text normalizer for HorecaMark product names.

Handles:
- Turkish stop word removal
- Special character cleaning
- Brand extraction
- Lowercase normalization
"""

import re
from typing import Optional

# Import comprehensive brand list
try:
    from .brand_list import normalize_brand, is_brand
    _HAS_BRAND_LIST = True
except ImportError:
    _HAS_BRAND_LIST = False


# Turkish stop words common in industrial/commercial product names
TURKISH_STOP_WORDS = {
    "endustriyel",
    "endüstriyel",
    "profesyonel",
    "ticari",
    "adet",
    "ad.",
    "adet ",
    "piece",
    "pc",
    "professional",
    "industrial",
    "commercial",
    "sanayi",
    "urun",
    "urun",
    "product",
    "oem",
    "original",
    "oryjinal",
    "genuine",
}

# Common brand patterns in Turkish hospitality equipment (legacy, kept for compatibility)
# Note: For comprehensive brand matching, use brand_list.normalize_brand()
BRAND_PATTERNS = [
    r"\b(?:Bosch|Siemens|Electrolux|Whirlpool|Samsung|LG|Beko|Arçelik|Arcelik)\b",
    r"\b(?:Fagor|Miele|Dito|Sanyo|Brema|Perry|Hicold|Giox|Makt)\b",
    r"\b(?:Vestel|Altus|Regal|Simfer|Karcher|Karcher|Kärcher)\b",
    r"\b(?:Robot|Coupe|Rational|Comenda|Winterhalter|Meiko)\b",
    r"\b(?:Ali|Oztiryakilar|Oztiryakiler|Ozdilek|Kutlutas|Goren)\b",
]


def normalize(name: str) -> str:
    """Normalize product name for matching.

    Removes:
    - Turkish stop words (endustriyel, profesyonel, etc.)
    - Special characters
    - Extra whitespace

    Preserves:
    - Numbers (capacity, dimensions)
    - Core product identifiers

    Args:
        name: Raw product name

    Returns:
        Normalized lowercase string
    """
    if not name:
        return ""

    # Convert to lowercase
    normalized = name.lower().strip()

    # Remove Turkish stop words
    for stop_word in TURKISH_STOP_WORDS:
        pattern = r"\b" + re.escape(stop_word) + r"\b"
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE)

    # Remove special characters but keep numbers and spaces
    # Keep: letters, numbers, spaces, hyphens, slashes (common in model names)
    normalized = re.sub(r"[^a-z0-9\s\-\/]", " ", normalized)

    # Normalize whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Remove trailing/leading hyphens and slashes
    normalized = normalized.strip(" -/")

    return normalized


def extract_brand(name: str) -> Optional[str]:
    """Extract brand name from product name.

    Args:
        name: Product name

    Returns:
        Brand name if found, None otherwise
    """
    if not name:
        return None

    # Use comprehensive brand list if available
    if _HAS_BRAND_LIST:
        result = normalize_brand(name.split()[0] if name.split() else "")
        if result:
            return result

    # Try known brand patterns (legacy)
    for pattern in BRAND_PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(0).capitalize()

    # Try to extract first word if it looks like a brand
    # (capitalized, at start, not a common word)
    first_word = name.split()[0] if name.split() else ""
    if first_word and first_word[0].isupper():
        return first_word.capitalize()

    return None


def extract_capacity(name: str) -> Optional[str]:
    """Extract capacity information from product name.

    Args:
        name: Product name

    Returns:
        Capacity string if found (e.g., "10kg", "500ml")
    """
    if not name:
        return None

    # Match patterns like "10kg", "500 ml", "2lt", "1000cc"
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(kg|ltr|lt|liter|ml|gr|gram|cc|cm|m)",
        r"(\d+(?:\.\d+)?)\s*(?:x)?(\d+(?:\.\d+)?)\s*(cm|m)",
    ]

    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(0).lower()

    return None


def clean_price(price_str: str) -> Optional[float]:
    """Extract numeric price from string.

    Handles:
    - Currency symbols (TL, TRY, $, etc.)
    - Thousand separators (.,)
    - Decimal separators

    Args:
        price_str: Raw price string

    Returns:
        Price as float, or None if parsing fails
    """
    if not price_str:
        return None

    # Remove currency symbols and whitespace
    cleaned = re.sub(r"[^\d.,\-]", "", price_str.strip())

    if not cleaned:
        return None

    # Handle Turkish format: 1.234,56 -> 1234.56
    if "," in cleaned and "." in cleaned:
        # Assume thousand separator is . and decimal is ,
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        # Check if it's decimal or thousand separator
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Decimal separator
            cleaned = cleaned.replace(",", ".")
        else:
            # Thousand separator
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        parts = cleaned.split(".")
        # If multiple dots, last one is decimal
        if len(parts) > 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]

    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_category(name: str) -> Optional[str]:
    """Extract product category from name keywords.

    Args:
        name: Product name

    Returns:
        Category string if detected
    """
    if not name:
        return None

    name_lower = name.lower()

    category_keywords = {
        "bulaşık makinesi": "dishwasher",
        "bulasik makinesi": "dishwasher",
        "dishwasher": "dishwasher",
        "fırın": "oven",
        "firin": "oven",
        "oven": "oven",
        "buzdolabı": "refrigerator",
        "buzdolabi": "refrigerator",
        "dolap": "refrigerator",
        "refrigerator": "refrigerator",
        "kombi": "combi",
        "combi": "combi",
        "mikrodalga": "microwave",
        "microwave": "microwave",
        "kettle": "kettle",
        "su ısıtıcı": "kettle",
        "blender": "blender",
        "mutfak robotu": "food_processor",
        "food processor": "food_processor",
        "süpürge": "vacuum",
        "supurge": "vacuum",
        "vacuum": "vacuum",
        "çay makinesi": "tea_maker",
        "cay makinesi": "tea_maker",
        "kahve makinesi": "coffee_maker",
        "espresso": "coffee_maker",
    }

    for keyword, category in category_keywords.items():
        if keyword in name_lower:
            return category

    return None


def normalize_stock_status(status: str) -> str:
    """Normalize stock status string.

    Args:
        status: Raw stock status string

    Returns:
        Normalized status: "in_stock", "out_of_stock", "pre_order", "unknown"
    """
    if not status:
        return "unknown"

    status_lower = status.lower().strip()

    in_stock_keywords = {
        "stokta var",
        "stokta",
        "haftelik",
        "hazır",
        "in stock",
        "available",
        "mevcut",
    }

    out_of_stock_keywords = {
        "stokta yok",
        "tükendi",
        "stok dışı",
        "yok",
        "out of stock",
        "unavailable",
    }

    pre_order_keywords = {
        "ön sipariş",
        "ön siparis",
        "yakında",
        "coming soon",
        "pre-order",
    }

    for keyword in in_stock_keywords:
        if keyword in status_lower:
            return "in_stock"

    for keyword in out_of_stock_keywords:
        if keyword in status_lower:
            return "out_of_stock"

    for keyword in pre_order_keywords:
        if keyword in status_lower:
            return "pre_order"

    return "unknown"

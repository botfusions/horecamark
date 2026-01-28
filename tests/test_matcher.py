"""
Test script for product matching system.

Demonstrates the matching algorithm with real-world examples.
"""

from scraper.utils.matcher import (
    ProductMatcher,
    ProductInfo,
    MatchResult,
    match_product,
    find_duplicates,
)


def test_basic_matching():
    """Test basic product matching."""
    print("=" * 60)
    print("TEST: Basic Product Matching")
    print("=" * 60)

    products = [
        ProductInfo(id=1, name="4 Gozlu Endustriyel Ocak - Dogalgazli"),
        ProductInfo(id=2, name="Endustriyel Kuzine 4 Burner - Heavy Duty"),
        ProductInfo(id=3, name="Fagor CG9-41 Ocak"),
        ProductInfo(id=4, name="Fagor Endustriyel Ocak CG9-41"),
        ProductInfo(id=5, name="Bosch PXY875DC1E Ocak"),
    ]

    matcher = ProductMatcher()

    # Test matching
    candidate = products[2]  # Fagor CG9-41 Ocak
    existing = [products[3], products[4]]  # Fagor CG9-41..., Bosch...

    result = matcher.match_product(candidate, existing)

    print(f"\nCandidate: {candidate.name}")
    print(f"Matched: {'YES' if result else 'NO'}")
    print(f"Product ID: {result.product_id}")
    print(f"Confidence: {result.confidence:.1f}%")
    print(f"Reason: {result.match_reason}")
    print(f"Scores: {result.scores}")


def test_batch_matching():
    """Test batch matching of multiple products."""
    print("\n" + "=" * 60)
    print("TEST: Batch Matching")
    print("=" * 60)

    new_products = [
        ProductInfo(id=None, name="Fagor CG9-41", site_name="cafemarkt"),
        ProductInfo(id=None, name="Endustriyel Kuzine 4 Burner", site_name="arigastro"),
        ProductInfo(id=None, name="Bosch PXY875DC1E", site_name="horecamarkt"),
    ]

    existing_products = [
        ProductInfo(id=100, name="Fagor Endustriyel Ocak CG9-41", brand="Fagor"),
        ProductInfo(id=101, name="Bosch Ocak PXY875DC1E", brand="Bosch"),
    ]

    matcher = ProductMatcher()
    results = matcher.match_all_products(new_products, existing_products)

    print(f"\nMatched: {len(results['matched'])}")
    for new_prod, target_id, conf in results['matched']:
        print(f"  - {new_prod.name} -> ID:{target_id} ({conf:.1f}%)")

    print(f"\nLow Confidence: {len(results['low_confidence'])}")
    for new_prod, target_id, conf in results['low_confidence']:
        print(f"  - {new_prod.name} -> ID:{target_id} ({conf:.1f}%)")

    print(f"\nUnmatched: {len(results['unmatched'])}")
    for prod in results['unmatched']:
        print(f"  - {prod.name}")


def test_sku_extraction():
    """Test SKU extraction from product names."""
    print("\n" + "=" * 60)
    print("TEST: SKU Extraction")
    print("=" * 60)

    matcher = ProductMatcher()

    test_names = [
        "Fagor CG9-41 Ocak",
        "Bosch PXY875DC1E",
        "TL-900 Series",
        "IM-500 Heavy Duty",
        "Model: CG9-41",
        "REF: TL900",
        "No SKU Here",
    ]

    print("\nSKU Extraction Results:")
    for name in test_names:
        sku = matcher.extract_sku(name)
        print(f"  {name:30} -> {sku or 'None'}")


def test_brand_extraction():
    """Test brand extraction from product names."""
    print("\n" + "=" * 60)
    print("TEST: Brand Extraction")
    print("=" * 60)

    matcher = ProductMatcher()

    test_names = [
        "Bosch PXY875DC1E Ocak",
        "Fagor CG9-41 Endustriyel",
        "Oztiryakiler IM-500",
        "Arçelik 1234",
        "Unknown Brand Product",
    ]

    print("\nBrand Extraction Results:")
    for name in test_names:
        brand = matcher.extract_brand(name)
        print(f"  {name:35} -> {brand or 'None'}")


def test_capacity_extraction():
    """Test capacity extraction from product names."""
    print("\n" + "=" * 60)
    print("TEST: Capacity Extraction")
    print("=" * 60)

    matcher = ProductMatcher()

    test_names = [
        "4 Gozlu Ocak",
        "900mm Fırın",
        "50lt Su Isıtıcı",
        "10kg Buzdolabı",
        "60x40cm Tezgah",
    ]

    print("\nCapacity Extraction Results:")
    for name in test_names:
        cap = matcher.extract_capacity(name)
        if cap:
            print(f"  {name:25} -> Type: {cap['type']:10} Value: {cap['value']}")
        else:
            print(f"  {name:25} -> None")


def test_duplicate_detection():
    """Test duplicate detection in a list."""
    print("\n" + "=" * 60)
    print("TEST: Duplicate Detection")
    print("=" * 60)

    products = [
        ProductInfo(id=1, name="Fagor CG9-41 Ocak"),
        ProductInfo(id=2, name="Fagor Endustriyel Ocak CG9-41"),
        ProductInfo(id=3, name="Bosch PXY875DC1E"),
        ProductInfo(id=4, name="Fagor CG 941"),
    ]

    duplicates = find_duplicates(products, threshold=80)

    print(f"\nFound {len(duplicates)} potential duplicates:")
    for p1, p2, score in duplicates:
        print(f"  - {p1.name} <-> {p2.name} ({score:.1f}%)")


def test_manual_mappings():
    """Test manual override mappings."""
    print("\n" + "=" * 60)
    print("TEST: Manual Mappings")
    print("=" * 60)

    # Add a manual mapping
    from scraper.utils.matcher import ManualMappings

    mappings = ManualMappings()
    mappings.add("cafemarkt_123", 456, 100, "Verified manually")

    # Test retrieval
    result = mappings.get("cafemarkt_123")
    print(f"\nManual mapping for 'cafemarkt_123': {result}")

    # Test non-existent
    result = mappings.get("nonexistent")
    print(f"Manual mapping for 'nonexistent': {result}")


def main():
    """Run all tests."""
    test_basic_matching()
    test_batch_matching()
    test_sku_extraction()
    test_brand_extraction()
    test_capacity_extraction()
    test_duplicate_detection()
    test_manual_mappings()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()

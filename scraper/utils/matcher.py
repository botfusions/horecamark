"""
Product matching system for HorecaMark.

Handles fuzzy matching of products from different sites that may have
different names but represent the same product.
"""

import re
import csv
import hashlib
import logging
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any

from thefuzz import fuzz, process

from .brand_list import normalize_brand, is_brand, BRAND_NORMALIZATION
from .normalizer import normalize as normalize_text

logger = logging.getLogger(__name__)

# Matching weights
WEIGHT_FUZZY = 0.60
WEIGHT_BRAND = 0.25
WEIGHT_SKU = 0.10
WEIGHT_CAPACITY = 0.05

# Matching thresholds
MATCH_THRESHOLD = 85
HIGH_CONFIDENCE = 95
MEDIUM_CONFIDENCE = 85
LOW_CONFIDENCE = 70

# SKU/Model number patterns (ordered by specificity)
SKU_PATTERNS = [
    r'\b[A-Z]{2,6}[-_]?\d{1,2}[-_]?\d{2,4}\b',  # CG9-41, TL-900, IM-500
    r'\b[A-Z]{2,6}[-_]?\d{4,}\b',  # CG941, TL900 (4+ digits)
    r'\b[A-Z]{1,3}\d{3,6}[A-Z]?\b',  # F41, TL900, CG941
    r'\b\d{3,6}[-_][A-Z]{2,6}\b',  # 900-CG, 500-IM
    r'(?:MOD|MODEL|TYPE)[:\s]*([A-Z0-9-]+)',  # MOD: CG9-41
    r'(?:REF|REFERENCE|KOD|KODU)[:\s]*([A-Z0-9-]+)',  # REF: TL900
    r'\b[A-Z]{2,4}\d{2,4}[-_]?\w*\b',  # PX87, CG9, etc.
    r'\b\d{3,}[A-Z]{2,}\b',  # 875DC1E, 900XYZ
]

# Capacity patterns
CAPACITY_PATTERNS = [
    (r'(\d+)\s*(?:gözlü|gozlu|g|eye|burner|bac|isi)', 'burner'),  # 4 gözlü
    (r'(\d+)\s*(?:mm|cm|m)', 'dimension'),  # 900mm, 60cm
    (r'(\d+(?:\.\d+)?)\s*(?:lt|l|litre|liter|ltr)', 'volume'),  # 50lt
    (r'(\d+(?:\.\d+)?)\s*(?:kg|gr|gram)', 'weight'),  # 10kg
    (r'(\d+)\s*[xX]\s*(\d+)', 'dimensions'),  # 6x7cm
]


@dataclass
class MatchResult:
    """Result of a product match operation."""

    product_id: Optional[int]
    confidence: float
    match_reason: str = ""
    scores: Dict[str, float] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.product_id is not None and self.confidence >= MATCH_THRESHOLD


@dataclass
class ProductInfo:
    """Product information for matching."""

    id: Optional[int]
    name: str
    brand: Optional[str] = None
    sku: Optional[str] = None
    capacity: Optional[str] = None
    category: Optional[str] = None
    site_name: Optional[str] = None


class ManualMappings:
    """Manages manual product override mappings."""

    def __init__(self, csv_path: str | Path | None = None):
        if csv_path is None:
            # Default path relative to project root
            project_root = Path(__file__).parent.parent.parent
            csv_path = project_root / "database" / "seeds" / "manual_mappings.csv"

        self.csv_path = Path(csv_path)
        self.mappings: Dict[str, Tuple[int, int, str]] = {}
        self._load()

    def _load(self) -> None:
        """Load manual mappings from CSV file."""
        if not self.csv_path.exists():
            logger.debug(f"Manual mappings file not found: {self.csv_path}")
            return

        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source_id = row.get('source_product_id', '').strip()

                    # Skip empty rows and comments
                    if not source_id or source_id.startswith('#'):
                        continue

                    try:
                        target_id = int(row.get('target_product_id', 0))
                        confidence = int(row.get('confidence', 100))
                        notes = row.get('notes', '').strip()

                        if target_id > 0:
                            self.mappings[source_id] = (target_id, confidence, notes)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Invalid mapping row: {row}, error: {e}")

            logger.info(f"Loaded {len(self.mappings)} manual mappings from {self.csv_path}")

        except Exception as e:
            logger.error(f"Error loading manual mappings: {e}")

    def get(self, source_id: str) -> Optional[Tuple[int, int, str]]:
        """Get manual mapping for a source product ID.

        Args:
            source_id: Source product ID (e.g., "cafemarkt_12345")

        Returns:
            Tuple of (target_id, confidence, notes) or None
        """
        return self.mappings.get(source_id)

    def add(self, source_id: str, target_id: int, confidence: int = 100, notes: str = "") -> None:
        """Add a manual mapping.

        Args:
            source_id: Source product ID
            target_id: Target product ID in products table
            confidence: Confidence score 1-100
            notes: Optional notes
        """
        self.mappings[source_id] = (target_id, confidence, notes)

    def save(self) -> None:
        """Save manual mappings to CSV file."""
        try:
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['source_product_id', 'target_product_id', 'confidence', 'notes'])
                for source_id, (target_id, confidence, notes) in self.mappings.items():
                    writer.writerow([source_id, target_id, confidence, notes])
            logger.info(f"Saved {len(self.mappings)} manual mappings to {self.csv_path}")
        except Exception as e:
            logger.error(f"Error saving manual mappings: {e}")


class ProductMatcher:
    """Multi-factor product matching system."""

    def __init__(self, manual_mappings_path: str | Path | None = None):
        self.manual_mappings = ManualMappings(manual_mappings_path)
        self._cache: Dict[str, MatchResult] = {}
        logger.info("ProductMatcher initialized")

    @staticmethod
    def extract_sku(name: str) -> Optional[str]:
        """Extract SKU/model number from product name.

        Args:
            name: Product name

        Returns:
            SKU string if found, None otherwise
        """
        if not name:
            return None

        for pattern in SKU_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                sku = match.group(1) if match.lastindex else match.group(0)
                # Normalize SKU
                sku = re.sub(r'[-_\s]+', '-', sku.strip().upper())
                return sku

        return None

    @staticmethod
    def extract_capacity(name: str) -> Optional[Dict[str, Any]]:
        """Extract capacity information from product name.

        Args:
            name: Product name

        Returns:
            Dict with capacity type and value, or None
        """
        if not name:
            return None

        for pattern, cap_type in CAPACITY_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                if cap_type == 'dimensions' and match.lastindex:
                    return {'type': cap_type, 'value': match.groups()}
                return {'type': cap_type, 'value': match.group(1)}

        return None

    @staticmethod
    def extract_brand(name: str) -> Optional[str]:
        """Extract brand from product name.

        Args:
            name: Product name

        Returns:
            Normalized brand name or None
        """
        if not name:
            return None

        words = name.split()

        # Check first word (brands usually at start)
        for word in words:
            word_clean = re.sub(r'[^\w]', '', word)
            if is_brand(word_clean):
                return normalize_brand(word_clean)

        # Check for brand patterns in full name
        for brand_normalized, canonical in BRAND_NORMALIZATION.items():
            if brand_normalized in name.lower():
                return canonical

        return None

    @staticmethod
    def calculate_fuzzy_score(name1: str, name2: str) -> float:
        """Calculate fuzzy string matching score.

        Args:
            name1: First product name
            name2: Second product name

        Returns:
            Score 0-100
        """
        if not name1 or not name2:
            return 0.0

        # Normalize both names
        norm1 = normalize_text(name1)
        norm2 = normalize_text(name2)

        # Calculate multiple similarity metrics
        ratio = fuzz.ratio(norm1, norm2)
        partial_ratio = fuzz.partial_ratio(norm1, norm2)
        token_sort = fuzz.token_sort_ratio(norm1, norm2)
        token_set = fuzz.token_set_ratio(norm1, norm2)

        # Weighted average favoring token set (handles word reordering)
        return (ratio * 0.2 + partial_ratio * 0.2 + token_sort * 0.2 + token_set * 0.4)

    @staticmethod
    def calculate_brand_score(brand1: Optional[str], brand2: Optional[str]) -> float:
        """Calculate brand match score.

        Args:
            brand1: First product brand
            brand2: Second product brand

        Returns:
            Score 0-100 (100 = perfect match, 50 = one unknown, 0 = mismatch)
        """
        if not brand1 or not brand2:
            return 50.0  # Neutral score when one or both brands unknown

        if brand1.lower() == brand2.lower():
            return 100.0

        return 0.0  # Explicit mismatch

    @staticmethod
    def calculate_sku_score(sku1: Optional[str], sku2: Optional[str]) -> float:
        """Calculate SKU match score.

        Args:
            sku1: First product SKU
            sku2: Second product SKU

        Returns:
            Score 0-100
        """
        if not sku1 or not sku2:
            return 50.0

        if sku1.lower() == sku2.lower():
            return 100.0

        # Check if one is substring of another
        if sku1.lower() in sku2.lower() or sku2.lower() in sku1.lower():
            return 75.0

        return 0.0

    @staticmethod
    def calculate_capacity_score(cap1: Optional[Dict], cap2: Optional[Dict]) -> float:
        """Calculate capacity match score.

        Args:
            cap1: First product capacity dict
            cap2: Second product capacity dict

        Returns:
            Score 0-100
        """
        if not cap1 or not cap2:
            return 50.0

        # Check capacity type match
        if cap1.get('type') == cap2.get('type'):
            if cap1.get('value') == cap2.get('value'):
                return 100.0
            # Try numeric comparison
            try:
                if isinstance(cap1['value'], (int, float)) and isinstance(cap2['value'], (int, float)):
                    if abs(cap1['value'] - cap2['value']) < 0.1:
                        return 100.0
            except (TypeError, ValueError):
                pass

        return 0.0

    def calculate_total_score(
        self,
        candidate: ProductInfo,
        existing: ProductInfo,
    ) -> Tuple[float, Dict[str, float]]:
        """Calculate weighted total match score.

        Args:
            candidate: Candidate product to match
            existing: Existing product in database

        Returns:
            Tuple of (total_score, individual_scores)
        """
        # Extract features
        candidate_brand = candidate.brand or self.extract_brand(candidate.name)
        existing_brand = existing.brand or self.extract_brand(existing.name)

        candidate_sku = candidate.sku or self.extract_sku(candidate.name)
        existing_sku = existing.sku or self.extract_sku(existing.name)

        candidate_cap = candidate.capacity or self.extract_capacity(candidate.name)
        existing_cap = existing.capacity or self.extract_capacity(existing.name)

        # Calculate individual scores
        fuzzy_score = self.calculate_fuzzy_score(candidate.name, existing.name)
        brand_score = self.calculate_brand_score(candidate_brand, existing_brand)
        sku_score = self.calculate_sku_score(candidate_sku, existing_sku)
        capacity_score = self.calculate_capacity_score(candidate_cap, existing_cap)

        # Weighted total
        total_score = (
            fuzzy_score * WEIGHT_FUZZY +
            brand_score * WEIGHT_BRAND +
            sku_score * WEIGHT_SKU +
            capacity_score * WEIGHT_CAPACITY
        )

        scores = {
            'fuzzy': fuzzy_score,
            'brand': brand_score,
            'sku': sku_score,
            'capacity': capacity_score,
            'total': total_score,
        }

        return total_score, scores

    def match_product(
        self,
        candidate: ProductInfo,
        existing_products: List[ProductInfo],
    ) -> MatchResult:
        """Match a candidate product against existing products.

        Args:
            candidate: Candidate product to match
            existing_products: List of existing products to match against

        Returns:
            MatchResult with best match or None if no match
        """
        if not existing_products:
            return MatchResult(None, 0.0, "No existing products")

        # Check manual mappings first
        if candidate.site_name and candidate.id:
            source_id = f"{candidate.site_name}_{candidate.id}"
            manual = self.manual_mappings.get(source_id)
            if manual:
                target_id, confidence, notes = manual
                return MatchResult(
                    product_id=target_id,
                    confidence=float(confidence),
                    match_reason=f"Manual mapping: {notes}",
                    scores={'manual': confidence},
                )

        # Check cache
        cache_key = self._make_cache_key(candidate.name)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached:
                return cached

        best_match = None
        best_score = 0.0
        best_scores = {}

        for existing in existing_products:
            total_score, scores = self.calculate_total_score(candidate, existing)

            if total_score > best_score:
                best_score = total_score
                best_match = existing
                best_scores = scores

        # Build match reason
        reasons = []
        if best_scores.get('fuzzy', 0) > 80:
            reasons.append("name similar")
        if best_scores.get('brand', 0) == 100:
            reasons.append("brand match")
        if best_scores.get('sku', 0) == 100:
            reasons.append("SKU match")
        if best_scores.get('capacity', 0) == 100:
            reasons.append("capacity match")

        match_reason = ", ".join(reasons) if reasons else "combined factors"

        result = MatchResult(
            product_id=best_match.id if best_match else None,
            confidence=best_score,
            match_reason=match_reason,
            scores=best_scores,
        )

        # Cache if high confidence
        if best_score >= HIGH_CONFIDENCE:
            self._cache[cache_key] = result

        return result

    def match_all_products(
        self,
        new_products: List[ProductInfo],
        existing_products: List[ProductInfo],
        threshold: float = MATCH_THRESHOLD,
    ) -> Dict[str, Any]:
        """Match all new products against existing database.

        Args:
            new_products: List of new products to match
            existing_products: List of existing products in database
            threshold: Minimum confidence for auto-match

        Returns:
            Dict with matched, unmatched, and low_confidence lists
        """
        results = {
            'matched': [],  # (new_product, existing_id, confidence)
            'unmatched': [],  # new_product
            'low_confidence': [],  # (new_product, existing_id, confidence)
        }

        for new_product in new_products:
            result = self.match_product(new_product, existing_products)

            if result.confidence >= HIGH_CONFIDENCE:
                results['matched'].append((new_product, result.product_id, result.confidence))
            elif result.confidence >= threshold:
                results['matched'].append((new_product, result.product_id, result.confidence))
            elif result.confidence >= LOW_CONFIDENCE:
                results['low_confidence'].append((new_product, result.product_id, result.confidence))
            else:
                results['unmatched'].append(new_product)

            # Log low confidence matches for review
            if LOW_CONFIDENCE <= result.confidence < threshold:
                logger.info(
                    f"Low confidence match: '{new_product.name}' -> "
                    f"ID:{result.product_id} ({result.confidence:.1f}%)"
                )

        return results

    @staticmethod
    def _make_cache_key(name: str) -> str:
        """Create cache key from product name."""
        normalized = normalize_text(name)
        return hashlib.md5(normalized.encode()).hexdigest()

    def clear_cache(self) -> None:
        """Clear the match cache."""
        self._cache.clear()

    @lru_cache(maxsize=1000)
    def get_best_matches(
        self,
        candidate_name: str,
        existing_products: List[ProductInfo],
        limit: int = 5,
    ) -> List[Tuple[ProductInfo, float, Dict[str, float]]]:
        """Get best potential matches for a candidate product.

        Args:
            candidate_name: Candidate product name
            existing_products: List of existing products
            limit: Maximum number of results

        Returns:
            List of (product, score, scores_dict) tuples
        """
        candidate = ProductInfo(id=None, name=candidate_name)

        results = []
        for existing in existing_products:
            total_score, scores = self.calculate_total_score(candidate, existing)
            results.append((existing, total_score, scores))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]


# Convenience functions

def match_product(
    candidate_name: str,
    existing_products: List[ProductInfo],
    candidate_brand: Optional[str] = None,
) -> Optional[int]:
    """Quick match function for simple use cases.

    Args:
        candidate_name: Candidate product name
        existing_products: List of existing products
        candidate_brand: Optional brand hint

    Returns:
        Matched product ID or None
    """
    matcher = ProductMatcher()
    candidate = ProductInfo(id=None, name=candidate_name, brand=candidate_brand)
    result = matcher.match_product(candidate, existing_products)

    if result:
        return result.product_id

    return None


def find_duplicates(
    products: List[ProductInfo],
    threshold: float = 90,
) -> List[Tuple[ProductInfo, ProductInfo, float]]:
    """Find potential duplicate products in a list.

    Args:
        products: List of products to check
        threshold: Minimum score to consider as duplicate

    Returns:
        List of (product1, product2, score) tuples
    """
    matcher = ProductMatcher()
    duplicates = []
    checked = set()

    for i, p1 in enumerate(products):
        for j, p2 in enumerate(products):
            if i >= j:
                continue

            pair_key = tuple(sorted([p1.name or '', p2.name or '']))
            if pair_key in checked:
                continue
            checked.add(pair_key)

            score, _ = matcher.calculate_total_score(p1, p2)

            if score >= threshold:
                duplicates.append((p1, p2, score))

    return duplicates

"""
UniMat AI — NLP Standardization Service

Combines regex-based tokenization with abbreviation expansion
to produce clean, standardized material descriptions for vector embedding.
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger("unimat.nlp")

# ─── Abbreviation Expansion Map ────────────────────────────────────────────────
# All abbreviations EXPAND to full readable words so the embedding model
# (trained on general English) understands the domain terms better.
# This is a generic industrial vocabulary — not specific to any dataset.
ABBREVIATIONS = {
    # Valve types
    "VLV": "VALVE", "GTE": "GATE", "CHK": "CHECK", "GLB": "GLOBE",
    "BFLY": "BUTTERFLY", "NRV": "NON RETURN VALVE",
    # Product types / Components
    "FLG": "FLANGE", "GSKT": "GASKET", "BRG": "BEARING",
    "BLT": "BOLT", "CBL": "CABLE", "LUB": "LUBRICANT", "GRS": "GREASE",
    # Materials / Chemicals
    "CS": "CARBON STEEL", "SS": "STAINLESS STEEL", "STL": "STEEL",
    "CU": "COPPER", "ALUM": "ALUMINIUM", "GI": "GALVANIZED IRON",
    "HDPE": "HIGH DENSITY POLYETHYLENE", "LITH": "LITHIUM", "NIT": "NITRILE",
    # Mechanical components
    "CENTRFGL": "CENTRIFUGAL", "CENT.": "CENTRIFUGAL",
    "SMLS": "SEAMLESS", "ERW": "ELECTRIC RESISTANCE WELDED",
    # Dimensions — expand to full words for better embedding
    "NB": "NOMINAL BORE", "OD": "OUTSIDE DIAMETER", "ID": "INSIDE DIAMETER",
    "DIA": "DIAMETER", "THK": "THICK", "LEN": "LENGTH",
    "SQMM": "SQ MM", "SQ.MM": "SQ MM", "MM2": "SQ MM",
    "MTR": "METER",
    # Pressure & Class
    "SCH": "SCHEDULE",
    # Flow/Pump
    "HORIZ": "HORIZONTAL", "CUM/HR": "M3/HR", "CU.M/HR": "M3/HR",
    # Fittings
    "WNRF": "WELD NECK RAISED FACE", "WN": "WELD NECK",
    "BW": "BUTT WELD", "RF": "RAISED FACE",
    "CON": "CONCENTRIC", "CONC": "CONCENTRIC",
    "LR": "LONG RADIUS", "EQ": "EQUAL",
    # Seals / Gaskets
    "SW": "SPIRAL WOUND", "SPWD": "SPIRAL WOUND", "SWG": "SPIRAL WOUND GASKET",
    "GRPH": "GRAPHITE", "GR": "GRAPHITE", "GRA": "GRAPHITE", "NBR": "NITRILE RUBBER",
    "DURO": "SHORE",
    # Cable/Electrical
    "ARMR": "ARMOURED", "ARM": "ARMOURED",
    "PWR": "POWER", "CTRL": "CONTROL",
    "XLPE": "XLPE", "PVC": "PVC",
    "MCCB": "MOLDED CASE CIRCUIT BREAKER",
    # Instruments
    "PRESS": "PRESSURE", "XMITR": "TRANSMITTER", "TX": "TRANSMITTER",
    "PT": "PRESSURE TRANSMITTER", "TW": "THERMOWELL",
    "RTD": "RESISTANCE TEMPERATURE DETECTOR",
    "DMM": "DIGITAL MULTIMETER",
    "NPT": "NATIONAL PIPE THREAD",
    # Attributes / Misc
    "SFTY": "SAFETY", "YEL": "YELLOW", "COMP": "COMPLEX", "EP": "EXTREME PRESSURE",
    # Assembly / General
    "ASSY": "ASSEMBLY",
    # Standards
    "DG": "DEEP GROOVE", "TEFC": "TOTALLY ENCLOSED FAN COOLED",
    "3PH": "3 PHASE",
}

# Regex patterns for extracting structured specs
SPEC_PATTERNS = {
    "dimension_inches": re.compile(r'(\d+(?:\.\d+)?)\s*(?:"|INCH|IN(?:CH)?)\b', re.IGNORECASE),
    "dimension_mm": re.compile(r'(\d+(?:\.\d+)?)\s*(?:MM|MILLIMETER)\b', re.IGNORECASE),
    "pressure_class": re.compile(r'(?:CLASS|CL|#)\s*(\d+)', re.IGNORECASE),
    "schedule": re.compile(r'SCH(?:EDULE)?\s*[-]?\s*(\d+[A-Z]?)', re.IGNORECASE),
    "voltage": re.compile(r'(\d+(?:\.\d+)?)\s*(?:KV|KVOLT)', re.IGNORECASE),
    "power": re.compile(r'(\d+(?:\.\d+)?)\s*(?:KW|KILOWATT)', re.IGNORECASE),
    "rpm": re.compile(r'(\d+)\s*RPM', re.IGNORECASE),
    "flow_rate": re.compile(r'(\d+(?:\.\d+)?)\s*(?:M3/HR|CUM/HR|CU\.M/HR)', re.IGNORECASE),
    "dn_size": re.compile(r'DN\s*(\d+)', re.IGNORECASE),
    "bearing_code": re.compile(r'\b(\d{4}-\d[A-Z]+)\b', re.IGNORECASE),
    "astm_grade": re.compile(r'(?:ASTM\s*)?A\d{2,3}\s*(?:GR\.?\s*[A-Z])?', re.IGNORECASE),
    "core_cable": re.compile(r'(\d+(?:\.\d+)?)\s*(?:C|CORE)', re.IGNORECASE),
}

# ─── spaCy model (lazy loaded) ─────────────────────────────────────────────────
_nlp_model = None


def _get_spacy_model():
    """Lazy-load spaCy model to avoid import-time overhead."""
    global _nlp_model
    if _nlp_model is None:
        try:
            import spacy
            _nlp_model = spacy.load("en_core_web_sm")
            logger.info("spaCy model 'en_core_web_sm' loaded successfully")
        except OSError:
            logger.warning("spaCy model 'en_core_web_sm' not found. Using regex-only mode.")
            _nlp_model = False  # Sentinel to avoid retrying
    return _nlp_model if _nlp_model is not False else None


def expand_abbreviations(text: str) -> str:
    """Expand known industrial abbreviations to full forms."""
    for abbrev, expansion in ABBREVIATIONS.items():
        # Use word boundary matching to avoid partial replacements
        text = re.sub(r'\b' + re.escape(abbrev) + r'\b', expansion, text)
    return text


def clean_text(text: str) -> str:
    """
    Standardize raw material description text.
    
    Pipeline:
    1. Uppercase normalization
    2. Replace hyphens with spaces (so coded items tokenize like descriptions)
    3. Abbreviation expansion
    4. Special character cleanup
    5. Whitespace normalization
    """
    if not text or str(text).strip() == "":
        return ""

    text = str(text).upper().strip()

    # Normalize quote marks used as inch symbol
    text = text.replace('"', ' INCH ')
    text = text.replace("''", ' INCH ')

    # Replace hyphens with spaces so coded items (FLG-WN-SS316-2IN)
    # tokenize the same as space-separated descriptions
    text = text.replace('-', ' ')

    # Expand abbreviations (after hyphen breaking so word boundaries match)
    text = expand_abbreviations(text)

    # Keep alphanumeric, periods, slashes, hash (for class #), spaces
    text = re.sub(r'[^A-Z0-9.\#\/\s]', ' ', text)

    # Collapse whitespace
    text = " ".join(text.split())

    return text


def extract_specs(text: str) -> dict:
    """
    Extract structured technical specifications from text using regex patterns.
    Returns a dict of extracted spec fields.
    """
    specs = {}
    for spec_name, pattern in SPEC_PATTERNS.items():
        match = pattern.search(text)
        if match:
            specs[spec_name] = match.group(0).strip()
    return specs


def spacy_extract_entities(text: str) -> List[str]:
    """
    Use spaCy NER to extract material-relevant entities.
    Falls back to empty list if spaCy is unavailable.
    """
    nlp = _get_spacy_model()
    if nlp is None:
        return []

    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ in ("ORG", "PRODUCT", "QUANTITY", "CARDINAL"):
            entities.append(ent.text.upper())
    return entities


def standardize(raw_description: str, uom: str = "") -> Tuple[str, dict]:
    """
    Full NLP standardization pipeline for a single material item.
    
    Args:
        raw_description: The raw material description from the CPSE.
        uom: Unit of measurement (kept as metadata, NOT embedded).
    
    Returns:
        Tuple of (parsed_string, extracted_specs_dict)
    """
    # UOM is intentionally excluded from the parsed string.
    # Terms like NOS, EA, SET, NUM are noise that reduces embedding similarity
    # between items that describe the same material with different UOMs.

    # Step 1: Clean and expand (description only, no UOM)
    parsed = clean_text(raw_description)

    # Step 2: Extract structured specs (for metadata, not for the embedding string)
    specs = extract_specs(raw_description.upper())
    if uom:
        specs["uom"] = uom.upper().strip()

    # Note: spaCy entity extraction was removed because the abbreviation expansion
    # already handles domain terms, and spaCy's general NER was appending duplicate
    # noise (e.g., "CS 4 INCH 300#") that reduced embedding similarity accuracy.

    return parsed, specs


def standardize_batch(items: List[dict]) -> List[dict]:
    """
    Standardize a batch of material items.
    
    Args:
        items: List of dicts with 'raw_description' and optional 'uom' keys.
    
    Returns:
        List of dicts with added 'parsed_string' and 'specs' keys.
    """
    results = []
    for item in items:
        raw_desc = item.get("raw_description", "")
        uom = item.get("uom", "")
        parsed_string, specs = standardize(raw_desc, uom)
        results.append({
            **item,
            "parsed_string": parsed_string,
            "specs": specs,
        })
    return results

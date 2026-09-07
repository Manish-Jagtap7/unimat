"""
UniMat AI — LLM Service (Gemini)

High-speed batch generation of Common National Material Codes (CNMC)
using Google Generative AI (Gemini). Batches multiple unique items into
a single structured JSON prompt to minimize API latency.
"""

import json
import hashlib
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger("unimat.llm")

settings = get_settings()

# ─── Result Model ───────────────────────────────────────────────────────────────

@dataclass
class GeneratedCode:
    """A generated Common National Material Code."""
    cnmc_code: str
    standardized_description: str
    category: Optional[str] = None


# ─── Fallback Hash-Based Code Generator ─────────────────────────────────────────

def _generate_fallback_code(descriptions: List[str]) -> GeneratedCode:
    """
    Generate a deterministic fallback CNMC when the LLM is unavailable.
    Uses MD5 hash of the combined descriptions for uniqueness.
    """
    combined = " | ".join(sorted(descriptions))
    hash_suffix = hashlib.md5(combined.encode()).hexdigest()[:6].upper()

    # Pick the longest description as the "best" standardized version
    best_desc = max(descriptions, key=len) if descriptions else "Standardized Material"

    return GeneratedCode(
        cnmc_code=f"IND-MAT-{hash_suffix}",
        standardized_description=best_desc.title(),
        category=None,
    )


# ─── Gemini API Batch Call ──────────────────────────────────────────────────────

def _build_prompt(batch_payload: Dict[str, List[str]]) -> str:
    """
    Build the structured JSON prompt for Gemini.
    
    Input format:
    {
        "group_0": ["desc1", "desc2", ...],
        "group_1": ["desc3", "desc4", ...],
    }
    """
    payload_str = json.dumps(batch_payload, indent=2)

    prompt = (
        "You are an AI Master Data expert specializing in industrial material standardization "
        "for Central Public Sector Enterprises (CPSEs) in India.\n\n"
        "I will provide a JSON object where keys are Group IDs and values are lists of "
        "similar or functionally equivalent legacy material descriptions from different CPSEs.\n\n"
        "For EACH Group ID, generate:\n"
        "1. A 'cnmc_code' — a Common National Material Code in the format: "
        "IND-[SECTOR]-[CATEGORY]-[SEQUENCE] (e.g., IND-OG-VLV-001, IND-PWR-CABLE-042)\n"
        "   - SECTOR: OG (Oil & Gas), PWR (Power), STL (Steel), GEN (General)\n"
        "   - CATEGORY: Short material category code (3-6 chars)\n"
        "2. A 'standardized_description' — a clean, standardized technical description "
        "following Indian industrial naming conventions.\n"
        "3. A 'category' — the material category (e.g., 'Valves', 'Pipes', 'Cables', 'Bearings')\n\n"
        "Respond ONLY with a valid JSON object (NO markdown, NO explanation):\n"
        '{"group_0": {"cnmc_code": "...", "standardized_description": "...", "category": "..."}, ...}\n\n'
        f"Input:\n{payload_str}"
    )

    return prompt


def _call_gemini(prompt: str) -> Optional[dict]:
    """
    Call the Gemini API with the given prompt.
    Returns parsed JSON dict or None on failure.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("No Gemini API key configured — using fallback codes")
        return None

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1},
        )

        text = response.text.strip()

        # Strip markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return None


# ─── Public API ─────────────────────────────────────────────────────────────────

def generate_codes_batch(
    groups: Dict[str, List[str]],
) -> Dict[str, GeneratedCode]:
    """
    Generate CNMC codes for multiple groups of material descriptions.
    
    Uses high-speed batching: groups are packed into a single Gemini API call
    (up to LLM_BATCH_SIZE groups per call) to minimize latency.
    
    Args:
        groups: Dict mapping group_id -> list of raw descriptions.
                e.g. {"group_0": ["desc1", "desc2"], "group_1": ["desc3"]}
    
    Returns:
        Dict mapping group_id -> GeneratedCode
    """
    if not groups:
        return {}

    # Pre-generate fallback codes for all groups
    results: Dict[str, GeneratedCode] = {}
    for group_id, descriptions in groups.items():
        results[group_id] = _generate_fallback_code(descriptions)

    # Split into batches for the LLM
    group_ids = list(groups.keys())
    batch_size = settings.LLM_BATCH_SIZE

    for batch_start in range(0, len(group_ids), batch_size):
        batch_ids = group_ids[batch_start:batch_start + batch_size]
        batch_payload = {gid: groups[gid] for gid in batch_ids}

        logger.info(
            f"Calling Gemini for batch {batch_start // batch_size + 1} "
            f"({len(batch_ids)} groups)"
        )

        prompt = _build_prompt(batch_payload)
        llm_response = _call_gemini(prompt)

        if llm_response:
            for gid in batch_ids:
                if gid in llm_response:
                    data = llm_response[gid]
                    results[gid] = GeneratedCode(
                        cnmc_code=data.get("cnmc_code", results[gid].cnmc_code),
                        standardized_description=data.get(
                            "standardized_description",
                            results[gid].standardized_description,
                        ),
                        category=data.get("category"),
                    )
            logger.info(f"Gemini batch successful: {len(batch_ids)} groups processed")
        else:
            logger.warning(f"Gemini batch failed — using fallback codes for {len(batch_ids)} groups")

    return results


def generate_single_code(descriptions: List[str]) -> GeneratedCode:
    """
    Generate a CNMC code for a single group of descriptions.
    Convenience wrapper around generate_codes_batch.
    """
    results = generate_codes_batch({"single": descriptions})
    return results.get("single", _generate_fallback_code(descriptions))

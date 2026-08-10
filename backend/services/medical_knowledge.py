import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICD10_FILE = os.path.join(BASE_DIR, "data", "icd10_codes.json")
MEDICATIONS_FILE = os.path.join(BASE_DIR, "data", "medications.json")
SNOMED_FILE = os.path.join(BASE_DIR, "data", "snomed_codes.json")

_ICD10_CACHE = None
_MEDICATIONS_CACHE = None
_SNOMED_CACHE = None

STOP_WORDS = {
    "with", "from", "been", "have", "that", "this", "your", "will", "what", "when",
    "more", "most", "about", "some", "such", "after", "before", "over", "under", "into",
    "than", "then", "just", "also", "like", "dose", "days", "oral", "take", "patient", "history",
    # Generic clinical structural words that appear across many unrelated indications
    # (e.g. "syndrome" matches both "Irritable Bowel Syndrome" and "Acute Coronary
    # Syndrome") — matching on these alone caused unrelated medications to be suggested.
    "syndrome", "disorder", "disease", "condition", "chronic", "acute", "unspecified",
    "likely", "functional",
}

def load_icd10_dataset() -> List[Dict[str, Any]]:
    global _ICD10_CACHE
    if _ICD10_CACHE is not None:
        return _ICD10_CACHE
    if os.path.exists(ICD10_FILE):
        with open(ICD10_FILE, "r") as f:
            _ICD10_CACHE = json.load(f)
            return _ICD10_CACHE
    return []

def load_medications_dataset() -> List[Dict[str, Any]]:
    global _MEDICATIONS_CACHE
    if _MEDICATIONS_CACHE is not None:
        return _MEDICATIONS_CACHE
    if os.path.exists(MEDICATIONS_FILE):
        with open(MEDICATIONS_FILE, "r") as f:
            _MEDICATIONS_CACHE = json.load(f)
            return _MEDICATIONS_CACHE
    return []

def load_snomed_dataset() -> List[Dict[str, Any]]:
    global _SNOMED_CACHE
    if _SNOMED_CACHE is not None:
        return _SNOMED_CACHE
    if os.path.exists(SNOMED_FILE):
        with open(SNOMED_FILE, "r") as f:
            _SNOMED_CACHE = json.load(f)
            return _SNOMED_CACHE
    return []


def _score_by_keywords(dataset: List[Dict[str, Any]], combined_text: str) -> List[Dict[str, Any]]:
    """Scores each dataset entry by how many of its keywords appear in combined_text."""
    scored = []
    for item in dataset:
        score = sum(1 for kw in item.get("keywords", []) if kw and kw.lower() in combined_text)
        if score > 0:
            scored.append((item, score))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def auto_match_icd10_codes(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Auto-matches relevant ICD-10 disease codes from the transcript and diagnosis text.
    """
    combined_text = f"{transcript} {diagnosis_text}".lower()
    scored = _score_by_keywords(load_icd10_dataset(), combined_text)
    matched = [
        {
            "code": item["code"],
            "title": item["title"],
            "category": item["category"],
            "relevanceScore": score
        }
        for item, score in scored
    ]
    return matched[:5]


def auto_match_snomed_codes(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Auto-matches relevant SNOMED CT concepts from the transcript and diagnosis text,
    using the same keyword-scoring approach as auto_match_icd10_codes.
    """
    combined_text = f"{transcript} {diagnosis_text}".lower()
    scored = _score_by_keywords(load_snomed_dataset(), combined_text)
    matched = [
        {
            "conceptId": item["conceptId"],
            "term": item["preferredTerm"],
            "category": item["category"],
            "icd10Map": item.get("icd10Map"),
            "relevanceScore": score
        }
        for item, score in scored
    ]
    return matched[:5]


def auto_suggest_prescriptions(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Auto-suggests relevant medications/prescriptions based on clinical findings.
    Filters out common conversational English stop-words to prevent false positive matches,
    and — like auto_match_icd10_codes/auto_match_snomed_codes — sorts by relevance and caps
    the result, so a broader medications dataset doesn't flood the note with every medication
    that shares one generic word with the diagnosis text (e.g. "syndrome", "disorder").
    """
    meds = load_medications_dataset()
    scored = []
    combined_text = f"{transcript} {diagnosis_text}".lower()

    for med in meds:
        indication_lower = med["indication"].lower()
        keywords = indication_lower.replace(",", "").replace("/", " ").split()
        match_count = sum(1 for kw in keywords if len(kw) > 3 and kw not in STOP_WORDS and kw in combined_text)

        if match_count > 0:
            scored.append((med, match_count))

    scored.sort(key=lambda pair: pair[1], reverse=True)

    return [
        {
            "name": med["name"],
            "brand": med["brand"],
            "dosage": med["defaultDosage"],
            "frequency": med["defaultFrequency"],
            "route": med["defaultRoute"],
            "duration": med["defaultDuration"],
            "indication": med["indication"]
        }
        for med, _score in scored[:5]
    ]


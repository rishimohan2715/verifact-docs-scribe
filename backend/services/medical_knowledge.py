import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICD10_FILE = os.path.join(BASE_DIR, "data", "icd10_codes.json")
MEDICATIONS_FILE = os.path.join(BASE_DIR, "data", "medications.json")

_ICD10_CACHE = None
_MEDICATIONS_CACHE = None

STOP_WORDS = {
    "with", "from", "been", "have", "that", "this", "your", "will", "what", "when",
    "more", "most", "about", "some", "such", "after", "before", "over", "under", "into",
    "than", "then", "just", "also", "like", "dose", "days", "oral", "take", "patient", "history"
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

def auto_match_icd10_codes(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Auto-matches relevant ICD-10 disease codes from the transcript and diagnosis text.
    """
    icd10_list = load_icd10_dataset()
    matched = []
    combined_text = f"{transcript} {diagnosis_text}".lower()

    for item in icd10_list:
        score = 0
        for kw in item.get("keywords", []):
            if kw and kw.lower() in combined_text:
                score += 1
        if score > 0:
            matched.append({
                "code": item["code"],
                "title": item["title"],
                "category": item["category"],
                "relevanceScore": score
            })

    # Sort by relevance score
    matched.sort(key=lambda x: x["relevanceScore"], reverse=True)
    return matched[:5]


def auto_suggest_prescriptions(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Auto-suggests relevant medications/prescriptions based on clinical findings.
    Filters out common conversational English stop-words to prevent false positive matches.
    """
    meds = load_medications_dataset()
    suggested = []
    combined_text = f"{transcript} {diagnosis_text}".lower()

    for med in meds:
        indication_lower = med["indication"].lower()
        keywords = indication_lower.replace(",", "").replace("/", " ").split()
        match_count = sum(1 for kw in keywords if len(kw) > 3 and kw not in STOP_WORDS and kw in combined_text)

        if match_count > 0:
            suggested.append({
                "name": med["name"],
                "brand": med["brand"],
                "dosage": med["defaultDosage"],
                "frequency": med["defaultFrequency"],
                "route": med["defaultRoute"],
                "duration": med["defaultDuration"],
                "indication": med["indication"]
            })

    return suggested


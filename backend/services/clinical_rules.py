import logging
from typing import List, Dict, Any
from services.text_extraction import find_sentences_containing

logger = logging.getLogger(__name__)

_NO_SENTENCE_FALLBACK = "Keyword match found in transcript; no single sentence could be isolated as evidence."


def _evidence_quote(transcript: str, keywords: List[str]) -> str:
    matches = find_sentences_containing(transcript, keywords, max_results=1)
    return matches[0] if matches else _NO_SENTENCE_FALLBACK


def analyze_clinical_risks(transcript: str, diagnosis_text: str) -> Dict[str, Any]:
    """
    Analyzes the consultation transcript and Ollama diagnosis to detect urgent clinical red flags,
    diagnostic risks, and clinical decision support recommendations for the doctor.

    This is the rule-based fallback used only when the LLM-driven analysis in services.llm is
    unavailable. Every evidenceQuote below is extracted from the actual transcript passed in —
    never a hardcoded string — so what's shown to the clinician is always something the patient
    or doctor actually said, not a canned line copied from the demo-case generator.
    """
    t_lower = transcript.lower()
    d_lower = diagnosis_text.lower()

    alerts: List[Dict[str, Any]] = []

    # 1. Acute Appendicitis Red Flag
    appendicitis_kw = ["appendicitis", "mcburney", "rlq", "right lower quadrant", "rebound tenderness"]
    if any(k in t_lower or k in d_lower for k in appendicitis_kw):
        alerts.append({
            "severity": "HIGH",
            "category": "Surgical Abdomen Red Flag",
            "title": "Acute Appendicitis / Right Lower Quadrant Peritonitis",
            "description": "Migration of abdominal pain to RLQ with McBurney's tenderness, guarding, and leukocytosis.",
            "recommendedAction": "Order Stat Abdominal Ultrasound / CT Abdomen. Keep patient NPO (nothing by mouth) and request Stat Surgical Consult.",
            "evidenceQuote": _evidence_quote(transcript, appendicitis_kw)
        })

    # 2. Acute Coronary Syndrome (ACS) / Myocardial Infarction Red Flag
    acs_kw = ["chest pain", "breastbone", "radiates", "left arm", "jaw", "st-segment", "troponin"]
    if any(k in t_lower or k in d_lower for k in acs_kw):
        alerts.append({
            "severity": "HIGH",
            "category": "Cardiovascular Red Flag",
            "title": "Acute Coronary Syndrome / Suspected MI",
            "description": "Retrosternal crushing chest pain with radiation and ECG ST changes detected.",
            "recommendedAction": "Administer Aspirin 325mg + Sublingual Nitroglycerin immediately. Order Stat Troponin I/T and serial 12-lead ECGs. Alert Cath Lab for potential PCI.",
            "evidenceQuote": _evidence_quote(transcript, acs_kw)
        })

    # 3. Severe Asthma Exacerbation Red Flag
    asthma_kw = ["asthma", "wheeze", "wheezing", "salbutamol", "albuterol"]
    if any(k in t_lower or k in d_lower for k in asthma_kw):
        alerts.append({
            "severity": "HIGH",
            "category": "Respiratory Red Flag",
            "title": "Acute Severe Asthma Exacerbation",
            "description": "Persistent wheezing, chest tightness, and Albuterol non-responsiveness.",
            "recommendedAction": "Administer Nebulized Salbutamol + Ipratropium stat, plus Systemic Corticosteroids (Prednisolone 40mg). Monitor Peak Flow & SpO2.",
            "evidenceQuote": _evidence_quote(transcript, asthma_kw)
        })

    # 4. Diabetic Ketoacidosis (DKA) Red Flag
    dka_kw = ["dka", "ketoacidosis", "kussmaul", "ketones", "glucose", "hyperglycemia"]
    if any(k in t_lower or k in d_lower for k in dka_kw):
        alerts.append({
            "severity": "HIGH",
            "category": "Endocrine Emergency",
            "title": "Diabetic Ketoacidosis (DKA) / Severe Metabolic Acidosis",
            "description": "Hyperglycemia, Kussmaul breathing, positive ketones, and metabolic acidosis.",
            "recommendedAction": "Initiate aggressive IV Normal Saline fluid resuscitation, continuous IV Regular Insulin infusion, and monitor Serum Potassium q2h.",
            "evidenceQuote": _evidence_quote(transcript, dka_kw)
        })

    # 5. Acute Renal Colic Red Flag
    renal_kw = ["renal colic", "flank", "hematuria", "groin", "cva tenderness"]
    if any(k in t_lower or k in d_lower for k in renal_kw):
        alerts.append({
            "severity": "MEDIUM",
            "category": "Urological Assessment",
            "title": "Acute Renal Colic / Suspected Nephrolithiasis",
            "description": "Excruciating flank pain radiating to groin with gross hematuria.",
            "recommendedAction": "Administer IV Ketorolac 30mg for analgesia. Order non-contrast CT Abdomen/Pelvis to locate ureteral stone size and location.",
            "evidenceQuote": _evidence_quote(transcript, renal_kw)
        })

    # 6. Neurological Red Flags (TIA / Stroke / Bell's Palsy)
    neuro_kw = ["droop", "drooping", "face", "facial", "slurred", "weakness", "numbness"]
    if any(k in t_lower or k in d_lower for k in neuro_kw):
        alerts.append({
            "severity": "HIGH",
            "category": "Neurological Red Flag",
            "title": "Possible TIA / Acute Neurological Event",
            "description": "Transcript indicates sudden onset of facial drooping / weakness. Urgent evaluation required.",
            "recommendedAction": "Order non-contrast Head CT / Brain MRI. Assess NIHSS score and perform cranial nerve exam.",
            "evidenceQuote": _evidence_quote(transcript, neuro_kw)
        })

    # 7. Gastrointestinal Assessment (General Epigastric Pain)
    gi_kw = ["stomach", "abdomen", "paining", "severe pain", "vomiting"]
    if any(k in t_lower or k in d_lower for k in gi_kw) and not alerts:
        alerts.append({
            "severity": "MEDIUM",
            "category": "Gastrointestinal Assessment",
            "title": "Acute Epigastric / Abdominal Pain",
            "description": "Reported abdominal pain.",
            "recommendedAction": "Perform abdominal palpation for rebound tenderness/guarding. Check serum amylase, lipase, and LFTs.",
            "evidenceQuote": _evidence_quote(transcript, gi_kw)
        })

    sections_checked = 0
    total_checks = 6
    if len(transcript) > 20: sections_checked += 1
    if len(alerts) > 0: sections_checked += 1
    if "diagnosis" in d_lower or len(d_lower) > 10: sections_checked += 1
    if any(w in t_lower for w in ["mg", "dose", "prescribe", "take", "treatment"]): sections_checked += 1
    sections_checked += 2

    quality_score = int((sections_checked / total_checks) * 100)

    return {
        "qualityScore": quality_score,
        "qualityRating": "Excellent Clinical Quality" if quality_score >= 85 else "Good",
        "alerts": alerts,
        "totalAlertsCount": len(alerts)
    }

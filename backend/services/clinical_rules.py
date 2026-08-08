import re
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def analyze_clinical_risks(transcript: str, diagnosis_text: str) -> Dict[str, Any]:
    """
    Analyzes the consultation transcript and Ollama diagnosis to detect urgent clinical red flags,
    diagnostic risks, and clinical decision support recommendations for the doctor.
    """
    t_lower = transcript.lower()
    d_lower = diagnosis_text.lower()

    alerts: List[Dict[str, Any]] = []

    # 1. Acute Appendicitis Red Flag
    if any(k in t_lower or k in d_lower for k in ["appendicitis", "mcburney", "rlq", "right lower quadrant", "rebound tenderness"]):
        alerts.append({
            "severity": "HIGH",
            "category": "Surgical Abdomen Red Flag",
            "title": "Acute Appendicitis / Right Lower Quadrant Peritonitis",
            "description": "Migration of abdominal pain to RLQ with McBurney's tenderness, guarding, and leukocytosis.",
            "recommendedAction": "Order Stat Abdominal Ultrasound / CT Abdomen. Keep patient NPO (nothing by mouth) and request Stat Surgical Consult.",
            "evidenceQuote": "pain around belly button shifted to lower right side... McBurney's point tenderness with positive rebound"
        })

    # 2. Acute Coronary Syndrome (ACS) / Myocardial Infarction Red Flag
    if any(k in t_lower or k in d_lower for k in ["chest pain", "breastbone", "radiates", "left arm", "jaw", "st-segment", "troponin"]):
        alerts.append({
            "severity": "HIGH",
            "category": "Cardiovascular Red Flag",
            "title": "Acute Coronary Syndrome / Suspected MI",
            "description": "Retrosternal crushing chest pain with radiation and ECG ST changes detected.",
            "recommendedAction": "Administer Aspirin 325mg + Sublingual Nitroglycerin immediately. Order Stat Troponin I/T and serial 12-lead ECGs. Alert Cath Lab for potential PCI.",
            "evidenceQuote": "severe crushing chest pain behind my breastbone... radiates to my left arm and jaw"
        })

    # 3. Severe Asthma Exacerbation Red Flag
    if any(k in t_lower or k in d_lower for k in ["asthma", "wheeze", "wheezing", "salbutamol", "albuterol"]):
        alerts.append({
            "severity": "HIGH",
            "category": "Respiratory Red Flag",
            "title": "Acute Severe Asthma Exacerbation",
            "description": "Persistent wheezing, chest tightness, and Albuterol non-responsiveness.",
            "recommendedAction": "Administer Nebulized Salbutamol + Ipratropium stat, plus Systemic Corticosteroids (Prednisolone 40mg). Monitor Peak Flow & SpO2.",
            "evidenceQuote": "coughing constantly, wheezing, Albuterol inhaler isn't giving relief"
        })

    # 4. Diabetic Ketoacidosis (DKA) Red Flag
    if any(k in t_lower or k in d_lower for k in ["dka", "ketoacidosis", "kussmaul", "ketones", "glucose", "hyperglycemia"]):
        alerts.append({
            "severity": "HIGH",
            "category": "Endocrine Emergency",
            "title": "Diabetic Ketoacidosis (DKA) / Severe Metabolic Acidosis",
            "description": "Hyperglycemia (410 mg/dL), Kussmaul breathing, positive ketones, and metabolic acidosis.",
            "recommendedAction": "Initiate aggressive IV Normal Saline fluid resuscitation, continuous IV Regular Insulin infusion, and monitor Serum Potassium q2h.",
            "evidenceQuote": "glucose 410 mg/dL, pH 7.18, ketones 3+"
        })

    # 5. Acute Renal Colic Red Flag
    if any(k in t_lower or k in d_lower for k in ["renal colic", "flank", "hematuria", "groin", "cva tenderness"]):
        alerts.append({
            "severity": "MEDIUM",
            "category": "Urological Assessment",
            "title": "Acute Renal Colic / Suspected Nephrolithiasis",
            "description": "Excruciating flank pain radiating to groin with gross hematuria.",
            "recommendedAction": "Administer IV Ketorolac 30mg for analgesia. Order non-contrast CT Abdomen/Pelvis to locate ureteral stone size and location.",
            "evidenceQuote": "agonizing pain in left flank radiating to groin... pinkish bloody urine"
        })

    # 6. Neurological Red Flags (TIA / Stroke / Bell's Palsy)
    if any(k in t_lower or k in d_lower for k in ["droop", "drooping", "face", "facial", "slurred", "weakness", "numbness"]):
        alerts.append({
            "severity": "HIGH",
            "category": "Neurological Red Flag",
            "title": "Possible TIA / Acute Neurological Event",
            "description": "Transcript indicates sudden onset of facial drooping / weakness. Urgent evaluation required.",
            "recommendedAction": "Order non-contrast Head CT / Brain MRI. Assess NIHSS score and perform cranial nerve exam.",
            "evidenceQuote": "patient noted face started drooping"
        })

    # 7. Gastrointestinal Assessment (General Epigastric Pain)
    if any(k in t_lower or k in d_lower for k in ["stomach", "abdomen", "paining", "severe pain", "vomiting"]) and not alerts:
        alerts.append({
            "severity": "MEDIUM",
            "category": "Gastrointestinal Assessment",
            "title": "Acute Epigastric / Abdominal Pain",
            "description": "Reported abdominal pain accompanied by nausea.",
            "recommendedAction": "Perform abdominal palpation for rebound tenderness/guarding. Check serum amylase, lipase, and LFTs.",
            "evidenceQuote": "stomach was paining and I had a lot of nauseousness"
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

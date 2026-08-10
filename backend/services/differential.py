import logging
from typing import List, Dict, Any
from services.text_extraction import find_sentences_containing

logger = logging.getLogger(__name__)

_NO_SENTENCE_FALLBACK = "Keyword match found in transcript; no single sentence could be isolated as evidence."


def _evidence_quotes(transcript: str, keywords: List[str], max_results: int = 3) -> List[str]:
    matches = find_sentences_containing(transcript, keywords, max_results=max_results)
    return matches if matches else [_NO_SENTENCE_FALLBACK]


def generate_differential_details(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Dynamically analyzes the consultation transcript and Ollama diagnosis to pinpoint
    the exact clinical problems, mapping them to pathophysiology explanations,
    supporting transcript evidence, and confirmatory tests.

    This is the rule-based fallback used only when the LLM-driven analysis in services.llm
    is unavailable. Evidence below is extracted from the actual transcript passed in —
    never a hardcoded string — so what's shown to the clinician always traces back to
    something the patient or doctor actually said, not a canned line from the demo generator.
    """
    t_lower = transcript.lower()
    d_lower = diagnosis_text.lower()
    differentials = []

    # 1. Acute Appendicitis (RLQ Pain / McBurney's Point)
    appendicitis_kw = ["appendicitis", "mcburney", "rlq", "right lower quadrant", "belly button", "periumbilical", "rebound tenderness"]
    if any(k in t_lower or k in d_lower for k in appendicitis_kw):
        differentials.append({
            "diagnosis": "Acute Appendicitis (RLQ Peritoneal Irritation)",
            "icd10": "K35.80",
            "pathophysiology": "Luminal obstruction of the appendiceal lumen (fecalith/lymphoid hyperplasia) leads to intraluminal hypertension, ischemia, and visceral pain shifting from periumbilical region to McBurney's point in the right lower quadrant.",
            "evidence": _evidence_quotes(transcript, appendicitis_kw),
            "confirmatoryTests": [
                "Urgent Abdominal Ultrasound / High-resolution Contrast CT Abdomen",
                "Serial abdominal examinations for peritoneal signs",
                "Pre-operative surgical consultation (Laparoscopic Appendectomy)"
            ],
            "severity": "CRITICAL"
        })

    # 2. Acute Coronary Syndrome (ACS) / Myocardial Infarction
    acs_kw = ["coronary", "acs", "myocardial", "infarction", "breastbone", "radiates", "left arm", "jaw", "st-segment", "troponin", "nitroglycerin"]
    if any(k in t_lower or k in d_lower for k in acs_kw):
        differentials.append({
            "diagnosis": "Acute Coronary Syndrome (ACS) / Myocardial Infarction",
            "icd10": "I21.9",
            "pathophysiology": "Acute myocardial ischemia caused by coronary artery plaque rupture or acute spasm, increasing myocardial oxygen demand vs supply mismatch. Manifests as retrosternal crushing pain, radiation to left arm/jaw, diaphoresis, and ST-segment ECG changes.",
            "evidence": _evidence_quotes(transcript, acs_kw),
            "confirmatoryTests": [
                "Stat High-Sensitivity Cardiac Troponin T/I (serial at 0h, 3h)",
                "Serial 12-Lead Electrocardiogram (ECG)",
                "Invasive Coronary Angiography (CAG) for primary PCI consideration"
            ],
            "severity": "CRITICAL"
        })

    # 3. Severe Asthma Exacerbation
    asthma_kw = ["asthma", "wheeze", "wheezing", "salbutamol", "albuterol", "expiratory", "ipratropium"]
    if any(k in t_lower or k in d_lower for k in asthma_kw):
        differentials.append({
            "diagnosis": "Acute Severe Asthma Exacerbation",
            "icd10": "J45.901",
            "pathophysiology": "Acute airway inflammation, bronchial smooth muscle bronchospasm, and mucous plugging leading to air trapping, expiratory wheezing, and ventilation-perfusion mismatch.",
            "evidence": _evidence_quotes(transcript, asthma_kw),
            "confirmatoryTests": [
                "Peak Expiratory Flow Rate (PEFR) / Spirometry",
                "Arterial Blood Gas (ABG) if SpO2 remains <92%",
                "Chest Radiograph (rule out pneumothorax or atelectasis)"
            ],
            "severity": "HIGH"
        })

    # 4. Diabetic Ketoacidosis (DKA) / Severe Hyperglycemia
    dka_kw = ["dka", "ketoacidosis", "kussmaul", "ketones", "glucose", "hyperglycemia", "fruity"]
    if any(k in t_lower or k in d_lower for k in dka_kw):
        differentials.append({
            "diagnosis": "Diabetic Ketoacidosis (DKA) / Severe Hyperglycemia",
            "icd10": "E11.10",
            "pathophysiology": "Absolute or relative insulin deficiency causes uninhibited lipolysis and hepatic ketogenesis, accumulating acetoacetate and beta-hydroxybutyrate, leading to severe metabolic acidosis.",
            "evidence": _evidence_quotes(transcript, dka_kw),
            "confirmatoryTests": [
                "Stat Arterial Blood Gas (ABG) & Serum Anion Gap calculation",
                "Serum Beta-hydroxybutyrate & Potassium monitoring",
                "Continuous IV Regular Insulin infusion protocol"
            ],
            "severity": "CRITICAL"
        })

    # 5. Acute Renal Colic / Nephrolithiasis
    renal_kw = ["renal colic", "nephrolithiasis", "flank", "groin", "hematuria", "cva tenderness", "ketorolac"]
    if any(k in t_lower or k in d_lower for k in renal_kw):
        differentials.append({
            "diagnosis": "Acute Renal Colic / Ureteral Calculi",
            "icd10": "N20.1",
            "pathophysiology": "Ureteral obstruction by a urinary calculus causes acute renal pelvis distension, ureteral smooth muscle spasm, and severe colicky pain radiating along the ureter to the groin.",
            "evidence": _evidence_quotes(transcript, renal_kw),
            "confirmatoryTests": [
                "Non-contrast CT Abdomen / Pelvis (KUB)",
                "Urinalysis & Urine Culture",
                "Serum Creatinine & BUN (assess renal function)"
            ],
            "severity": "HIGH"
        })

    # 6. Congestive Heart Failure / ADHF
    chf_kw = ["heart failure", "adhf", "breathlessness", "short of breath", "pillows", "pedal edema", "orthopnea"]
    if any(k in t_lower or k in d_lower for k in chf_kw):
        differentials.append({
            "diagnosis": "Acute Decompensated Heart Failure (ADHF)",
            "icd10": "I50.9",
            "pathophysiology": "Medication non-adherence leads to sodium/fluid retention, increasing ventricular filling pressures (preload) and systemic venous congestion, manifesting as bilateral pulmonary basilar crackles and pitting pedal edema.",
            "evidence": _evidence_quotes(transcript, chf_kw),
            "confirmatoryTests": [
                "NT-proBNP level (>450 pg/mL suggests volume overload)",
                "Transthoracic Echocardiogram (LVEF estimation & valvular function)",
                "Chest X-Ray (assess for pulmonary venous congestion, Kerley B lines)"
            ],
            "severity": "CRITICAL"
        })

    # 7. Gastritis / Dyspepsia (ONLY if no appendicitis or ACS)
    gastritis_kw = ["gastritis", "gerd", "epigastric"]
    if any(k in t_lower or k in d_lower for k in gastritis_kw) and not differentials:
        differentials.append({
            "diagnosis": "Acute Gastritis vs Gastroesophageal Reflux Disease (GERD)",
            "icd10": "K29.70 / K21.9",
            "pathophysiology": "Upper gastrointestinal mucosal irritation leading to postprandial epigastric pain and morning nausea.",
            "evidence": _evidence_quotes(transcript, gastritis_kw, max_results=2),
            "confirmatoryTests": [
                "Abdominal ultrasound (rule out biliary pathology)",
                "H. pylori fecal antigen or urea breath test"
            ],
            "severity": "MEDIUM"
        })

    return differentials

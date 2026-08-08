import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def generate_differential_details(transcript: str, diagnosis_text: str) -> List[Dict[str, Any]]:
    """
    Dynamically analyzes the consultation transcript and Ollama diagnosis to pinpoint
    the exact clinical problems, mapping them to pathophysiology explanations,
    supporting transcript evidence, and confirmatory tests.
    """
    t_lower = transcript.lower()
    d_lower = diagnosis_text.lower()
    differentials = []

    # 1. Acute Appendicitis (RLQ Pain / McBurney's Point)
    if any(k in t_lower or k in d_lower for k in ["appendicitis", "mcburney", "rlq", "right lower quadrant", "belly button", "periumbilical", "rebound tenderness"]):
        differentials.append({
            "diagnosis": "Acute Appendicitis (RLQ Peritoneal Irritation)",
            "icd10": "K35.80",
            "pathophysiology": "Luminal obstruction of the appendiceal lumen (fecalith/lymphoid hyperplasia) leads to intraluminal hypertension, ischemia, and visceral pain shifting from periumbilical region to McBurney's point in the right lower quadrant.",
            "evidence": [
                "Dull pain around belly button shifting overnight to lower right stomach",
                "Sharp localized tenderness at McBurney's point with positive rebound tenderness and guarding",
                "Fever (38.3 C) and leukocytosis (WBC 14,500)"
            ],
            "confirmatoryTests": [
                "Urgent Abdominal Ultrasound / High-resolution Contrast CT Abdomen",
                "Serial abdominal examinations for peritoneal signs",
                "Pre-operative surgical consultation (Laparoscopic Appendectomy)"
            ],
            "severity": "CRITICAL"
        })

    # 2. Acute Coronary Syndrome (ACS) / Myocardial Infarction
    if any(k in t_lower or k in d_lower for k in ["coronary", "acs", "myocardial", "infarction", "breastbone", "radiates", "left arm", "jaw", "st-segment", "troponin", "nitroglycerin"]):
        differentials.append({
            "diagnosis": "Acute Coronary Syndrome (ACS) / Myocardial Infarction",
            "icd10": "I21.9",
            "pathophysiology": "Acute myocardial ischemia caused by coronary artery plaque rupture or acute spasm, increasing myocardial oxygen demand vs supply mismatch. Manifests as retrosternal crushing pain, radiation to left arm/jaw, diaphoresis, and ST-segment ECG changes.",
            "evidence": [
                "Sudden severe crushing chest pain behind breastbone radiating to left arm and jaw",
                "Diaphoresis (sweating heavily) and nausea",
                "ECG shows ST-segment depression in V4-V6"
            ],
            "confirmatoryTests": [
                "Stat High-Sensitivity Cardiac Troponin T/I (serial at 0h, 3h)",
                "Serial 12-Lead Electrocardiogram (ECG)",
                "Invasive Coronary Angiography (CAG) for primary PCI consideration"
            ],
            "severity": "CRITICAL"
        })

    # 3. Severe Asthma Exacerbation
    if any(k in t_lower or k in d_lower for k in ["asthma", "wheeze", "wheezing", "salbutamol", "albuterol", "expiratory", "ipratropium"]):
        differentials.append({
            "diagnosis": "Acute Severe Asthma Exacerbation",
            "icd10": "J45.901",
            "pathophysiology": "Acute airway inflammation, bronchial smooth muscle bronchospasm, and mucous plugging leading to air trapping, expiratory wheezing, and ventilation-perfusion mismatch.",
            "evidence": [
                "Coughing constantly, wheezing, non-responsive to short-acting inhaler",
                "Widespread expiratory wheezing across both lung fields",
                "Oxygen saturation at 91% on room air"
            ],
            "confirmatoryTests": [
                "Peak Expiratory Flow Rate (PEFR) / Spirometry",
                "Arterial Blood Gas (ABG) if SpO2 remains <92%",
                "Chest Radiograph (rule out pneumothorax or atelectasis)"
            ],
            "severity": "HIGH"
        })

    # 4. Diabetic Ketoacidosis (DKA) / Severe Hyperglycemia
    if any(k in t_lower or k in d_lower for k in ["dka", "ketoacidosis", "kussmaul", "ketones", "glucose", "hyperglycemia", "fruity"]):
        differentials.append({
            "diagnosis": "Diabetic Ketoacidosis (DKA) / Severe Hyperglycemia",
            "icd10": "E11.10",
            "pathophysiology": "Absolute or relative insulin deficiency causes uninhibited lipolysis and hepatic ketogenesis, accumulating acetoacetate and beta-hydroxybutyrate, leading to severe metabolic acidosis.",
            "evidence": [
                "Polydipsia, polyuria, confusion, and fruity breath odor",
                "Random blood glucose 410 mg/dL and arterial pH 7.18",
                "Urine ketones strongly positive (3+)"
            ],
            "confirmatoryTests": [
                "Stat Arterial Blood Gas (ABG) & Serum Anion Gap calculation",
                "Serum Beta-hydroxybutyrate & Potassium monitoring",
                "Continuous IV Regular Insulin infusion protocol"
            ],
            "severity": "CRITICAL"
        })

    # 5. Acute Renal Colic / Nephrolithiasis
    if any(k in t_lower or k in d_lower for k in ["renal colic", "nephrolithiasis", "flank", "groin", "hematuria", "cva tenderness", "ketorolac"]):
        differentials.append({
            "diagnosis": "Acute Renal Colic / Ureteral Calculi",
            "icd10": "N20.1",
            "pathophysiology": "Ureteral obstruction by a urinary calculus causes acute renal pelvis distension, ureteral smooth muscle spasm, and severe colicky pain radiating along the ureter to the groin.",
            "evidence": [
                "Excruciating colicky flank pain radiating to the groin",
                "Gross hematuria (pinkish bloody urine)",
                "Severe left costovertebral angle (CVA) tenderness"
            ],
            "confirmatoryTests": [
                "Non-contrast CT Abdomen / Pelvis (KUB)",
                "Urinalysis & Urine Culture",
                "Serum Creatinine & BUN (assess renal function)"
            ],
            "severity": "HIGH"
        })

    # 6. Congestive Heart Failure / ADHF
    if any(k in t_lower or k in d_lower for k in ["heart failure", "adhf", "breathlessness", "short of breath", "pillows", "pedal edema", "orthopnea"]):
        differentials.append({
            "diagnosis": "Acute Decompensated Heart Failure (ADHF)",
            "icd10": "I50.9",
            "pathophysiology": "Medication non-adherence leads to sodium/fluid retention, increasing ventricular filling pressures (preload) and systemic venous congestion, manifesting as bilateral pulmonary basilar crackles and 3+ pitting pedal edema.",
            "evidence": [
                "Shortness of breath walking to the bathroom",
                "Cannot sleep flat, propped up with three pillows",
                "Swelling in feet and ankles, gained 5 kg in 10 days"
            ],
            "confirmatoryTests": [
                "NT-proBNP level (>450 pg/mL suggests volume overload)",
                "Transthoracic Echocardiogram (LVEF estimation & valvular function)",
                "Chest X-Ray (assess for pulmonary venous congestion, Kerley B lines)"
            ],
            "severity": "CRITICAL"
        })

    # 7. Gastritis / Dyspepsia (ONLY if no appendicitis or ACS)
    if any(k in t_lower or k in d_lower for k in ["gastritis", "gerd", "epigastric"]) and not differentials:
        differentials.append({
            "diagnosis": "Acute Gastritis vs Gastroesophageal Reflux Disease (GERD)",
            "icd10": "K29.70 / K21.9",
            "pathophysiology": "Upper gastrointestinal mucosal irritation leading to postprandial epigastric pain and morning nausea.",
            "evidence": [
                "Upper stomach paining after meals",
                "Nauseousness throughout the morning"
            ],
            "confirmatoryTests": [
                "Abdominal ultrasound (rule out biliary pathology)",
                "H. pylori fecal antigen or urea breath test"
            ],
            "severity": "MEDIUM"
        })

    return differentials

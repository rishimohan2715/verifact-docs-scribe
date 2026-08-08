import random
import uuid
from typing import Dict, Any, List

FIRST_NAMES = ["Aarav", "Priya", "Rahul", "Ananya", "Rohan", "Sneha", "Vikram", "Kavya", "Aditya", "Neha", "Siddharth", "Meera", "Karan", "Pooja", "Arjun", "Divya"]
LAST_NAMES = ["Sharma", "Patel", "Verma", "Rao", "Banerjee", "Krishnan", "Malhotra", "Gupta", "Deshmukh", "Nair", "Joshi", "Iyer"]

MEDICAL_HISTORIES = [
    "Essential Hypertension, Type 2 Diabetes",
    "Bronchial Asthma, Allergic Rhinitis",
    "Hypertension, Hyperlipidemia, CAD",
    "Chronic Kidney Disease Stage III",
    "Type 1 Diabetes Mellitus",
    "No prior chronic medical illnesses",
    "Recurrent Nephrolithiasis",
    "Congestive Heart Failure (HFrEF)"
]

# Detailed Multi-Turn Doctor-Patient Clinical Interview Packages
MULTI_TURN_CLINICAL_PACKAGES = [
    {
        "category": "Acute Coronary Syndrome (ACS)",
        "chief_symptom": "crushing retrosternal chest pressure",
        "q_onset": "About 45 minutes ago while sitting at my desk.",
        "q_severity": "It's an 8 out of 10 heavy crushing pressure, shooting down my left arm and lower jaw.",
        "q_assoc": "I'm sweating profusely—my shirt is drenched—and I feel very dizzy and nauseous.",
        "q_meds": "I have high blood pressure and cholesterol, but I haven't taken my pills for the last two weeks because I ran out.",
        "doctor_exam": "BP is high at 158/94 mmHg, HR 104 bpm, SpO2 95% on room air. 12-lead ECG demonstrates 2mm ST-segment depression in leads V4 to V6 with T-wave inversions.",
        "doctor_plan": "We are administering 325mg chewable Aspirin, placing Sublingual Nitroglycerin under your tongue, drawing Stat Cardiac Troponin T levels, and moving you to Cardiology telemetry."
    },
    {
        "category": "Acute Appendicitis",
        "chief_symptom": "stomach pain around belly button that moved to lower right side",
        "q_onset": "Yesterday morning it was a dull ache around my navel, but overnight it shifted to the lower right belly.",
        "q_severity": "It's a sharp 9 out of 10 pain right in that lower right spot. Every step I walk or cough makes it hurt unbearable.",
        "q_assoc": "I vomited twice this morning, feel feverish and warm, and have zero appetite.",
        "q_meds": "No prior medical conditions and I'm not taking any regular medications.",
        "doctor_exam": "Temperature is 38.4 C. Palpation of right lower quadrant demonstrates sharp McBurney's point tenderness with positive rebound tenderness and guarding. WBC count is 14,800.",
        "doctor_plan": "We are placing you on strict NPO status, starting IV fluids, ordering stat Abdominal Ultrasound and CT scan, and requesting an urgent general surgery consult."
    },
    {
        "category": "Diabetic Ketoacidosis (DKA)",
        "chief_symptom": "unquenchable thirst, extreme fatigue, and rapid breathing",
        "q_onset": "For four days I've been drinking liters of water non-stop and peeing every 20 minutes.",
        "q_severity": "I feel extremely weak, dizzy, confused, and my stomach feels sick.",
        "q_assoc": "I've been vomiting since yesterday, and my breathing feels very deep and fast.",
        "q_meds": "I have Type 1 Diabetes but I ran out of my Insulin glargine three days ago.",
        "doctor_exam": "Respirations are 28 breaths/min with Kussmaul pattern and fruity breath odor. Blood glucose is 425 mg/dL, arterial pH is 7.16, and urine ketones are 3+ positive.",
        "doctor_plan": "We are starting aggressive IV normal saline fluid rehydration, a continuous intravenous Regular Insulin infusion drip, and admitting you to the ICU."
    },
    {
        "category": "Severe Asthma Exacerbation",
        "chief_symptom": "progressive breathlessness and tightness in chest",
        "q_onset": "Started 3 days ago after I caught a mild cold, and got worse last night.",
        "q_severity": "I feel like I'm suffocating or breathing through a tiny straw. I can't even speak in full sentences.",
        "q_assoc": "Constant coughing fits and loud wheezing when I exhale.",
        "q_meds": "I have asthma and I've been using my blue Albuterol rescue inhaler every 45 minutes, but it's not helping anymore.",
        "doctor_exam": "SpO2 is 90% on room air. Auscultation reveals widespread, high-pitched expiratory wheezing across both lung fields.",
        "doctor_plan": "We are administering nebulized Salbutamol and Ipratropium stat, starting 2L nasal cannula oxygen, and giving oral Prednisolone 40mg."
    },
    {
        "category": "Acute Renal Colic (Kidney Stone)",
        "chief_symptom": "excruciating left back and flank pain radiating to groin",
        "q_onset": "Came on suddenly 2 hours ago while I was driving.",
        "q_severity": "It's an agonizing 10 out of 10 cramping pain in my left lower back shooting straight into my groin. I can't sit still.",
        "q_assoc": "I went to the bathroom and my urine was pinkish-red with blood. I threw up from the pain.",
        "q_meds": "I had a kidney stone 2 years ago, but no other regular medications.",
        "doctor_exam": "Left costovertebral angle (CVA) percussion elicits severe pain and flinching. Urinalysis confirms gross hematuria.",
        "doctor_plan": "We are administering IV Ketorolac 30mg stat for pain and ordering a non-contrast CT KUB scan of your abdomen and pelvis."
    }
]

def generate_random_case_payload() -> Dict[str, Any]:
  """
  STRESS-TEST MULTI-TURN CLINICAL INTERVIEW GENERATOR:
  Generates a 10-turn doctor-patient clinical interview where the doctor asks basic
  history questions, and the AI infers the diagnosis, pathophysiology, ICD-10, and Rx.
  """
  first_name = random.choice(FIRST_NAMES)
  last_name = random.choice(LAST_NAMES)
  patient_name = f"{first_name} {last_name}"
  
  mrn = f"MRN-{random.randint(10000, 99999)}-{random.randint(100, 999)}"
  age = random.randint(21, 79)
  pmh = random.choice(MEDICAL_HISTORIES)
  
  pkg = random.choice(MULTI_TURN_CLINICAL_PACKAGES)

  # 10-turn natural clinical interview
  dialogue = [
    ("DOCTOR", f"Good afternoon {first_name}, I'm Dr. Raman. You are {age} years old with a history of {pmh}. What brings you in today?"),
    ("PATIENT", f"Doctor, I'm experiencing severe {pkg['chief_symptom']}."),
    ("DOCTOR", "When exactly did this start, and what were you doing when it began?"),
    ("PATIENT", pkg["q_onset"]),
    ("DOCTOR", "On a scale of 1 to 10, how severe is the pain, and does it radiate anywhere else?"),
    ("PATIENT", pkg["q_severity"]),
    ("DOCTOR", "Have you noticed any associated symptoms like nausea, sweating, fever, or changes in your breathing or urination?"),
    ("PATIENT", pkg["q_assoc"]),
    ("DOCTOR", "Are you taking your prescribed daily medications regularly, or have you missed any doses recently?"),
    ("PATIENT", pkg["q_meds"]),
    ("DOCTOR", "Thank you. Let me perform a physical examination and inspect your vital signs and lab results."),
    ("DOCTOR", f"Physical examination findings: {pkg['doctor_exam']}"),
    ("PATIENT", "What do those test results mean doctor? What is the treatment plan?"),
    ("DOCTOR", f"Here is our immediate clinical plan: {pkg['doctor_plan']}")
  ]

  transcript_lines = []
  segments = []
  time_sec = 0

  for spk, text in dialogue:
    min_val = time_sec // 60
    sec_val = time_sec % 60
    time_str = f"{min_val:02d}:{sec_val:02d}"

    duration = max(4, min(16, len(text) // 10))

    segments.append({
      "speaker": spk,
      "text": text,
      "start": float(time_sec),
      "end": float(time_sec + duration),
      "time": time_str
    })
    transcript_lines.append(f"{spk}: {text}")
    time_sec += duration + 2

  full_transcript = " ".join([s["text"] for s in segments])

  return {
    "patient_name": patient_name,
    "mrn": mrn,
    "age": age,
    "pmh": pmh,
    "consult_type": "Discharge Summary" if random.random() > 0.3 else "OPD Note",
    "scenario_title": f"10-Turn Q&A: {pkg['category']} ({patient_name})",
    "full_transcript": full_transcript,
    "segments": segments
  }

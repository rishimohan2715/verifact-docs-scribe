import os
import json
import re
import logging
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field, ValidationError
from services.text_extraction import split_sentences

logger = logging.getLogger(__name__)

# Small local models often "helpfully" return a structured field (e.g. diagnosis as a
# numbered list of dicts) instead of the plain string the prompt asked for. Accepting
# either shape here — instead of rejecting the whole response — lets _format_sections'
# existing list/dict-to-string flattening handle it, rather than discarding an otherwise
# well-formed response and falling back over a formatting quirk.
NoteFieldValue = Union[str, List[Any], Dict[str, Any]]

# ─── Pydantic Schema for Structured Note + Risk/Differential Validation ───────

class ClinicalNoteSchema(BaseModel):
    chiefComplaint: NoteFieldValue = Field(..., description="Primary symptom, onset, and chief clinical complaint")
    hpi: NoteFieldValue = Field(..., description="Comprehensive History of Present Illness summarizing symptoms, timeline, medication adherence, and prior medical history")
    examination: NoteFieldValue = Field(..., description="Objective physical examination findings, vital signs (BP, HR, SpO2, Temp), and physical exam findings")
    diagnosis: NoteFieldValue = Field(..., description="Numbered list of primary and secondary clinical diagnoses with inferred medical etiology")
    treatment: NoteFieldValue = Field(..., description="Inpatient/outpatient management plan, emergency medications, dosages, routes, and diagnostic orders")
    followUp: NoteFieldValue = Field(..., description="Follow-up timeline, outpatient clinic appointments, specialist referrals, and warning signs to return to ER")


class RiskAlertSchema(BaseModel):
    severity: Literal["HIGH", "MEDIUM", "LOW"]
    category: str
    title: str
    description: str
    recommendedAction: str
    evidenceQuote: str = Field(..., description="A verbatim substring copied exactly from the transcript")


class DifferentialSchema(BaseModel):
    diagnosis: str
    icd10: Optional[str] = None
    pathophysiology: str
    evidence: List[str] = Field(..., description="Verbatim substrings copied exactly from the transcript")
    confirmatoryTests: List[str] = []
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


class ClinicalAnalysisSchema(BaseModel):
    note: ClinicalNoteSchema
    riskAlerts: List[RiskAlertSchema] = []
    differentials: List[DifferentialSchema] = []


_CACHED_OLLAMA_MODEL = None

def _get_available_ollama_model() -> str:
    """
    Checks running Ollama models ONCE and caches the result globally.
    Prefers medgemma -> llama3.2:3b -> llama3:latest -> llama3.1:latest -> mistral.
    """
    global _CACHED_OLLAMA_MODEL
    if _CACHED_OLLAMA_MODEL:
        return _CACHED_OLLAMA_MODEL

    preferred = ["medgemma", "llama3.2:3b", "llama3:latest", "llama3.1:latest", "llama3", "mistral"]
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                models = [m.get("name", "") for m in data.get("models", [])]
                for pref in preferred:
                    for m in models:
                        if pref in m.lower():
                            logger.info(f"Selected and cached Ollama model: {m}")
                            _CACHED_OLLAMA_MODEL = m
                            return m
                if models:
                    _CACHED_OLLAMA_MODEL = models[0]
                    return _CACHED_OLLAMA_MODEL
    except Exception as e:
        logger.info(f"Could not query Ollama tags API: {e}")

    _CACHED_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    return _CACHED_OLLAMA_MODEL


def _get_ollama_timeout_seconds() -> float:
    """
    Real local models need real time to generate a combined note+risk+differential
    JSON response. Configurable per-machine via OLLAMA_TIMEOUT_SECONDS; defaults to
    a budget generous enough for a 3-8B model on CPU, not the previous 1.5-4s which
    made the LLM path fail almost every time regardless of accuracy.
    """
    return float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))


# Ollama (0.5+) supports passing an actual JSON Schema as `format` instead of just the
# string "json", which constrains decoding at the grammar level rather than hoping the
# model follows prose instructions. This is what actually stops a small model from
# flattening "note" fields to the top level or emitting diagnosis as a list — the model
# is structurally unable to produce anything else. Hand-written rather than derived from
# the (deliberately loose) Pydantic schema below, since the loose Union types there exist
# as a tolerance fallback for when schema-constrained decoding isn't honored.
_OLLAMA_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "note": {
            "type": "object",
            "properties": {
                "chiefComplaint": {"type": "string"},
                "hpi": {"type": "string"},
                "examination": {"type": "string"},
                "diagnosis": {"type": "string"},
                "treatment": {"type": "string"},
                "followUp": {"type": "string"},
            },
            "required": ["chiefComplaint", "hpi", "examination", "diagnosis", "treatment", "followUp"],
        },
        "riskAlerts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "category": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "recommendedAction": {"type": "string"},
                    "evidenceQuote": {"type": "string"},
                },
                "required": ["severity", "category", "title", "description", "recommendedAction", "evidenceQuote"],
            },
        },
        "differentials": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "diagnosis": {"type": "string"},
                    "icd10": {"type": "string"},
                    "pathophysiology": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "confirmatoryTests": {"type": "array", "items": {"type": "string"}},
                    "severity": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
                },
                "required": ["diagnosis", "pathophysiology", "evidence", "severity"],
            },
        },
    },
    "required": ["note", "riskAlerts", "differentials"],
}


def _call_ollama_with_timeout(model_name: str, prompt: str, timeout_seconds: Optional[float] = None) -> Optional[str]:
    """
    Direct non-blocking HTTP call to local Ollama API, using schema-constrained decoding
    so the response structurally matches _OLLAMA_RESPONSE_SCHEMA.
    """
    import urllib.request
    import urllib.error

    if timeout_seconds is None:
        timeout_seconds = _get_ollama_timeout_seconds()

    url = "http://localhost:11434/api/generate"
    payload = json.dumps({
        "model": model_name,
        "prompt": prompt,
        "format": _OLLAMA_RESPONSE_SCHEMA,
        "stream": False,
        "options": {
            "temperature": 0.1,
            # A combined note+risk+differential JSON response needs real headroom —
            # the previous 300-token cap silently truncated valid responses mid-object,
            # which failed json.loads and fell back regardless of how long the timeout was.
            # 1800 still wasn't always enough for longer transcripts to reach the trailing
            # fields (diagnosis/treatment/followUp) before running out of budget.
            "num_predict": 3000,
            "top_p": 0.9
        }
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status == 200:
                resp_data = json.loads(response.read().decode("utf-8"))
                return resp_data.get("response", "")
    except Exception as e:
        logger.info(f"Ollama local API offline or timed out ({e}). Engaging extractive fallback.")
        return None


def _verify_quote(quote: str, transcript: str) -> bool:
    """
    Whitespace/case-normalized substring check — the transcript is the ground truth.
    An LLM-supplied evidence quote is only trustworthy if it's actually present in the
    text the model was given, not a paraphrase or a plausible-sounding invention.
    """
    norm_q = re.sub(r"\s+", " ", quote.strip().lower())
    norm_t = re.sub(r"\s+", " ", transcript.lower())
    return bool(norm_q) and norm_q in norm_t


def _filter_verified_alerts(alerts: List[Dict[str, Any]], transcript: str) -> List[Dict[str, Any]]:
    return [a for a in alerts if _verify_quote(a.get("evidenceQuote", ""), transcript)]


def _filter_verified_differentials(diffs: List[Dict[str, Any]], transcript: str) -> List[Dict[str, Any]]:
    out = []
    for d in diffs:
        verified_evidence = [q for q in d.get("evidence", []) if _verify_quote(q, transcript)]
        if verified_evidence:
            out.append({**d, "evidence": verified_evidence})
    return out


# Seen in practice: a small local model, when confused, echoes these field-explanation
# phrases back verbatim as if they were the actual clinical content instead of writing
# real content for the patient. A response doing this passes Pydantic's type check (it's
# still a string) but is clinically useless, so it's checked for separately.
_SCHEMA_ECHO_PHRASES = (
    "primary symptom, its onset, and why the patient is here today",
    "narrative history of present illness covering symptoms, timeline",
    "objective exam findings and vital signs actually mentioned or implied",
    "numbered list of likely diagnoses with brief etiology",
    "the management plan",
    "follow-up timeline and explicit warning signs to return",
)


def _looks_like_schema_echo(note_fields: Dict[str, Any]) -> bool:
    for value in note_fields.values():
        text = str(value).strip().lower()
        if any(phrase in text for phrase in _SCHEMA_ECHO_PHRASES):
            return True
    return False


def generate_clinical_note(redacted_transcript: str, template_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates a structured clinical discharge summary, risk alerts, and differential
    diagnoses in a single local Ollama call. Every risk/differential evidence quote is
    verified as a verbatim substring of the transcript before being trusted; anything
    that doesn't verify is dropped rather than shown to the clinician. Falls back to a
    generic extractive summarizer (never a hardcoded disease guess) if Ollama is
    unavailable or its output fails validation.
    """
    model_name = _get_available_ollama_model()
    prompt_version = "v2.0.0"

    base_prompt = f"""You are an expert Clinical Documentation System.
Analyze the transcript below and write a real clinical note about THIS specific patient,
in their words and findings — never copy the field explanations as if they were the answer.

Fields to fill in "note":
- chiefComplaint: the primary symptom, its onset, and why the patient is here today
- hpi: a narrative History of Present Illness covering symptoms, timeline, medication adherence, prior history
- examination: objective exam findings and vital signs actually mentioned or implied
- diagnosis: a numbered list of likely diagnoses with brief etiology, as plain text (not an array of objects)
- treatment: the management plan — medications, dosages, routes, diagnostic orders
- followUp: follow-up timeline and explicit warning signs to return

riskAlerts (list, can be empty): urgent red flags actually supported by the transcript.
Each item needs severity (HIGH|MEDIUM|LOW), category, title, description, recommendedAction,
and evidenceQuote — a short quote copied VERBATIM, character-for-character, from the transcript.

differentials (list, can be empty): candidate diagnoses actually supported by the transcript.
Each item needs diagnosis, icd10 (omit if unsure), pathophysiology, evidence (list of verbatim
quotes from the transcript), confirmatoryTests (list), and severity (CRITICAL|HIGH|MEDIUM|LOW).

Example of the JSON shape, filled with REAL example content for an unrelated patient (write
your own content for the transcript below — do not reuse any of this example's wording):
{{
  "note": {{
    "chiefComplaint": "Patient presents with a 2-day history of fever and sore throat.",
    "hpi": "Fever up to 101F for 2 days with painful swallowing, no cough.",
    "examination": "Temp 38.1C, pharyngeal erythema, no exudate noted.",
    "diagnosis": "1. Acute pharyngitis, likely viral",
    "treatment": "Supportive care, warm saline gargles, paracetamol for fever",
    "followUp": "Return if fever persists beyond 5 days or breathing becomes difficult"
  }},
  "riskAlerts": [],
  "differentials": []
}}

Every evidenceQuote/evidence string MUST be copied verbatim from the transcript below —
do not paraphrase, summarize, or invent a quote. It is fine to return empty riskAlerts/
differentials lists if nothing in the transcript actually supports one.

Transcript:
{redacted_transcript}

Respond STRICTLY with valid JSON in the shape shown above, filled in for this patient."""

    try:
        raw_output = _call_ollama_with_timeout(model_name, base_prompt)

        if raw_output:
            try:
                parsed_json = json.loads(raw_output)
                validated = ClinicalAnalysisSchema(**parsed_json)

                note_fields = validated.note.model_dump()
                if _looks_like_schema_echo(note_fields):
                    logger.warning("Model echoed field explanations instead of real content. Using extractive fallback.")
                    return _extractive_fallback_note_generator(redacted_transcript)

                sections = _format_sections(note_fields)
                structured_text = _build_structured_text(sections)

                verified_alerts = _filter_verified_alerts(
                    [a.model_dump() for a in validated.riskAlerts], redacted_transcript
                )
                verified_differentials = _filter_verified_differentials(
                    [d.model_dump() for d in validated.differentials], redacted_transcript
                )
                verified_alerts = [_humanize_alert(a) for a in verified_alerts]
                verified_differentials = [_humanize_differential(d) for d in verified_differentials]

                return {
                    "structured_note": structured_text,
                    "sections": sections,
                    "riskAlerts": verified_alerts,
                    "differentials": verified_differentials,
                    "llm_model": model_name,
                    "prompt_version": prompt_version,
                    "status": "success"
                }
            except (json.JSONDecodeError, ValidationError) as err:
                logger.warning(f"JSON validation error: {err}. Using extractive fallback.")

        logger.info("Engaging extractive fallback note generator...")
        return _extractive_fallback_note_generator(redacted_transcript)

    except Exception as e:
        logger.warning(f"Note generation exception ({e}). Using extractive fallback.")
        return _extractive_fallback_note_generator(redacted_transcript)


_PII_PLACEHOLDER_TEXT = {
    "<PERSON>": "the patient",
    "<DATE_TIME>": "the reported time",
    "<LOCATION>": "the reported location",
    "<PHONE_NUMBER>": "[phone redacted]",
    "<EMAIL_ADDRESS>": "[email redacted]",
}


def _humanize_pii_placeholders(text: str) -> str:
    for placeholder, replacement in _PII_PLACEHOLDER_TEXT.items():
        text = text.replace(placeholder, replacement)
    return text


def _humanize_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    alert["evidenceQuote"] = _humanize_pii_placeholders(alert.get("evidenceQuote", ""))
    return alert


_LEADING_LIST_NUMBER = re.compile(r"^\s*\d+[.)]\s*")


def _humanize_differential(diff: Dict[str, Any]) -> Dict[str, Any]:
    diff["evidence"] = [_humanize_pii_placeholders(q) for q in diff.get("evidence", [])]
    # Some models echo the numbered-list formatting they used for the note's diagnosis
    # field into the differential's own diagnosis name (e.g. "2. Asthma exacerbation").
    diff["diagnosis"] = _LEADING_LIST_NUMBER.sub("", diff.get("diagnosis", ""))
    return diff


def _format_sections(data: Dict[str, Any]) -> Dict[str, str]:
    required_keys = ["chiefComplaint", "hpi", "examination", "diagnosis", "treatment", "followUp"]
    result = {}
    for key in required_keys:
        val = data.get(key, "")

        if isinstance(val, list):
            lines = []
            for item in val:
                if isinstance(item, dict):
                    desc = item.get("description") or item.get("name") or item.get("medication") or item.get("test") or item.get("appointment") or str(item)
                    etiology = item.get("etiology") or item.get("dosage") or item.get("description")
                    if etiology and etiology != desc:
                        lines.append(f"- {desc}: {etiology}")
                    else:
                        lines.append(f"- {desc}")
                else:
                    lines.append(f"- {str(item)}")
            val = "\n".join(lines)
        elif isinstance(val, dict):
            lines = []
            for k, v in val.items():
                if isinstance(v, dict):
                    v_str = ", ".join([f"{sub_k}: {sub_v}" for sub_k, sub_v in v.items()])
                    lines.append(f"- {k}: {v_str}")
                else:
                    lines.append(f"- {k}: {v}")
            val = "\n".join(lines)

        val_str = str(val).strip()
        val_str = _humanize_pii_placeholders(val_str)
        val_str = re.sub(r"\{'number':.*\}", "", val_str)

        result[key] = val_str or "No specific details recorded in transcript."
    return result


def _build_structured_text(sections: Dict[str, str]) -> str:
    labels = {
        "chiefComplaint": "Chief Complaint",
        "hpi": "History of Present Illness",
        "examination": "Examination Findings",
        "diagnosis": "Diagnosis",
        "treatment": "Treatment / Plan",
        "followUp": "Follow-up"
    }
    blocks = []
    for k, label in labels.items():
        val = sections.get(k, "")
        blocks.append(f"## {label}\n{val}")
    return "\n\n".join(blocks)


# Reused from services.transcription's speaker-attribution heuristic: the clinician asks
# questions, the patient reports symptoms (often elliptically, with no "I" at all — "Cramping
# mostly and a lot of bloating" is a complete patient answer with no self-reference). Rather
# than requiring an explicit patient marker to include a sentence, default to including any
# non-question sentence UNLESS it's phrased like the clinician's side of the conversation —
# the same "no cue keeps the current speaker" logic transcription.py uses for turn attribution.
_FIRST_PERSON_MARKERS = (
    "i'm ", "i've ", "i'd ", "i feel", "i felt", "i have", "i had", "i get", "i stay",
    "i can't", "i cannot", "i was", "my ", "i don't", "i do ",
)
_DOCTOR_PHRASE_MARKERS = (
    "tell me", "let me", "we are", "we will", "on a scale", "examination",
    "alright", "all right", "good morning", "good afternoon", "good evening",
    "what brings", "what kind of", "what's your name", "why are you here",
)
_MEDICATION_PATTERN = re.compile(r"\b\d+\s?(mg|mcg|units|iu|ml)\b", re.IGNORECASE)
_VITALS_PATTERN = re.compile(
    r"(\d{2,3}\s?/\s?\d{2,3})|spo2|blood pressure|heart rate|\bbpm\b|\btemp\b|°\s?[cf]\b",
    re.IGNORECASE,
)


def _is_patient_sourced(sentence: str) -> bool:
    lowered = f" {sentence.lower()} "
    return any(marker in lowered for marker in _FIRST_PERSON_MARKERS)


def _is_doctor_phrased(sentence: str) -> bool:
    lowered = sentence.lower()
    return any(marker in lowered for marker in _DOCTOR_PHRASE_MARKERS)


def _extractive_fallback_note_generator(transcript: str, status: str = "extracted_fallback") -> Dict[str, Any]:
    """
    Generic, non-diagnostic fallback used when the local LLM is unavailable or its
    output fails validation (status="extracted_fallback"), or intentionally skipped for
    speed on synthetic demo transcripts (status="demo_fast_extract" — see
    generate_clinical_note_fast). Builds an HPI from the transcript's own sentences by
    default-including everything that isn't clearly the clinician's side of the
    conversation (a question, or phrased like one of the doctor's stock lines) — this
    matters because real patient answers are often elliptical ("Cramping mostly and a lot
    of bloating") with no first-person pronoun to key off of. This works on any real
    transcript instead of only the handful of scripted disease scenarios the old version
    recognized, and never falls through to dumping the raw transcript. It deliberately
    does not guess a diagnosis or treatment plan: fabricating those from keyword matches
    is exactly the kind of unverified claim this fallback exists to avoid.
    """
    sentences = split_sentences(transcript)

    hpi_sentences: List[str] = []
    exam_sentences: List[str] = []
    first_patient_sentence: Optional[str] = None

    for sentence in sentences:
        is_question = sentence.strip().endswith("?")
        is_patient = _is_patient_sourced(sentence)
        is_vitals = bool(_VITALS_PATTERN.search(sentence))

        if is_patient and first_patient_sentence is None:
            first_patient_sentence = sentence

        if is_vitals:
            exam_sentences.append(sentence)
        elif not is_question and not _is_doctor_phrased(sentence):
            hpi_sentences.append(sentence)

    chief_source = first_patient_sentence or (sentences[0] if sentences else "")
    chief_complaint = f"Patient reports: {chief_source}" if chief_source else "No chief complaint could be extracted from the transcript."

    hpi = " ".join(hpi_sentences) if hpi_sentences else "No detailed history could be extracted from the transcript. Clinician must complete HPI directly from the recording/transcript."
    examination = "\n".join(exam_sentences) if exam_sentences else "No objective examination findings could be extracted from the transcript. Clinician must complete on physical exam."

    diagnosis = "Auto-extraction mode: differential diagnosis not generated. The local AI model was unavailable — clinician must determine diagnosis directly from the transcript and history above."
    treatment = "Auto-extraction mode: treatment plan not generated. The local AI model was unavailable — clinician must enter the management plan directly."
    followUp = "Auto-extraction mode: follow-up plan not generated. The local AI model was unavailable — clinician must enter follow-up instructions directly."

    sections = {
        "chiefComplaint": _humanize_pii_placeholders(chief_complaint),
        "hpi": _humanize_pii_placeholders(hpi),
        "examination": _humanize_pii_placeholders(examination),
        "diagnosis": diagnosis,
        "treatment": treatment,
        "followUp": followUp,
    }

    return {
        "structured_note": _build_structured_text(sections),
        "sections": sections,
        "riskAlerts": [],
        "differentials": [],
        "llm_model": "extractive-fallback",
        "prompt_version": "v2.0.0-fallback",
        "status": status
    }


def generate_clinical_note_fast(redacted_transcript: str, template_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Ultra-fast clinical note generation that SKIPS Ollama entirely.
    Uses the extractive fallback generator (< 0.1 seconds).
    Use this for demo/random-case endpoints where speed is critical and the transcript
    is already synthetic/scripted — status is "demo_fast_extract" rather than
    "extracted_fallback" since the LLM wasn't unavailable, it was intentionally skipped.
    """
    return _extractive_fallback_note_generator(redacted_transcript, status="demo_fast_extract")

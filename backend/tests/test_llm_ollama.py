"""
Tests for services.llm.generate_clinical_note against a mocked Ollama HTTP call.

Context: the real bug this module fixes was a 1.5-4s Ollama timeout that made the LLM
path fail almost every time, falling back to a 5-disease keyword matcher that dumped the
raw transcript for anything else. These tests mock _call_ollama_with_timeout directly so
no real Ollama process or model weights are needed.
"""
import json
from unittest.mock import patch

from services.llm import generate_clinical_note

TRANSCRIPT = (
    "Doctor, I've been having crampy pain in my lower belly and a lot of bloating "
    "for about a week. How long have you had this? It comes and goes, and I also "
    "have loose motions sometimes."
)

WELL_FORMED_OLLAMA_RESPONSE = json.dumps({
    "note": {
        "chiefComplaint": "Patient reports crampy lower abdominal pain and bloating for one week.",
        "hpi": "Intermittent crampy lower abdominal pain with bloating and occasional loose motions for one week.",
        "examination": "Abdomen soft, mild diffuse tenderness, no rebound or guarding.",
        "diagnosis": "1. Irritable bowel syndrome, clinical diagnosis pending workup",
        "treatment": "Dietary modification, antispasmodic as needed",
        "followUp": "Review in 2 weeks or sooner if symptoms worsen",
    },
    "riskAlerts": [
        {
            "severity": "LOW",
            "category": "Gastrointestinal Assessment",
            "title": "Intermittent Abdominal Cramping",
            "description": "Reported cramping and bloating.",
            "recommendedAction": "Routine follow-up, no acute intervention needed.",
            "evidenceQuote": "I've been having crampy pain in my lower belly and a lot of bloating",
        }
    ],
    "differentials": [
        {
            "diagnosis": "Irritable bowel syndrome",
            "icd10": "K58.9",
            "pathophysiology": "Altered gut motility and visceral hypersensitivity.",
            "evidence": ["It comes and goes, and I also have loose motions sometimes."],
            "confirmatoryTests": ["Stool studies to exclude infection"],
            "severity": "LOW",
        }
    ],
})


def test_ollama_success_returns_verified_sections_and_alerts():
    with patch("services.llm._call_ollama_with_timeout", return_value=WELL_FORMED_OLLAMA_RESPONSE):
        result = generate_clinical_note(TRANSCRIPT, {})

    assert result["status"] == "success"
    assert "bloating" in result["sections"]["hpi"].lower()
    assert len(result["riskAlerts"]) == 1
    assert len(result["differentials"]) == 1
    assert result["riskAlerts"][0]["evidenceQuote"] in TRANSCRIPT


def test_ollama_unavailable_falls_back_without_crashing():
    with patch("services.llm._call_ollama_with_timeout", return_value=None):
        result = generate_clinical_note(TRANSCRIPT, {})

    assert result["status"] == "extracted_fallback"
    assert result["riskAlerts"] == []
    assert result["differentials"] == []


def test_malformed_json_from_ollama_falls_back_without_crashing():
    with patch("services.llm._call_ollama_with_timeout", return_value="not valid json {{{"):
        result = generate_clinical_note(TRANSCRIPT, {})

    assert result["status"] == "extracted_fallback"


def test_ollama_response_missing_required_fields_falls_back():
    incomplete = json.dumps({"note": {"chiefComplaint": "Only this field"}})
    with patch("services.llm._call_ollama_with_timeout", return_value=incomplete):
        result = generate_clinical_note(TRANSCRIPT, {})

    assert result["status"] == "extracted_fallback"


def test_unverifiable_quote_is_dropped_not_shown_to_clinician():
    """
    Regression test for the core correctness fix: an LLM-supplied evidence quote that
    isn't an actual substring of the transcript (a hallucination/paraphrase) must never
    reach the clinician, even though the rest of the response is well-formed.
    """
    response_with_fake_quote = json.dumps({
        "note": {
            "chiefComplaint": "Patient reports abdominal pain.",
            "hpi": "Abdominal pain for one week.",
            "examination": "Unremarkable.",
            "diagnosis": "1. Abdominal pain, unspecified",
            "treatment": "Supportive care",
            "followUp": "Routine follow-up",
        },
        "riskAlerts": [
            {
                "severity": "HIGH",
                "category": "Fabricated",
                "title": "Invented Red Flag",
                "description": "This did not happen in the transcript.",
                "recommendedAction": "N/A",
                "evidenceQuote": "the patient reported crushing chest pain radiating to the jaw",
            }
        ],
        "differentials": [],
    })

    with patch("services.llm._call_ollama_with_timeout", return_value=response_with_fake_quote):
        result = generate_clinical_note(TRANSCRIPT, {})

    assert result["status"] == "success"
    assert result["riskAlerts"] == []


def test_partially_verified_differential_keeps_only_verified_evidence():
    response = json.dumps({
        "note": {
            "chiefComplaint": "Patient reports abdominal pain.",
            "hpi": "Abdominal pain for one week.",
            "examination": "Unremarkable.",
            "diagnosis": "1. Abdominal pain, unspecified",
            "treatment": "Supportive care",
            "followUp": "Routine follow-up",
        },
        "riskAlerts": [],
        "differentials": [
            {
                "diagnosis": "Irritable bowel syndrome",
                "icd10": "K58.9",
                "pathophysiology": "Altered gut motility.",
                "evidence": [
                    "It comes and goes, and I also have loose motions sometimes.",
                    "a completely invented quote that never appeared in the transcript",
                ],
                "confirmatoryTests": [],
                "severity": "LOW",
            }
        ],
    })

    with patch("services.llm._call_ollama_with_timeout", return_value=response):
        result = generate_clinical_note(TRANSCRIPT, {})

    assert len(result["differentials"]) == 1
    assert result["differentials"][0]["evidence"] == [
        "It comes and goes, and I also have loose motions sometimes."
    ]

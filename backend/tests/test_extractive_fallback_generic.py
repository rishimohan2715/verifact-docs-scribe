"""
Tests for services.llm._extractive_fallback_note_generator.

Context: the reported bug — a real, non-emergency consultation (abdominal cramping,
bloating, diarrhea) matched none of the old fallback's 5 hardcoded disease keyword sets
(ACS, appendicitis, DKA, asthma, renal colic), so it fell through to pasting the raw
transcript verbatim into the HPI field. The rewritten fallback builds HPI from generic
sentence shape (first-person symptom language, onset markers, medication doses) instead
of a disease allowlist, so it never falls back to a raw dump.
"""
from services.llm import _extractive_fallback_note_generator, generate_clinical_note_fast

IBS_LIKE_TRANSCRIPT = (
    "Alright, so what's your name and why are you here? "
    "I'm Ravi Kishan. I'm here because my stomach's been giving me trouble. "
    "What kind of trouble have you been facing? "
    "Cramping mostly and a lot of bloating. It kind of comes and goes. "
    "Okay, and when did this start? "
    "Maybe eight months ago. "
    "Do you have diarrhea? "
    "Sometimes, yeah. Loose motions come and then sometimes constipation too."
)


def test_generic_case_produces_real_narrative_not_raw_transcript_dump():
    result = _extractive_fallback_note_generator(IBS_LIKE_TRANSCRIPT)

    hpi = result["sections"]["hpi"]
    assert not hpi.startswith("Full transcript summary:")
    assert hpi != IBS_LIKE_TRANSCRIPT
    # The narrative should still contain the patient's own words, just curated rather
    # than dumped wholesale — the doctor's questions should not appear verbatim in it.
    assert "Cramping mostly" in hpi or "cramping" in hpi.lower()
    assert "What kind of trouble have you been facing?" not in hpi


def test_generic_case_does_not_guess_a_diagnosis():
    result = _extractive_fallback_note_generator(IBS_LIKE_TRANSCRIPT)

    diagnosis = result["sections"]["diagnosis"].lower()
    assert "local ai model was unavailable" in diagnosis
    # Must not silently reuse one of the old 5 canned disease guesses.
    assert "appendicitis" not in diagnosis
    assert "asthma" not in diagnosis
    assert "ketoacidosis" not in diagnosis


def test_chief_complaint_uses_patients_own_first_sentence():
    result = _extractive_fallback_note_generator(IBS_LIKE_TRANSCRIPT)
    assert result["sections"]["chiefComplaint"].startswith("Patient reports:")


def test_status_is_extracted_fallback_by_default():
    result = _extractive_fallback_note_generator(IBS_LIKE_TRANSCRIPT)
    assert result["status"] == "extracted_fallback"


def test_demo_fast_path_uses_distinct_status_label():
    """generate_clinical_note_fast intentionally skips Ollama for speed on synthetic demo
    transcripts — it should not claim the local AI model was 'unavailable'."""
    result = generate_clinical_note_fast(IBS_LIKE_TRANSCRIPT)
    assert result["status"] == "demo_fast_extract"


def test_vitals_shaped_sentence_goes_to_examination_not_hpi():
    transcript = "I have chest pain. Blood pressure is 140/90 and heart rate is 98 bpm."
    result = _extractive_fallback_note_generator(transcript)
    assert "140/90" in result["sections"]["examination"]
    assert "140/90" not in result["sections"]["hpi"]


def test_empty_transcript_does_not_crash():
    result = _extractive_fallback_note_generator("")
    assert result["sections"]["chiefComplaint"]
    assert result["status"] == "extracted_fallback"

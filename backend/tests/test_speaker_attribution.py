"""
Tests for services.transcription._infer_speaker.

Context: faster-whisper's VAD-filtered segments are contiguous (every
inter-segment gap measured 0.00s on real recordings), so there is no timing
signal available for detecting a turn change. Speaker attribution is
inferred purely from the linguistic shape of a clinical consultation.
"""
from services.transcription import _infer_speaker


def test_question_is_attributed_to_doctor():
    assert _infer_speaker("How long have you had this pain?", "PATIENT", False) == "DOCTOR"


def test_first_person_symptom_language_is_attributed_to_patient():
    assert _infer_speaker("I've been having chest pain for two days.", "DOCTOR", False) == "PATIENT"


def test_segment_after_a_question_is_the_answer():
    # No lexical cue of its own ("Two days ago.") — must fall back to the fact
    # that the previous segment ended in a question mark.
    assert _infer_speaker("Two days ago.", "DOCTOR", previous_was_question=True) == "PATIENT"


def test_no_cue_continues_the_running_speaker():
    # A whisper segment boundary that lands mid-sentence should not flip speaker.
    assert _infer_speaker("nearby traffic or cooking fires.", "PATIENT", False) == "PATIENT"
    assert _infer_speaker("nearby traffic or cooking fires.", "DOCTOR", False) == "DOCTOR"


def test_doctor_marker_without_question_mark():
    assert _infer_speaker("Let me perform a physical examination now", "PATIENT", False) == "DOCTOR"


def test_question_mark_wins_over_patient_marker():
    # "I" language inside a question is still the clinician asking about the patient.
    assert _infer_speaker("Have you noticed any swelling in your legs?", "PATIENT", False) == "DOCTOR"


def test_full_real_consultation_reconstructs_correctly():
    """
    Regression test for the exact conversation recovered from a real recording
    during debugging (backend/storage/audio/20260807_171227.webm): every single
    segment had been mislabeled "DOCTOR" by the old alternate-only-in-AUTO-mode
    logic. This walks the transcript turn by turn the way transcribe_audio does.
    """
    turns = [
        ("I'm not a state doctor. I'm having some trouble with my breathing.", "PATIENT"),
        ("You can ask me what are you need?", "DOCTOR"),
        ("So when did this issue actually start, Mr. Ravine?", "DOCTOR"),
        ("I'd say about a week ago, but it got worse in the last two days.", "PATIENT"),
        ("And for how long have you been having these issues?", "DOCTOR"),
        ("It's been a while, breathing trouble, often on for maybe two years", "PATIENT"),
        ("This time it hasn't.", "PATIENT"),
        ("Okay, and what are your symptoms like?", "DOCTOR"),
        ("Tide chest, whistling sound when I breathe, especially at night.", "PATIENT"),
        ("Short breaths and coughing. It feels heavier at night.", "PATIENT"),
        ("And when did these issues actually spike up?", "DOCTOR"),
        ("Two days ago. It's suddenly worsened.", "PATIENT"),
        ("I felt more wheezing, more tightness, harder to get a full breath.", "PATIENT"),
        ("Okay, tell me one thing. How long have you noticed that these issues spike up?", "DOCTOR"),
        ("What kind of environment do you work in on staying?", "DOCTOR"),
        ("I stay in a shared apartment, sometimes dusty, and there's often smoke", "PATIENT"),
        ("nearby traffic or cooking fires. It gets worse.", "PATIENT"),
        ("Swenier, feel stuffy.", "PATIENT"),
        ("All right.", "DOCTOR"),
    ]

    current_speaker = "DOCTOR"  # matches the frontend's default first-speaker dropdown
    previous_was_question = False
    mismatches = []

    for text, expected in turns:
        speaker = _infer_speaker(text, current_speaker, previous_was_question)
        if speaker != expected:
            mismatches.append((text, expected, speaker))
        current_speaker = speaker
        previous_was_question = text.strip().endswith("?")

    assert mismatches == [], f"Speaker mismatches: {mismatches}"

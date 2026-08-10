"""
Tests confirming clinical_rules.py and differential.py source their evidenceQuote/evidence
fields from the ACTUAL transcript passed in, not the hardcoded strings copied from
random_case.py's demo dialogue that they used before this fix.
"""
from services.clinical_rules import analyze_clinical_risks
from services.differential import generate_differential_details

REAL_ASTHMA_SENTENCE = (
    "My chest has been feeling really tight and I keep wheezing whenever I breathe out, "
    "it's not the same as the canned demo line about Albuterol non-responsiveness."
)


def test_risk_alert_evidence_is_the_real_transcript_sentence_not_the_demo_line():
    result = analyze_clinical_risks(REAL_ASTHMA_SENTENCE, "")
    assert len(result["alerts"]) == 1
    quote = result["alerts"][0]["evidenceQuote"]
    assert quote in REAL_ASTHMA_SENTENCE
    # The old hardcoded demo-script quote must not appear.
    assert "coughing constantly, wheezing, Albuterol inhaler isn't giving relief" not in quote


def test_differential_evidence_is_the_real_transcript_sentence_not_the_demo_line():
    result = generate_differential_details(REAL_ASTHMA_SENTENCE, "")
    assert len(result) == 1
    evidence = result[0]["evidence"]
    assert all(q in REAL_ASTHMA_SENTENCE for q in evidence)
    assert "Coughing constantly, wheezing, non-responsive to short-acting inhaler" not in evidence


def test_no_matching_sentence_falls_back_to_honest_placeholder():
    """
    The keyword trigger checks both the transcript AND the (LLM-drafted) diagnosis text,
    so a keyword can fire the alert via the diagnosis while never appearing in the
    transcript itself. In that case there's no real sentence to quote — the evidence must
    say so honestly rather than fabricate one.
    """
    transcript = "The patient came in for a routine follow-up with no new complaints."
    result = analyze_clinical_risks(transcript, diagnosis_text="wheeze noted on exam")
    assert len(result["alerts"]) == 1
    assert "no single sentence could be isolated" in result["alerts"][0]["evidenceQuote"].lower()


def test_no_keywords_match_produces_no_alerts_or_differentials():
    benign_transcript = "The patient is here for a routine annual physical with no complaints."
    assert analyze_clinical_risks(benign_transcript, "")["alerts"] == []
    assert generate_differential_details(benign_transcript, "") == []

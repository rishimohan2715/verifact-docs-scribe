"""
Unit tests for services.llm's quote-verification helpers (_verify_quote and friends),
the mechanism that stops an LLM-hallucinated evidence quote from ever reaching a clinician.
"""
from services.llm import _verify_quote, _filter_verified_alerts, _filter_verified_differentials

TRANSCRIPT = "I've been having crampy pain in my lower belly for about a week now."


def test_exact_substring_verifies():
    assert _verify_quote("crampy pain in my lower belly", TRANSCRIPT) is True


def test_whitespace_and_case_differences_still_verify():
    assert _verify_quote("  CRAMPY   pain in MY lower belly  ", TRANSCRIPT) is True


def test_paraphrased_quote_does_not_verify():
    assert _verify_quote("severe abdominal cramping for several days", TRANSCRIPT) is False


def test_empty_quote_does_not_verify():
    assert _verify_quote("", TRANSCRIPT) is False


def test_filter_verified_alerts_drops_unverifiable_ones():
    alerts = [
        {"title": "Real", "evidenceQuote": "crampy pain in my lower belly"},
        {"title": "Fake", "evidenceQuote": "crushing chest pain radiating to the jaw"},
    ]
    result = _filter_verified_alerts(alerts, TRANSCRIPT)
    assert [a["title"] for a in result] == ["Real"]


def test_filter_verified_differentials_keeps_only_verified_evidence_items():
    differentials = [
        {
            "diagnosis": "IBS",
            "evidence": ["crampy pain in my lower belly", "a fabricated quote nobody said"],
        }
    ]
    result = _filter_verified_differentials(differentials, TRANSCRIPT)
    assert len(result) == 1
    assert result[0]["evidence"] == ["crampy pain in my lower belly"]


def test_filter_verified_differentials_drops_entry_with_zero_verified_evidence():
    differentials = [
        {"diagnosis": "Fabricated", "evidence": ["nothing here is real", "made up entirely"]}
    ]
    result = _filter_verified_differentials(differentials, TRANSCRIPT)
    assert result == []

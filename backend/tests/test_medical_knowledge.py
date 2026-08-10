"""
Tests for services.medical_knowledge.auto_suggest_prescriptions.

Context: unlike auto_match_icd10_codes/auto_match_snomed_codes, this function had no
relevance sort or result cap — expanding the medications dataset to cover more primary-care
conditions caused it to return every medication sharing even one generic word (e.g.
"syndrome", "disorder") with the diagnosis text. A real IBS case returned 13 medications
including Aspirin, Nitroglycerin, and an SSRI. Fixed to sort by match count and cap at 5,
matching the existing pattern in auto_match_icd10_codes.
"""
from services.medical_knowledge import auto_suggest_prescriptions


def test_ibs_diagnosis_does_not_suggest_unrelated_cardiac_medications():
    diagnosis = "1. Irritable Bowel Syndrome (IBS), likely functional gastrointestinal disorder"
    transcript = "Cramping mostly and a lot of bloating, comes and goes."
    result = auto_suggest_prescriptions(transcript, diagnosis)

    names = [m["name"] for m in result]
    assert "Aspirin" not in names
    assert "Nitroglycerin" not in names
    assert "Escitalopram" not in names


def test_results_are_capped_at_five():
    everything = "asthma wheezing appendicitis mcburney dka ketoacidosis gerd reflux ibs bloating anxiety hypothyroidism"
    result = auto_suggest_prescriptions(everything, "")
    assert len(result) <= 5


def test_results_sorted_by_relevance_descending():
    result = auto_suggest_prescriptions(
        "Acute severe asthma exacerbation with wheezing, salbutamol, albuterol, expiratory, ipratropium all noted. Also mild fever.",
        "",
    )
    scores_are_implicit_in_order = [m["name"] for m in result]
    assert scores_are_implicit_in_order  # at minimum, asthma medication should be first
    assert result[0]["name"] in ("Salbutamol + Ipratropium",)


def test_no_matching_diagnosis_returns_empty_list():
    assert auto_suggest_prescriptions("routine annual physical, no complaints", "") == []

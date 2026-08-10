"""
Tests for services.medical_knowledge.auto_match_snomed_codes, mirroring the existing
ICD-10 matching behavior (same keyword-scoring approach, same dataset-loading pattern).
"""
from services.medical_knowledge import auto_match_snomed_codes, load_snomed_dataset


def test_dataset_loads_and_has_required_fields():
    dataset = load_snomed_dataset()
    assert len(dataset) > 0
    for item in dataset:
        assert item["conceptId"]
        assert item["preferredTerm"]
        assert item["category"]
        assert isinstance(item["keywords"], list)


def test_matches_asthma_transcript_to_asthma_concept():
    result = auto_match_snomed_codes("Patient has wheezing and uses an albuterol inhaler.", "")
    concept_ids = [r["conceptId"] for r in result]
    assert "195967001" in concept_ids  # Asthma


def test_matches_ibs_transcript_to_ibs_concept():
    result = auto_match_snomed_codes("Cramping, bloating, and loose motions that come and go.", "")
    concept_ids = [r["conceptId"] for r in result]
    assert "10743008" in concept_ids  # Irritable bowel syndrome


def test_result_includes_icd10_cross_reference():
    result = auto_match_snomed_codes("Patient has wheezing.", "")
    asthma_match = next(r for r in result if r["conceptId"] == "195967001")
    assert asthma_match["icd10Map"] == "J45.901"


def test_results_are_sorted_by_relevance_score_descending():
    result = auto_match_snomed_codes(
        "Wheezing, wheeze, asthma, albuterol, salbutamol, expiratory, ipratropium all present. Also mild headache.",
        "",
    )
    scores = [r["relevanceScore"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_empty_transcript_returns_no_matches():
    assert auto_match_snomed_codes("", "") == []


def test_results_are_capped_at_five():
    everything = " ".join(kw for item in load_snomed_dataset() for kw in item["keywords"])
    result = auto_match_snomed_codes(everything, "")
    assert len(result) <= 5

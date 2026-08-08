import re
import logging
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

# ─── Cached Presidio Engines (load ONCE into RAM, reuse forever) ──────────────
_PRESIDIO_ANALYZER = None
_PRESIDIO_ANONYMIZER = None
_PRESIDIO_AVAILABLE = None  # None = not yet checked, True/False = result


def _get_presidio_engines():
    """
    Lazily initializes Presidio AnalyzerEngine & AnonymizerEngine ONCE and caches
    them globally. The spaCy NLP model load (5-15s) happens only on first call.
    """
    global _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER, _PRESIDIO_AVAILABLE

    if _PRESIDIO_AVAILABLE is False:
        return None, None

    if _PRESIDIO_AVAILABLE is True:
        return _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER

    # First-time initialization
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        logger.info("Initializing Presidio engines (one-time spaCy model load)...")
        _PRESIDIO_ANALYZER = AnalyzerEngine()
        _PRESIDIO_ANONYMIZER = AnonymizerEngine()
        _PRESIDIO_AVAILABLE = True
        logger.info("Presidio engines cached in RAM successfully.")
        return _PRESIDIO_ANALYZER, _PRESIDIO_ANONYMIZER

    except Exception as e:
        logger.info(f"Presidio unavailable ({e}). Using fast regex PII redaction.")
        _PRESIDIO_AVAILABLE = False
        return None, None


def redact_pii(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Sanitizes sensitive patient data. Uses RAM-cached Presidio if available,
    otherwise falls back to instant regex redaction.
    """
    analyzer, anonymizer = _get_presidio_engines()

    if analyzer and anonymizer:
        try:
            results = analyzer.analyze(
                text=text,
                entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "DATE_TIME", "LOCATION"],
                language="en"
            )
            anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)

            redactions = []
            for res in results:
                redactions.append({
                    "entity_type": res.entity_type,
                    "start": res.start,
                    "end": res.end,
                    "score": round(res.score, 2)
                })
            return anonymized_result.text, redactions

        except Exception as e:
            logger.warning(f"Presidio runtime error ({e}). Falling back to regex.")

    return _regex_redact_fallback(text)


def _regex_redact_fallback(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Ultra-fast regex fallback to sanitize common PII patterns (< 1ms):
    - Names following titles (Mrs. Krishnan, Mr. Smith, Dr. Raman)
    - Phone numbers
    - MRN patterns (MRN-12345)
    """
    redacted = text
    redactions = []

    # Replace title + name (e.g. Mrs. Krishnan, Mr. Sharma)
    name_pattern = r'\b(Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+)\b'
    for match in re.finditer(name_pattern, redacted):
        redactions.append({
            "entity_type": "PERSON",
            "start": match.start(),
            "end": match.end(),
            "score": 0.9
        })
    redacted = re.sub(name_pattern, r'\1 [PATIENT_NAME]', redacted)

    # Phone numbers
    phone_pattern = r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
    for match in re.finditer(phone_pattern, redacted):
        redactions.append({
            "entity_type": "PHONE_NUMBER",
            "start": match.start(),
            "end": match.end(),
            "score": 0.95
        })
    redacted = re.sub(phone_pattern, '[PHONE_NUMBER]', redacted)

    # MRN
    mrn_pattern = r'\bMRN-?\d{4,8}\b'
    redacted = re.sub(mrn_pattern, '[MRN]', redacted)

    return redacted, redactions

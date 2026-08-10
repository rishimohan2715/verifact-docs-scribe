import re
from typing import List

_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s.strip()]


def find_sentences_containing(text: str, keywords: List[str], max_results: int = 3) -> List[str]:
    """Returns up to max_results transcript sentences that contain any of the keywords, verbatim."""
    sentences = split_sentences(text)
    matches = [s for s in sentences if any(kw.lower() in s.lower() for kw in keywords)]
    return matches[:max_results]

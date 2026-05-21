from typing import List
from logana.models.fieldState import FieldState, isKnown, Absent
from logana.extractors.timestamp import TimestampExtractor
from logana.pipeline.timeContext import PipelineTimeContext


def huntTimestamp(
    text: str,
    extractor: TimestampExtractor,
) -> FieldState:
    """Finds the best timestamp candidate across the full line and whitespace tokens."""
    cleaned = text.strip()
    if not cleaned:
        return Absent()

    candidates: List[FieldState] = [extractor.extract(cleaned)]
    for token in cleaned.split():
        candidates.append(extractor.extract(token))

    best = Absent()
    for candidate in candidates:
        if not isKnown(candidate):
            continue
        if not isKnown(best) or candidate.confidence > best.confidence:
            best = candidate
    return best

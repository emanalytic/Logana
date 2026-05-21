"""JSON loading with orjson when available, stdlib json as fallback."""

from __future__ import annotations

import json
from typing import Any, List, Tuple

try:
    import orjson
except ImportError:  # pragma: no cover
    orjson = None  # type: ignore[assignment]


def loadJsonObject(text: str) -> Tuple[Any, List[str]]:
    """Load one JSON object from a line, tolerating non-JSON prefix/trailing text."""
    stripped = text.strip()
    start_idx = stripped.find("{")
    if start_idx < 0:
        raise json.JSONDecodeError("No JSON object start found", stripped, 0)

    payload = stripped[start_idx:]
    warnings: List[str] = []
    if start_idx > 0:
        warnings.append("Ignored non-JSON prefix before object payload")

    if orjson is not None:
        try:
            data = orjson.loads(payload)
            end_idx = len(payload)
        except orjson.JSONDecodeError:
            decoder = json.JSONDecoder()
            data, end_idx = decoder.raw_decode(payload)
    else:
        decoder = json.JSONDecoder()
        data, end_idx = decoder.raw_decode(payload)

    trailing = payload[end_idx:].strip()
    if trailing:
        warnings.append("Ignored trailing text after JSON object payload")

    return data, warnings

from __future__ import annotations

import json


def canonical_json(value) -> str:
    """Serialize JSON deterministically for hashing and persistence."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

"""pack_quality — measure whether a DomainPack is any GOOD, not just schema-legal.

`DomainPack.validate()` says the shape is legal. A weak pack (vague falsifiers, one family, no typed
relations) makes the whole engine produce APPARENT rigor. This scores six components in [0,1] and an
overall — so a poor pack can be caught before it launders weak structure as rigor.
"""
from __future__ import annotations
from typing import Dict


def _falsifier_specific(a) -> bool:
    return len((a.falsifier or "").split()) >= 4


def pack_quality(pack) -> Dict:
    """Six components + an overall in [0,1]. Higher = a stronger pack."""
    names = [a.name for a in pack.assumptions]
    n = len(pack.assumptions)
    duplicates = sorted({x for x in names if names.count(x) > 1})
    weak_falsifiers = [a.name for a in pack.assumptions if not _falsifier_specific(a)]
    uncovered_axes = sorted(set(pack.axes) - set(pack.dimension_of.values()))

    components = {
        "assumption_count_score": round(min(1.0, n / 4.0), 3),
        "axis_coverage_score": round((len(pack.axes) - len(uncovered_axes)) / len(pack.axes), 3) if pack.axes else 0.0,
        "falsifier_specificity_score": round(sum(_falsifier_specific(a) for a in pack.assumptions) / n, 3) if n else 0.0,
        "known_family_score": round(min(1.0, len(set(pack.known_families)) / 2.0), 3),
        "relation_density_score": round(min(1.0, len(pack.relations) / n), 3) if n else 0.0,
        "info_kind_score": round(min(1.0, len(pack.info_kinds) / 2.0), 3),
    }
    overall = round(sum(components.values()) / len(components), 3)
    return {"overall": overall, "score": overall, "components": components,
            "duplicates": duplicates, "weak_falsifiers": weak_falsifiers, "uncovered_axes": uncovered_axes}

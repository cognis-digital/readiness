"""Readiness engine.

Computes SORTS-style C-ratings (C-1 best .. C-5 worst) across the four
measured areas: personnel (P), equipment on-hand (S/R), equipment
serviceability (R), and training (T). The overall level is the worst
(highest-numbered) area level, mirroring real SORTS rollup logic where a
unit can be no more ready than its weakest measured area.

Standard library only. Includes a small, dependency-free YAML subset parser
so the tool runs with zero install.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any


# C-level thresholds expressed as the minimum percentage to *achieve* a level.
# Based on common SORTS measured-area bands.
C_THRESHOLDS = [
    (90.0, 1),
    (80.0, 2),
    (70.0, 3),
    (60.0, 4),
]
# Below the lowest threshold -> C-5.
WORST_LEVEL = 5

# Relative weight of each area when computing a composite percentage.
# (Rollup uses worst-level, but the composite pct is a useful single number.)
AREA_WEIGHTS = {
    "personnel": 0.30,
    "equipment_onhand": 0.20,
    "equipment_serviceable": 0.20,
    "training": 0.30,
}

C_LEVEL_LABELS = {
    1: "C-1 (fully ready)",
    2: "C-2 (substantially ready)",
    3: "C-3 (marginally ready)",
    4: "C-4 (not ready)",
    5: "C-5 (undeployable / not measured)",
}


def c_level_from_pct(pct: float) -> int:
    """Map a percentage (0-100) to a C-level (1 best .. 5 worst)."""
    for threshold, level in C_THRESHOLDS:
        if pct >= threshold:
            return level
    return WORST_LEVEL


def overall_c_level(levels: list[int]) -> int:
    """Overall rollup = worst (max) measured area level."""
    if not levels:
        return WORST_LEVEL
    return max(levels)


@dataclass
class Area:
    """One measured readiness area."""

    name: str
    have: float
    required: float
    weight: float

    @property
    def pct(self) -> float:
        if self.required <= 0:
            return 100.0
        return min(100.0, round((self.have / self.required) * 100.0, 1))

    @property
    def level(self) -> int:
        return c_level_from_pct(self.pct)

    @property
    def gap(self) -> float:
        """Shortfall in absolute units (>=0)."""
        return max(0.0, round(self.required - self.have, 2))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "have": self.have,
            "required": self.required,
            "weight": self.weight,
            "pct": self.pct,
            "level": self.level,
            "level_label": C_LEVEL_LABELS[self.level],
            "gap": self.gap,
        }


@dataclass
class UnitReadiness:
    unit: str
    areas: list[Area] = field(default_factory=list)

    @property
    def composite_pct(self) -> float:
        total_w = sum(a.weight for a in self.areas)
        if total_w <= 0:
            return 0.0
        return round(sum(a.pct * a.weight for a in self.areas) / total_w, 1)

    @property
    def overall_level(self) -> int:
        return overall_c_level([a.level for a in self.areas])

    @property
    def limiting_areas(self) -> list[str]:
        """Area(s) that set the overall (worst) level."""
        lvl = self.overall_level
        return [a.name for a in self.areas if a.level == lvl]

    def gaps(self) -> list[dict[str, Any]]:
        out = []
        for a in self.areas:
            if a.gap > 0:
                out.append(
                    {
                        "area": a.name,
                        "have": a.have,
                        "required": a.required,
                        "gap": a.gap,
                        "pct": a.pct,
                        "level": a.level,
                    }
                )
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit": self.unit,
            "overall_level": self.overall_level,
            "overall_label": C_LEVEL_LABELS[self.overall_level],
            "composite_pct": self.composite_pct,
            "limiting_areas": self.limiting_areas,
            "areas": [a.to_dict() for a in self.areas],
            "gaps": self.gaps(),
        }


# --------------------------------------------------------------------------
# Minimal YAML subset parser (no third-party deps).
# Supports: top-level scalars, nested mappings (2-space indent), and the
# specific structure used by readiness input files. Values may be int/float/
# str. This is intentionally small and strict.
# --------------------------------------------------------------------------
def _coerce(val: str) -> Any:
    v = val.strip()
    if v == "":
        return None
    if (v[0] == v[-1]) and v[0] in ("'", '"') and len(v) >= 2:
        return v[1:-1]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "~"):
        return None
    try:
        if "." in v or "e" in low:
            return float(v)
        return int(v)
    except ValueError:
        return v


def parse_yaml(text: str) -> dict[str, Any]:
    """Parse the supported YAML subset into nested dicts.

    Indentation is 2 spaces per level. Lines may be 'key:' (a mapping) or
    'key: value' (a scalar). Comments (#) and blank lines are ignored.
    """
    root: dict[str, Any] = {}
    # stack of (indent, container) pairs
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_lineno, raw in enumerate(text.splitlines(), start=1):
        # strip trailing comments (only when not inside quotes - simple heuristic)
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        # handle inline comment
        if "#" in line:
            # do not strip inside quoted strings
            in_q = False
            q = ""
            cut = None
            for i, ch in enumerate(line):
                if in_q:
                    if ch == q:
                        in_q = False
                elif ch in ("'", '"'):
                    in_q = True
                    q = ch
                elif ch == "#":
                    cut = i
                    break
            if cut is not None:
                line = line[:cut].rstrip()
                if not line.strip():
                    continue

        indent = len(line) - len(line.lstrip(" "))
        content = line.strip()
        if ":" not in content:
            raise ValueError(f"line {raw_lineno}: expected 'key:' or 'key: value'")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()

        # pop to the correct parent
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"line {raw_lineno}: bad indentation")
        parent = stack[-1][1]

        if rest == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _coerce(rest)

    return root


def _num(d: dict[str, Any], key: str, where: str) -> float:
    if key not in d:
        raise ValueError(f"{where}: missing '{key}'")
    val = d[key]
    if not isinstance(val, (int, float)):
        raise ValueError(f"{where}: '{key}' must be a number, got {val!r}")
    if not math.isfinite(val):
        raise ValueError(f"{where}: '{key}' must be a finite number, got {val!r}")
    if val < 0:
        raise ValueError(f"{where}: '{key}' must be >= 0")
    return float(val)


def assess(data: dict[str, Any]) -> UnitReadiness:
    """Build a UnitReadiness from parsed input data.

    Expected structure (see demos/01-basic):
      unit: <name>
      personnel: {assigned, required}
      equipment: {onhand, authorized, serviceable}
      training: {mission_essential_tasks_trained, mission_essential_tasks_total}
    """
    unit = str(data.get("unit", "UNNAMED"))

    p = data.get("personnel")
    e = data.get("equipment")
    t = data.get("training")
    if not isinstance(p, dict):
        raise ValueError("input: missing 'personnel' mapping")
    if not isinstance(e, dict):
        raise ValueError("input: missing 'equipment' mapping")
    if not isinstance(t, dict):
        raise ValueError("input: missing 'training' mapping")

    assigned = _num(p, "assigned", "personnel")
    p_required = _num(p, "required", "personnel")
    onhand = _num(e, "onhand", "equipment")
    authorized = _num(e, "authorized", "equipment")
    serviceable = _num(e, "serviceable", "equipment")
    met_trained = _num(t, "mission_essential_tasks_trained", "training")
    met_total = _num(t, "mission_essential_tasks_total", "training")

    # Cross-field sanity: serviceable cannot exceed equipment on-hand.
    if serviceable > onhand:
        raise ValueError(
            f"equipment: 'serviceable' ({serviceable:g}) cannot exceed"
            f" 'onhand' ({onhand:g})"
        )

    # Cross-field sanity: tasks trained cannot exceed total tasks.
    if met_trained > met_total and met_total > 0:
        raise ValueError(
            f"training: 'mission_essential_tasks_trained' ({met_trained:g})"
            f" cannot exceed 'mission_essential_tasks_total' ({met_total:g})"
        )

    # serviceable is measured against equipment on-hand (can't service what you
    # don't have); guard divide-by-zero in Area.pct.
    areas = [
        Area("personnel", assigned, p_required, AREA_WEIGHTS["personnel"]),
        Area("equipment_onhand", onhand, authorized, AREA_WEIGHTS["equipment_onhand"]),
        Area(
            "equipment_serviceable",
            serviceable,
            onhand,
            AREA_WEIGHTS["equipment_serviceable"],
        ),
        Area("training", met_trained, met_total, AREA_WEIGHTS["training"]),
    ]
    return UnitReadiness(unit=unit, areas=areas)


def assess_text(text: str) -> UnitReadiness:
    """Parse YAML text and assess in one step."""
    return assess(parse_yaml(text))


def to_json(unit: UnitReadiness) -> str:
    return json.dumps(unit.to_dict(), indent=2)

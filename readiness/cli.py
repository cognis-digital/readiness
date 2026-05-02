"""Command-line interface for the readiness tool.

Subcommands:
  assess <file>   Compute C-ratings from a readiness YAML and flag gaps.

Global:
  --version
  --format {table,json}
  --fail-under {1..5}   Exit non-zero if overall level is worse than this.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import TOOL_NAME, TOOL_VERSION
from .core import UnitReadiness, assess_text, C_LEVEL_LABELS


def _render_table(u: UnitReadiness) -> str:
    lines = []
    lines.append(f"UNIT: {u.unit}")
    lines.append(
        f"OVERALL: {C_LEVEL_LABELS[u.overall_level]}  "
        f"(composite {u.composite_pct}%)"
    )
    if u.limiting_areas:
        lines.append("LIMITED BY: " + ", ".join(u.limiting_areas))
    lines.append("")
    header = f"{'AREA':<24}{'HAVE':>8}{'REQ':>8}{'PCT':>8}{'LEVEL':>8}"
    lines.append(header)
    lines.append("-" * len(header))
    for a in u.areas:
        lines.append(
            f"{a.name:<24}{a.have:>8g}{a.required:>8g}"
            f"{a.pct:>7}%{('C-' + str(a.level)):>8}"
        )
    gaps = u.gaps()
    if gaps:
        lines.append("")
        lines.append("GAPS:")
        for g in gaps:
            lines.append(
                f"  - {g['area']}: short {g['gap']:g} "
                f"({g['have']:g}/{g['required']:g}, {g['pct']}%, C-{g['level']})"
            )
    else:
        lines.append("")
        lines.append("GAPS: none")
    return "\n".join(lines)


def _cmd_assess(args: argparse.Namespace) -> int:
    try:
        with open(args.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"error: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2

    try:
        unit = assess_text(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(unit.to_dict(), indent=2))
    else:
        print(_render_table(unit))

    # Exit-code policy: failure = overall level worse than threshold.
    if unit.overall_level > args.fail_under:
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="SORTS-style unit readiness as code (defensive/analytical).",
    )
    p.add_argument(
        "--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}"
    )
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("assess", help="compute C-ratings and flag gaps")
    a.add_argument("file", help="readiness YAML input file")
    a.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="output format (default: table)",
    )
    a.add_argument(
        "--fail-under",
        type=int,
        default=3,
        choices=(1, 2, 3, 4, 5),
        help="exit non-zero if overall level worse than this (default: 3)",
    )
    a.set_defaults(func=_cmd_assess)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

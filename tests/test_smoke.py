"""Smoke tests for the readiness tool. Standard library only, no network."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from readiness import (  # noqa: E402
    TOOL_NAME,
    TOOL_VERSION,
    assess_text,
    c_level_from_pct,
    overall_c_level,
    parse_yaml,
)
from readiness.cli import main  # noqa: E402


SAMPLE = """
unit: TEST UNIT
personnel:
  assigned: 540
  required: 600
equipment:
  authorized: 60
  onhand: 42
  serviceable: 30
training:
  mission_essential_tasks_trained: 11
  mission_essential_tasks_total: 12
"""

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demos", "01-basic", "unit.yaml")


class TestMeta(unittest.TestCase):
    def test_version_string(self):
        self.assertEqual(TOOL_NAME, "readiness")
        self.assertTrue(TOOL_VERSION.count(".") >= 2)


class TestCLevels(unittest.TestCase):
    def test_bands(self):
        self.assertEqual(c_level_from_pct(95), 1)
        self.assertEqual(c_level_from_pct(90), 1)
        self.assertEqual(c_level_from_pct(85), 2)
        self.assertEqual(c_level_from_pct(75), 3)
        self.assertEqual(c_level_from_pct(65), 4)
        self.assertEqual(c_level_from_pct(10), 5)

    def test_rollup_is_worst(self):
        self.assertEqual(overall_c_level([1, 3, 1, 2]), 3)
        self.assertEqual(overall_c_level([]), 5)


class TestParser(unittest.TestCase):
    def test_nested_and_scalars(self):
        data = parse_yaml(SAMPLE)
        self.assertEqual(data["unit"], "TEST UNIT")
        self.assertEqual(data["personnel"]["assigned"], 540)
        self.assertEqual(data["equipment"]["serviceable"], 30)

    def test_comment_and_blank(self):
        data = parse_yaml("# c\nunit: X  # inline\n\npersonnel:\n  assigned: 1\n  required: 2\n")
        self.assertEqual(data["unit"], "X")
        self.assertEqual(data["personnel"]["assigned"], 1)

    def test_bad_line(self):
        with self.assertRaises(ValueError):
            parse_yaml("this has no colon")


class TestAssess(unittest.TestCase):
    def test_overall_limited_by_equipment(self):
        u = assess_text(SAMPLE)
        self.assertEqual(u.unit, "TEST UNIT")
        self.assertEqual(u.overall_level, 3)
        self.assertIn("equipment_onhand", u.limiting_areas)
        d = u.to_dict()
        self.assertEqual(d["overall_level"], 3)
        self.assertTrue(any(g["area"] == "equipment_onhand" for g in d["gaps"]))

    def test_personnel_pct(self):
        u = assess_text(SAMPLE)
        pers = next(a for a in u.areas if a.name == "personnel")
        self.assertEqual(pers.pct, 90.0)
        self.assertEqual(pers.level, 1)

    def test_zero_required_no_div_error(self):
        text = (
            "unit: Z\npersonnel:\n  assigned: 0\n  required: 0\n"
            "equipment:\n  authorized: 0\n  onhand: 0\n  serviceable: 0\n"
            "training:\n  mission_essential_tasks_trained: 0\n"
            "  mission_essential_tasks_total: 0\n"
        )
        u = assess_text(text)
        self.assertEqual(u.overall_level, 1)

    def test_missing_section(self):
        with self.assertRaises(ValueError):
            assess_text("unit: bad\npersonnel:\n  assigned: 1\n  required: 2\n")


class TestCLI(unittest.TestCase):
    def test_table_exit_zero(self):
        # default fail-under=3, demo is C-3 -> not worse -> exit 0
        self.assertEqual(main(["assess", DEMO]), 0)

    def test_fail_under_two(self):
        # C-3 is worse than 2 -> exit 1
        self.assertEqual(main(["assess", DEMO, "--fail-under", "2"]), 1)

    def test_json_output(self):
        proc = subprocess.run(
            [sys.executable, "-m", "readiness", "assess", DEMO, "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertEqual(parsed["unit"], "2-7 CAV (notional)")
        self.assertEqual(parsed["overall_level"], 3)

    def test_module_version(self):
        proc = subprocess.run(
            [sys.executable, "-m", "readiness", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("readiness", proc.stdout)


if __name__ == "__main__":
    unittest.main()

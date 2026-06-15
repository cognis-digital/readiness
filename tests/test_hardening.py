"""Hardening tests: error paths and edge-case inputs.

All tests use stdlib only; no network access.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from readiness.core import assess_text  # noqa: E402
from readiness.cli import main  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _yaml(
    unit="T",
    p_assigned=540, p_required=600,
    e_authorized=60, e_onhand=42, e_serviceable=30,
    t_trained=11, t_total=12,
) -> str:
    """Build minimal valid YAML with overridable leaf values."""
    lines = [
        "unit: " + str(unit),
        "personnel:",
        "  assigned: " + str(p_assigned),
        "  required: " + str(p_required),
        "equipment:",
        "  authorized: " + str(e_authorized),
        "  onhand: " + str(e_onhand),
        "  serviceable: " + str(e_serviceable),
        "training:",
        "  mission_essential_tasks_trained: " + str(t_trained),
        "  mission_essential_tasks_total: " + str(t_total),
    ]
    return "\n".join(lines) + "\n"


class TestNonFiniteRejection(unittest.TestCase):
    """_num must reject inf and NaN; they are not valid readiness counts."""

    def test_infinity_personnel_assigned_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            assess_text(_yaml(p_assigned="1e999"))
        self.assertIn("finite", str(ctx.exception))

    def test_infinity_equipment_onhand_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            assess_text(_yaml(e_onhand="1e999", e_serviceable=0))
        self.assertIn("finite", str(ctx.exception))


class TestCrossFieldValidation(unittest.TestCase):
    """Cross-field constraints are enforced with clear error messages."""

    def test_serviceable_exceeds_onhand(self):
        with self.assertRaises(ValueError) as ctx:
            assess_text(_yaml(e_onhand=10, e_serviceable=25))
        msg = str(ctx.exception)
        self.assertIn("serviceable", msg)
        self.assertIn("onhand", msg)

    def test_trained_exceeds_total(self):
        with self.assertRaises(ValueError) as ctx:
            assess_text(_yaml(t_trained=15, t_total=12))
        msg = str(ctx.exception)
        self.assertIn("mission_essential_tasks_trained", msg)
        self.assertIn("mission_essential_tasks_total", msg)

    def test_trained_equals_total_ok(self):
        """Exact 100-percent trained is valid."""
        u = assess_text(_yaml(t_trained=12, t_total=12))
        t = next(a for a in u.areas if a.name == "training")
        self.assertEqual(t.pct, 100.0)

    def test_serviceable_equals_onhand_ok(self):
        """All on-hand equipment serviceable is valid."""
        u = assess_text(_yaml(e_onhand=42, e_serviceable=42))
        s = next(a for a in u.areas if a.name == "equipment_serviceable")
        self.assertEqual(s.pct, 100.0)


class TestCLIMissingFile(unittest.TestCase):
    """CLI must exit 2 and write to stderr when the file is absent."""

    def test_missing_file_returns_exit2(self):
        code = main(["assess", "/absolutely/nonexistent/path/unit.yaml"])
        self.assertEqual(code, 2)

    def test_missing_file_subprocess_stderr(self):
        proc = subprocess.run(
            [sys.executable, "-m", "readiness", "assess", "/no/such/file.yaml"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("error", proc.stderr.lower())
        self.assertEqual(proc.stdout, "")


class TestCLIMalformedInput(unittest.TestCase):
    """CLI must exit 2 for unparseable or structurally invalid YAML."""

    def test_malformed_yaml_returns_exit2(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tf:
            tf.write("no colon line\n")
            path = tf.name
        try:
            self.assertEqual(main(["assess", path]), 2)
        finally:
            os.unlink(path)

    def test_missing_section_returns_exit2(self):
        yaml_str = "\n".join([
            "unit: partial",
            "personnel:",
            "  assigned: 1",
            "  required: 2",
            "",
        ])
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(yaml_str)
            path = tf.name
        try:
            self.assertEqual(main(["assess", path]), 2)
        finally:
            os.unlink(path)


class TestMcpServerImport(unittest.TestCase):
    """mcp_server must import without raising (no broken scan reference)."""

    def test_import_does_not_raise(self):
        import readiness.mcp_server as _mod  # noqa: F401
        self.assertTrue(callable(_mod.serve))


if __name__ == "__main__":
    unittest.main()
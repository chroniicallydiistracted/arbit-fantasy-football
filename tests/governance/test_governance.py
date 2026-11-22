"""Unit tests for durable, offline, deterministic governance gates."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import subprocess
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/governance.py"
spec = importlib.util.spec_from_file_location("arbit_governance", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GovernanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patch = patch.object(module, "ROOT", self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.write("docs/product/requirements.json", {"version": 1, "requirements": [{"id": "MD-001"}]})
        self.write("docs/governance/requirements.json", {"requirements": [{"id": "GOVAI-001"}]})
        self.write("docs/governance/change-gates.json", {"classes": {"docs": ["foundation"]}})
        self.write("docs/governance/check-commands.json", {"commands": {"foundation": ["python", "-c", "pass"]}})
        self.write("docs/governance/state.json", {"version": 1, "project": "arbit-fantasy-football", "active_task": None, "latest_handoff": "docs/project/handoffs/initial.md"})
        self.file("docs/project/status.md", "Status")
        self.file("docs/project/changelog.md", "Changelog")
        self.file("docs/project/handoffs/initial.md", "Initial")
        self.file("docs/project/review.md", "Review")
        self.file("docs/project/change.md", "Before")

    def file(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def write(self, name, value):
        self.file(name, json.dumps(value))

    def start(self):
        module.cmd_start(Namespace(id="TASK-20261122-001", title="Make progress", objective="Specific outcome",
                                   change_class="docs", requirements=["MD-001"], files=["docs/project/change.md"]))

    def test_path_escape_rejected(self):
        for name in ("../private.env", "/etc/passwd", "docs/../../data.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                module.relative_path(name)

    def test_no_duplicate_active_task(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "active"):
            module.cmd_start(Namespace(id="TASK-20261122-002", title="Other", objective="Other",
                                       change_class="docs", requirements=["MD-001"], files=["docs/project/change.md"]))

    def test_review_gate_rejects_missing_evidence(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "review"):
            module.cmd_advance(Namespace(to="plan"))

    def test_plan_gate_rejects_out_of_scope_files(self):
        self.start()
        module.cmd_update(Namespace(section="review", summary="Read source", files=["docs/project/review.md"]))
        module.cmd_advance(Namespace(to="plan"))
        module.cmd_update(Namespace(section="plan", summary="Will change source", files=["docs/project/status.md"]))
        with self.assertRaisesRegex(ValueError, "scoped"):
            module.cmd_advance(Namespace(to="implement"))

    def test_park_resume_preserves_context(self):
        self.start()
        module.cmd_note(Namespace(kind="risk", text="Missing rules are unresolved", evidence="source doc"))
        module.cmd_park(Namespace(reason="Needs owner approval", next_action="Find accepted decision"))
        self.assertIsNone(module.state()["active_task"])
        module.cmd_resume(Namespace(id="TASK-20261122-001"))
        self.assertIn("Find accepted decision", module.brief_text())
        self.assertEqual(len(module.active_task()["journal"]), 2)

    def test_reserved_check_name_rejects_arbitrary_true(self):
        self.start()
        t = module.active_task(); t["phase"] = "validate"; module.store_task(t)
        with self.assertRaisesRegex(ValueError, "Reserved check"):
            module.cmd_check(Namespace(name="foundation", timeout=10, command=["--", "true"]))

    def test_closeout_rejects_no_evidence(self):
        self.start()
        t = module.active_task(); t["phase"] = "handoff"; module.store_task(t)
        with self.assertRaisesRegex(ValueError, "Closeout BLOCKED"):
            module.cmd_finish()

    def test_full_task_passes_and_writes_handoff(self):
        self.start()
        module.cmd_note(Namespace(kind="observation", text="Verified repository artifact", evidence="docs/project/review.md"))
        module.cmd_update(Namespace(section="review", summary="Read evidence", files=["docs/project/review.md"]))
        module.cmd_advance(Namespace(to="plan"))
        module.cmd_update(Namespace(section="plan", summary="Update a file", files=["docs/project/change.md"]))
        module.cmd_advance(Namespace(to="implement"))
        self.file("docs/project/change.md", "After")
        module.cmd_update(Namespace(section="implementation", summary="Made the change", files=["docs/project/change.md"]))
        module.cmd_advance(Namespace(to="validate"))
        module.cmd_check(Namespace(name="foundation", timeout=10, command=[]))
        module.cmd_update(Namespace(section="validation", summary="Foundation check observed exit=0", files=[]))
        module.cmd_advance(Namespace(to="document"))
        module.cmd_update(Namespace(section="documentation", summary="Updated state/changelog", files=["docs/project/status.md", "docs/project/changelog.md"]))
        module.cmd_advance(Namespace(to="handoff"))
        module.cmd_handoff(Namespace(next_action="No further change; verify in release", unresolved="No identified blockers"))
        module.cmd_finish()
        self.assertIsNone(module.state()["active_task"])
        self.assertEqual(module.task_by_id("TASK-20261122-001")["status"], "completed")

    def test_old_check_stales_after_modification(self):
        self.start()
        t = module.active_task(); t["phase"] = "validate"; module.store_task(t)
        module.cmd_check(Namespace(name="foundation", timeout=10, command=[]))
        self.file("docs/project/change.md", "After validation")
        self.assertNotEqual(module.active_task()["checks"][-1]["scope_sha256"],
                            module.hash_scoped(["docs/project/change.md"]))

    def test_cli_dispatches_named_check(self):
        with patch.object(module, "cmd_check") as command, patch("sys.argv", ["governance.py", "run-check", "--name", "foundation"]):
            self.assertEqual(module.main(), 0)
            command.assert_called_once()

    def test_amend_preserves_correction_journal(self):
        self.start()
        module.cmd_update(Namespace(section="review", summary="Original review", files=["docs/project/review.md"]))
        module.cmd_advance(Namespace(to="plan"))
        module.cmd_amend(Namespace(section="review", summary="Corrected review", reason="New source evidence"))
        t = module.active_task()
        self.assertEqual(t["sections"]["review"]["summary"], "Corrected review")
        self.assertEqual(t["journal"][-1]["kind"], "correction")

    def test_diff_gate_requires_closed_task_and_covering_handoff(self):
        def git(*args):
            p = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return p.stdout.strip()
        git("init", "-q")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")
        git("add", ".")
        git("commit", "-qm", "baseline")
        base = git("rev-parse", "HEAD")
        self.file("docs/project/change.md", "New value")
        tid = "TASK-20261122-001"
        self.write(f"docs/governance/tasks/{tid}.json", {
            "id": tid, "status": "completed", "scope_files": ["docs/project/change.md"],
            "deleted_files": [], "sections": {"handoff": {"path": "docs/project/handoffs/new.md"}}})
        self.file("docs/project/handoffs/new.md", "Handoff record")
        git("add", ".")
        git("commit", "-qm", "covered change")
        module.cmd_diff_gate(base)
        self.file("not-scoped.md", "Unauthorized change")
        git("add", ".")
        git("commit", "-qm", "uncovered change")
        with self.assertRaisesRegex(ValueError, "not covered"):
            module.cmd_diff_gate(base)

    def test_declared_deletion_must_be_scoped(self):
        with self.assertRaisesRegex(ValueError, "Intended deletions"):
            module.cmd_start(Namespace(id="TASK-20261122-002", title="Remove file", objective="Remove old file",
                change_class="docs", requirements=["MD-001"], files=["docs/project/change.md"],
                deletions=["docs/project/review.md"]))

    def test_credential_pattern_rejected(self):
        with self.assertRaises(ValueError):
            module.safe_text("password=supersecretpassword")


if __name__ == "__main__":
    unittest.main()

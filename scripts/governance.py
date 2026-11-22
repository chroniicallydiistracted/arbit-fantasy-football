#!/usr/bin/env python3
"""Arbit durable agent task recorder / closeout gate (stdlib, offline, cross-platform).

Does not infer owner approval, deploy, read provider secrets, or execute app code
unless explicitly called with `run-check -- command ...` by an operator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PHASES = ("review", "plan", "implement", "validate", "document", "handoff")
SECTIONS = {"review": "review", "plan": "plan", "implement": "implementation", "validate": "validation", "document": "documentation"}
ID_PATTERN = re.compile(r"TASK-\d{8}-\d{3,5}$")
SECRET_PATTERN = re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----|(?:token|password|api[_-]?key|secret)\s*[=:]\s*[^\s]{8,}", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, temp = tempfile.mkstemp(prefix=".gov-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(content)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def relative_path(name: str, *, must_exist: bool = False) -> Path:
    if not name or Path(name).is_absolute():
        raise ValueError(f"Expected repository-relative path, got: {name!r}")
    resolved = (ROOT / name).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"Path escapes repository: {name}")
    if must_exist and not resolved.is_file():
        raise ValueError(f"Missing file: {name}")
    return resolved


def safe_text(value: str) -> str:
    value = value.strip()
    if SECRET_PATTERN.search(value):
        raise ValueError("Possible credential in governance record; redact it first")
    if not value:
        raise ValueError("Non-empty evidence text is required")
    return value


def task_path(task_id: str) -> Path:
    if not ID_PATTERN.fullmatch(task_id):
        raise ValueError("Task ID must be TASK-YYYYMMDD-NNN (up to five digits)")
    return ROOT / "docs/governance/tasks" / f"{task_id}.json"


def state() -> dict[str, Any]:
    return load(ROOT / "docs/governance/state.json")


def task_by_id(task_id: str) -> dict[str, Any]:
    path = task_path(task_id)
    if not path.is_file():
        raise ValueError(f"Task not found: {task_id}")
    return load(path)


def active_task() -> dict[str, Any]:
    task_id = state()["active_task"]
    if not task_id:
        raise ValueError("No active task; use start or resume")
    return task_by_id(task_id)


def store_task(task: dict[str, Any]) -> None:
    task["updated_at"] = now()
    save(task_path(task["id"]), task)


def required_ids() -> set[str]:
    prod = {r["id"] for r in load(ROOT / "docs/product/requirements.json")["requirements"]}
    gov = {r["id"] for r in load(ROOT / "docs/governance/requirements.json")["requirements"]}
    return prod | gov


def hash_scoped(paths: list[str]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name in paths:
        if name == "docs/governance/state.json" or name.startswith("docs/governance/tasks/"):
            # Task bookkeeping is updated by the recorder itself after validation.
            # Validate its schema/closeout separately rather than demand byte stability.
            hashes[name] = "DYNAMIC-STATE"
            continue
        path = relative_path(name)
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
    return hashes


def brief_text() -> str:
    s = state()
    lines = ["ARBIT / FFA fantasy football (ESPN league 1729878439)",
             "Authority: AGENTS.md → docs/governance/START_HERE.md → owner decisions/ADRs.",
             "Source and runtime state are not interchangeable.",
             f"Latest handoff pointer: {s['latest_handoff']}"]
    if s["active_task"]:
        t = task_by_id(s["active_task"])
        lines.extend([f"ACTIVE: {t['id']} / {t['title']} ({t['phase']})",
                      f"Objective: {t['objective']}",
                      f"Next: {t.get('next_action') or 'Complete current stage evidence and advance'}",
                      f"Task file: docs/governance/tasks/{t['id']}.json"])
    else:
        lines.append("No active governed task. Consult project status/roadmap before starting one.")
        lines.append("Recorded project next action (verify before executing): " + s.get("project_next_action", "Not set"))
    blocked = []
    for path in sorted((ROOT / "docs/governance/tasks").glob("TASK-*.json")):
        t = load(path)
        if t["status"] == "blocked":
            blocked.append(f"{t['id']}: {t.get('next_action') or t.get('block_reason')}")
    if blocked:
        lines.append("BLOCKED TASKS: " + " | ".join(blocked[:8]))
    status_lines = (ROOT / "docs/project/status.md").read_text(encoding="utf-8").splitlines()
    lines.append("Status excerpt: " + " ".join(line.strip() for line in status_lines[1:6])[:650])
    lines.append("Critical unresolved: no validated projection, sit/start, waiver or trade advisor shipped (ADR-007 accepted 2026-11-22, OWN-066).")
    lines.append("Run `python scripts/governance.py doctor`; verify repository diff and deployment separately.")
    return "\n".join(lines)


def doctor() -> list[str]:
    problems: list[str] = []
    critical = ["AGENTS.md", "CLAUDE.md", "docs/governance/START_HERE.md",
                "docs/governance/SOURCE_OF_TRUTH.md", "docs/governance/FANTASY_ADVISOR_CHARTER.md",
                "docs/governance/state.json", "docs/governance/requirements.json",
                "docs/governance/change-gates.json", "docs/governance/check-commands.json", ".claude/settings.json", "scripts/governance_hook.py"]
    for name in critical:
        if not relative_path(name).is_file():
            problems.append(f"Missing critical governance file: {name}")
    if problems:
        return problems
    s = state()
    if s.get("version") != 1 or s.get("project") != "arbit-fantasy-football":
        problems.append("Invalid state version/project")
    handoff = s.get("latest_handoff")
    if not handoff or not relative_path(handoff).is_file():
        problems.append("State.latest_handoff does not resolve")
    reqs = load(ROOT / "docs/governance/requirements.json")["requirements"]
    ids = [r["id"] for r in reqs]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"GOVAI-\d{3}", n) for n in ids):
        problems.append("Governance requirements contain invalid/duplicate IDs")
    known = required_ids()
    gates = load(ROOT / "docs/governance/change-gates.json")["classes"]
    commands = load(ROOT / "docs/governance/check-commands.json")["commands"]
    if not gates or any(not v or not set(v).issubset(commands) for v in gates.values()):
        problems.append("Change-class gates reference unknown or empty commands")
    active: list[str] = []
    for path in sorted((ROOT / "docs/governance/tasks").glob("TASK-*.json")):
        try:
            t = load(path)
            if t["id"] != path.stem or not ID_PATTERN.fullmatch(t["id"]):
                problems.append(f"Invalid ID in {path.name}")
            if t["status"] not in {"active", "blocked", "completed"}:
                problems.append(f"Unknown task status in {path.name}")
            if t["phase"] not in PHASES or t["change_class"] not in gates:
                problems.append(f"Unknown task phase/change class in {path.name}")
            if not t["requirements"] or not set(t["requirements"]).issubset(known):
                problems.append(f"Missing or invalid requirement IDs in {path.name}")
            for name in t["scope_files"]:
                relative_path(name)
            if not set(t.get("deleted_files", [])).issubset(t["scope_files"]):
                problems.append(f"Invalid deletion scope in {path.name}")
            if t["status"] == "active":
                active.append(t["id"])
            if t["status"] == "completed":
                for phase in PHASES:
                    for problem in section_errors(t, phase):
                        problems.append(f"Completed task {path.name}: {problem}")
            if SECRET_PATTERN.search(json.dumps(t)):
                problems.append(f"Suspected secret in {path.name}")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            problems.append(f"Malformed task {path.name}: {error}")
    if len(active) > 1 or active != ([s["active_task"]] if s["active_task"] else []):
        problems.append("Active task index and task states differ")
    root_agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "scripts/governance.py brief" not in root_agents:
        problems.append("AGENTS.md does not reference the restart protocol")
    if "2026-11-10-m3-nfl-availability.md)" in root_agents:
        problems.append("AGENTS.md has outdated hardcoded latest handoff")
    try:
        hooks = load(ROOT / ".claude/settings.json")["hooks"]
        if "SessionStart" not in hooks or "Stop" not in hooks:
            problems.append("Claude hook configuration lacks restart/stop reminder")
    except (ValueError, KeyError):
        problems.append("Malformed Claude hooks configuration")
    return problems


def cmd_start(args: argparse.Namespace) -> None:
    s = state()
    if s["active_task"]:
        raise ValueError(f"Cannot start while {s['active_task']} active; park/finish it first")
    path = task_path(args.id)
    if path.exists():
        raise ValueError("Task ID already exists")
    if args.change_class not in load(ROOT / "docs/governance/change-gates.json")["classes"]:
        raise ValueError("Unknown change class")
    if not args.requirements or not set(args.requirements).issubset(required_ids()):
        raise ValueError("At least one valid requirement ID is required")
    scope = list(dict.fromkeys(args.files))
    if not scope:
        raise ValueError("At least one scoped repository-relative file is required")
    for name in scope:
        relative_path(name)
    deletions = list(dict.fromkeys(getattr(args, "deletions", []) or []))
    if not set(deletions).issubset(scope):
        raise ValueError("Intended deletions must be included in scoped files")
    for name in deletions:
        relative_path(name, must_exist=True)
    sections: dict[str, dict[str, Any]] = {part: {"summary": "", "files": []} for part in
                                              ("review", "plan", "implementation", "validation", "documentation")}
    sections["handoff"] = {"path": None, "next_action": "", "unresolved": ""}
    task = {"version": 1, "id": args.id, "title": safe_text(args.title),
            "objective": safe_text(args.objective), "status": "active", "phase": "review",
            "change_class": args.change_class, "requirements": list(dict.fromkeys(args.requirements)),
            "scope_files": scope, "deleted_files": deletions, "created_at": now(), "updated_at": now(),
            "baseline": git_head(), "next_action": "Read affected requirements/source and record Review evidence",
            "sections": sections, "checks": [], "journal": []}
    store_task(task)
    s["active_task"] = args.id
    save(ROOT / "docs/governance/state.json", s)
    print(f"STARTED {args.id}: {args.title}")


def git_head() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def cmd_update(args: argparse.Namespace) -> None:
    t = active_task()
    expected = SECTIONS.get(t["phase"])
    if args.section != expected:
        raise ValueError(f"Current phase is {t['phase']}; update {expected} first")
    part = t["sections"][args.section]
    part["summary"] = safe_text(args.summary)
    if args.files:
        part["files"] = list(dict.fromkeys(args.files))
        for name in part["files"]:
            relative_path(name)
    store_task(t)
    print(f"RECORDED {args.section} for {t['id']}")


def cmd_amend(args: argparse.Namespace) -> None:
    """Correct an earlier stage summary while preserving why the record changed."""
    t = active_task()
    part_to_phase = {value: key for key, value in SECTIONS.items()}
    phase = part_to_phase[args.section]
    if PHASES.index(phase) >= PHASES.index(t["phase"]):
        raise ValueError("Only completed earlier sections may be amended; use update for the current stage")
    previous = t["sections"][args.section]["summary"]
    t["sections"][args.section]["summary"] = safe_text(args.summary)
    t["journal"].append({"at": now(), "kind": "correction",
                         "note": f"Amended {args.section}: {safe_text(args.reason)}",
                         "evidence": "previous_summary_sha256=" + hashlib.sha256(previous.encode()).hexdigest()})
    store_task(t)
    print(f"AMENDED {args.section} for {t['id']}; correction recorded")


def cmd_note(args: argparse.Namespace) -> None:
    t = active_task()
    t["journal"].append({"at": now(), "kind": args.kind,
                         "note": safe_text(args.text),
                         "evidence": safe_text(args.evidence) if args.evidence else "not yet verified"})
    store_task(t)
    print(f"NOTE {args.kind}: {t['id']}")


def section_errors(t: dict[str, Any], phase: str) -> list[str]:
    errors = []
    key = SECTIONS.get(phase)
    if key:
        block = t["sections"][key]
        if not block["summary"]:
            errors.append(f"{key}: summary required")
    if phase == "review":
        files = t["sections"]["review"]["files"]
        if not files or any(not relative_path(n).is_file() for n in files):
            errors.append("review: inspected source documents/files required")
    if phase == "plan":
        files = t["sections"]["plan"]["files"]
        if not files or not set(files).issubset(t["scope_files"]):
            errors.append("plan: affected files must be within scoped paths")
    if phase == "implement":
        files = t["sections"]["implementation"]["files"]
        if not files or not set(files).issubset(t["scope_files"]):
            errors.append("implementation: modified files must be within scoped paths")
    if phase in {"validate", "handoff"}:
        wanted = load(ROOT / "docs/governance/change-gates.json")["classes"][t["change_class"]]
        successes = {c["name"] for c in t["checks"] if c["exit_code"] == 0}
        missing = sorted(set(wanted) - successes)
        if missing:
            errors.append(f"validation: missing successful checks {missing}")
        if not t["sections"]["validation"]["summary"]:
            errors.append("validation: result/limitations summary required")
        recent_by_name = {c["name"]: c for c in t["checks"]}
        for name in wanted:
            if name in recent_by_name and recent_by_name[name]["exit_code"] != 0:
                errors.append(f"validation: latest {name} run failed")
    if phase in {"document", "handoff"}:
        docs = set(t["sections"]["documentation"]["files"])
        for required in {"docs/project/status.md", "docs/project/changelog.md"}:
            if required not in docs:
                errors.append(f"documentation: include {required}")
    if phase == "handoff":
        part = t["sections"]["handoff"]
        if not part["path"] or not relative_path(part["path"]).is_file():
            errors.append("handoff: generated file required")
        if not part["next_action"] or not part["unresolved"]:
            errors.append("handoff: next action and unresolved status required")
        if not t["journal"]:
            errors.append("handoff: at least one finding/risk/decision/correction note required")
    return errors


def cmd_advance(args: argparse.Namespace) -> None:
    t = active_task()
    current = PHASES.index(t["phase"])
    if current == len(PHASES) - 1 or args.to != PHASES[current + 1]:
        raise ValueError(f"Next valid phase after {t['phase']} is {PHASES[current + 1] if current < 5 else 'finish'}")
    errors = section_errors(t, t["phase"])
    if errors:
        raise ValueError("Cannot advance: " + "; ".join(errors))
    t["phase"] = args.to
    t["next_action"] = f"Record {args.to} evidence"
    store_task(t)
    print(f"ADVANCED {t['id']} → {args.to}")


def cmd_check(args: argparse.Namespace) -> None:
    t = active_task()
    if t["phase"] not in {"validate", "document", "handoff"}:
        raise ValueError("Run check after entering validate phase")
    argv = args.command
    if argv and argv[0] == "--":
        argv = argv[1:]
    profiles = load(ROOT / "docs/governance/check-commands.json")["commands"]
    if args.name in profiles:
        expected = profiles[args.name]
        if argv and argv != expected:
            raise ValueError(f"Reserved check name {args.name} requires exact command: {expected}")
        argv = expected
    elif not argv:
        raise ValueError("Unregistered check name needs an executable after --")
    if any(SECRET_PATTERN.search(x) for x in argv):
        raise ValueError("Do not put credentials in argv")
    start = time.monotonic()
    exit_code = 127
    digest = ""
    try:
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=args.timeout,
                                check=False)
        exit_code = result.returncode
        digest = hashlib.sha256(result.stdout + b"\n" + result.stderr).hexdigest()
    except subprocess.TimeoutExpired:
        exit_code = 124
    except OSError:
        exit_code = 127
    result_record = {"name": args.name, "argv": argv, "at": now(), "exit_code": exit_code,
                     "duration_seconds": round(time.monotonic()-start, 3),
                     "stdout_stderr_sha256": digest, "git_head": git_head(),
                     "scope_sha256": hash_scoped(t["scope_files"])}
    t["checks"].append(result_record)
    store_task(t)
    print(f"CHECK {args.name} exit={exit_code} duration={result_record['duration_seconds']}s; output was not persisted")
    if exit_code:
        raise SystemExit(exit_code if 0 < exit_code <= 125 else 1)


def cmd_handoff(args: argparse.Namespace) -> None:
    t = active_task()
    if t["phase"] != "handoff":
        raise ValueError("Advance to handoff after documenting")
    unresolved = safe_text(args.unresolved)
    nxt = safe_text(args.next_action)
    filename = f"{now()[:10]}-{t['id'].lower()}-governance-handoff.md"
    rel = "docs/project/handoffs/" + filename
    path = relative_path(rel)
    if path.exists():
        raise ValueError("Handoff exists; use a new task rather than overwrite evidence")
    section_lines = []
    for phase, field in SECTIONS.items():
        part = t["sections"][field]
        section_lines.append(f"## {phase.capitalize()}\n\n{part['summary']}\n\nFiles: {', '.join(part['files']) or 'not separately listed'}\n")
    checks = "\n".join(f"- `{c['name']}`: exit={c['exit_code']}, {c['at']}; argv={json.dumps(c['argv'])}; output SHA-256={c['stdout_stderr_sha256']}" for c in t["checks"]) or "- None (blocked)"
    notes = "\n".join(f"- {n['at']} [{n['kind']}] {n['note']} — {n['evidence']}" for n in t["journal"]) or "- None"
    content = (f"# Task handoff — {t['id']} — {t['title']}\n\n"
               f"Status at authoring: implementation pending governance finish gate. Not a deployment claim.\n\n"
               f"**Objective:** {t['objective']}\n\n**Requirements:** {', '.join(t['requirements'])}\n\n"
               f"**Change class:** {t['change_class']}\n\n**Scoped files:** {', '.join(t['scope_files'])}\n\n"
               + "\n".join(section_lines) + f"\n## Recorded commands\n\n{checks}\n\n"
               f"## Findings / decisions / contradictions\n\n{notes}\n\n"
               f"## Remaining unresolved / blocked\n\n{unresolved}\n\n"
               f"## Next executable action\n\n{nxt}\n\n"
               "## Release truth\n\nNo production deployment, provider freshness, owner sign-off or model readiness is inferred from this handoff.\n")
    path.write_text(content, encoding="utf-8")
    t["sections"]["handoff"] = {"path": rel, "next_action": nxt, "unresolved": unresolved}
    t["next_action"] = nxt
    store_task(t)
    s = state(); s["latest_handoff"] = rel
    save(ROOT / "docs/governance/state.json", s)
    print(f"HANDOFF written: {rel}")


def cmd_finish() -> None:
    t = active_task()
    if t["phase"] != "handoff":
        raise ValueError("Cannot finish before handoff phase")
    failures = []
    for phase in PHASES:
        failures.extend(section_errors(t, phase))
    for name in t["scope_files"]:
        if name in t.get("deleted_files", []):
            if relative_path(name).exists():
                failures.append(f"Declared deletion still exists at finish: {name}")
        elif not relative_path(name).is_file():
            failures.append(f"Scoped file missing at finish: {name}")
    required = set(load(ROOT / "docs/governance/change-gates.json")["classes"][t["change_class"]])
    latest_by_name = {c["name"]: c for c in t["checks"]}
    hashes = hash_scoped(t["scope_files"])
    for name in required:
        check = latest_by_name.get(name)
        if not check or check["scope_sha256"] != hashes:
            failures.append(f"Validation `{name}` is stale or missing after scoped changes")
    if failures:
        raise ValueError("Closeout BLOCKED: " + "; ".join(sorted(set(failures))))
    t["status"] = "completed"
    t["closed_at"] = now()
    store_task(t)
    s = state(); s["active_task"] = None
    save(ROOT / "docs/governance/state.json", s)
    print(f"FINISHED {t['id']} — recorded documentation/check gates satisfied; not an automatic product or deployment approval")


def cmd_park(args: argparse.Namespace) -> None:
    t = active_task()
    t["status"] = "blocked"
    t["block_reason"] = safe_text(args.reason)
    t["next_action"] = safe_text(args.next_action)
    t["journal"].append({"at": now(), "kind": "risk", "note": t["block_reason"], "evidence": "blocking condition"})
    store_task(t)
    s = state(); s["active_task"] = None; save(ROOT / "docs/governance/state.json", s)
    print(f"PARKED {t['id']}; recovery details saved")


def cmd_resume(args: argparse.Namespace) -> None:
    s = state()
    if s["active_task"]:
        raise ValueError("Park or complete the current active task first")
    t = task_by_id(args.id)
    if t["status"] != "blocked":
        raise ValueError("Only blocked tasks may be resumed")
    t["status"] = "active"
    store_task(t)
    s["active_task"] = t["id"]
    save(ROOT / "docs/governance/state.json", s)
    print(f"RESUMED {t['id']}: {t['next_action']}")


def cmd_diff_gate(base: str) -> None:
    """PR-only: every changed path needs a modified closed task file in the PR."""
    if not re.fullmatch(r"[A-Za-z0-9_./^~-]{1,120}", base) or base.startswith("-"):
        raise ValueError("Unsafe git reference")
    args = ["git", "diff", "--name-only", "--diff-filter=ACMRTD", "-z", f"{base}...HEAD"]
    result = subprocess.run(args, cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise ValueError("Git diff failed. Fetch the PR base history before running diff-gate")
    paths = {raw.decode("utf-8") for raw in result.stdout.split(b"\x00") if raw}
    if not paths:
        print("DIFF-GATE: no changed paths")
        return
    deleted_result = subprocess.run(["git", "diff", "--name-only", "--diff-filter=D", "-z", f"{base}...HEAD"], cwd=ROOT, capture_output=True, check=False)
    if deleted_result.returncode:
        raise ValueError("Could not audit deleted paths")
    deleted = {raw.decode("utf-8") for raw in deleted_result.stdout.split(b"\x00") if raw}
    changed_task_paths = [p for p in paths if re.fullmatch(r"docs/governance/tasks/TASK-\d{8}-\d{3,5}\.json", p)]
    completed = []
    for p in changed_task_paths:
        t = load(relative_path(p, must_exist=True))
        if t["status"] == "completed" and t["sections"]["handoff"]["path"] in paths:
            completed.append(t)
    coverage = set()
    for t in completed:
        coverage.update(t["scope_files"])
        coverage.add(f"docs/governance/tasks/{t['id']}.json")
        coverage.add(t["sections"]["handoff"]["path"])
    covered_deletions = set().union(*(set(t.get("deleted_files", [])) for t in completed)) if completed else set()
    if deleted - covered_deletions:
        raise ValueError("Deleted paths lack explicit deletion approval in a closed task: " + ", ".join(sorted(deleted - covered_deletions)))
    uncovered = sorted(paths - coverage)
    if uncovered:
        raise ValueError("Changed paths not covered by a closed task + changed handoff in this PR: " + ", ".join(uncovered))
    print(f"DIFF-GATE: {len(paths)} changed paths covered by {len(completed)} completed task(s)")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("brief", help="Read a compact zero-chat restart digest")
    sub.add_parser("doctor", help="Check governance and task index integrity")
    start = sub.add_parser("start", help="Create one active durable task")
    start.add_argument("--id", required=True)
    start.add_argument("--title", required=True)
    start.add_argument("--objective", required=True)
    start.add_argument("--class", dest="change_class", required=True)
    start.add_argument("--requirements", nargs="+", required=True)
    start.add_argument("--files", nargs="+", required=True)
    start.add_argument("--deletions", nargs="*", default=[], help="Existing scoped paths intentionally removed")
    update = sub.add_parser("update", help="Record evidence for the current stage")
    update.add_argument("--section", choices=tuple(SECTIONS.values()), required=True)
    update.add_argument("--summary", required=True)
    update.add_argument("--files", nargs="*")
    amend = sub.add_parser("amend", help="Revise a completed stage with an append-only correction note")
    amend.add_argument("--section", choices=tuple(SECTIONS.values()), required=True)
    amend.add_argument("--summary", required=True)
    amend.add_argument("--reason", required=True)
    note = sub.add_parser("note", help="Add chronological finding, caveat, conflict or question")
    note.add_argument("--kind", choices=("observation", "assumption", "risk", "question", "decision_proposed", "correction", "next_step"), required=True)
    note.add_argument("--text", required=True)
    note.add_argument("--evidence")
    adv = sub.add_parser("advance", help="Move one stage forward after evidence gate")
    adv.add_argument("--to", choices=PHASES, required=True)
    check = sub.add_parser("run-check", help="Execute real test and store result digest only")
    check.add_argument("--name", required=True)
    check.add_argument("--timeout", type=int, default=300)
    check.add_argument("command", nargs=argparse.REMAINDER)
    handoff = sub.add_parser("handoff", help="Write the full dated handoff and update pointer")
    handoff.add_argument("--next", dest="next_action", required=True)
    handoff.add_argument("--unresolved", required=True)
    sub.add_parser("finish", help="Require all stages, docs and fresh successful checks")
    park = sub.add_parser("park", help="Park a blocked task, preserving restart information")
    park.add_argument("--reason", required=True)
    park.add_argument("--next", dest="next_action", required=True)
    resume = sub.add_parser("resume", help="Resume one blocked task")
    resume.add_argument("--id", required=True)
    diff = sub.add_parser("diff-gate", help="Git PR changed-file task traceability")
    diff.add_argument("--base", required=True)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.action == "brief":
            print(brief_text())
        elif args.action == "doctor":
            problems = doctor()
            for problem in problems:
                print("FAIL:", problem)
            print(f"{'PASS' if not problems else 'FAIL'}: governance structural check ({len(problems)} problem(s))")
            return int(bool(problems))
        elif args.action == "start":
            cmd_start(args)
        elif args.action == "update":
            cmd_update(args)
        elif args.action == "note":
            cmd_note(args)
        elif args.action == "amend":
            cmd_amend(args)
        elif args.action == "advance":
            cmd_advance(args)
        elif args.action == "run-check":
            cmd_check(args)
        elif args.action == "handoff":
            cmd_handoff(args)
        elif args.action == "finish":
            cmd_finish()
        elif args.action == "park":
            cmd_park(args)
        elif args.action == "resume":
            cmd_resume(args)
        elif args.action == "diff-gate":
            cmd_diff_gate(args.base)
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as error:
        print(f"GOVERNANCE BLOCKED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Opt-in copy of safe global instruction templates. Never runs on import."""
from __future__ import annotations

import argparse
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Print destinations; default behavior")
    group.add_argument("--apply", action="store_true", help="Copy to user home")
    parser.add_argument("--replace", action="store_true", help="Replace existing only with dated backup")
    args = parser.parse_args()
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    src_dest = [
        (ROOT / "docs/governance/global/codex/AGENTS.md", codex_home / "AGENTS.md"),
        (ROOT / "docs/governance/global/claude/CLAUDE.md", Path.home() / ".claude/CLAUDE.md"),
    ]
    for src, dest in src_dest:
        if not src.is_file():
            raise SystemExit(f"Missing template: {src}")
        if dest.exists() and not args.replace:
            print(f"SKIP existing {dest}; review and merge manually, or --replace with backup")
            continue
        if not args.apply:
            print(f"DRY RUN: {src.relative_to(ROOT)} → {dest}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = dest.with_name(dest.name + ".backup-" + timestamp)
            if backup.exists():
                raise SystemExit(f"Backup target already exists: {backup}")
            shutil.copy2(dest, backup)
            print(f"BACKUP: {backup}")
        shutil.copy2(src, dest)
        print(f"INSTALLED: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

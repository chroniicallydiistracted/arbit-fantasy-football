#!/usr/bin/env python3
"""Claude Code lifecycle nudge; policy enforcement lives in CLI and CI."""
from __future__ import annotations

import sys
from governance import brief_text, state, task_by_id


def main() -> int:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    # Read and discard bounded hook input so nothing from a user prompt is persisted.
    sys.stdin.read(1_000_000)
    if event == "session-start":
        print(brief_text())
    elif event == "stop":
        active = state().get("active_task")
        if active:
            t = task_by_id(active)
            print(f"Governance reminder: {active} remains {t['phase']}; persist work or park before treating it as complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Arbit — Claude Code entry point

Follow [AGENTS.md](AGENTS.md) as the cross-agent authority and
[governance start](docs/governance/START_HERE.md) for restart and accountability.
At session start run `python scripts/governance.py brief` and `doctor`; load the
active task and authoritative source documents, not previous conversational state.
Do not re-create parallel policies here. See [Claude rules](.claude/rules/).

Project hooks offer context reminders, but the executable `finish` check and CI
are the actual gates. Never assert that a hook is a security boundary or that a
Codex session automatically runs Claude hooks.

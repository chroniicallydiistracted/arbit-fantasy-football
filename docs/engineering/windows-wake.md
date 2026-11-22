# Waking the PC for Arbit's reads

Arbit's worker runs in WSL on the owner's PC, which the owner puts to sleep when they choose. The PC can't stay on all the time, and Sleep stays in the Start menu (OWN-065). While the PC sleeps every lane stops, including the ESPN reads that settle game-day inactives (R-066). `infra/windows/arbit-wake.ps1` wakes the PC for the windows that matter and lets it sleep again.

## What it does

- **Planner:** the Task Scheduler task `\Arbit\Plan wake windows` runs daily at 9:00 local and at logon. If the PC slept through 9:00, it runs on the next wake.
  - It reads ESPN's public NFL scoreboard: one cookie-free request per day ahead, a second apart, nine a day.
  - It replaces the `\Arbit\Wake …` tasks for the next 8 days.
- **Windows** (merged when less than 30 minutes apart):
  - **Games:** 120 minutes before each kickoff to 30 minutes after. Inactives are posted about 90 minutes before kickoff, and ESPN's status changes 60–85 minutes before (SRC-33). Kickoffs whose time ESPN hasn't set yet are skipped until it has.
  - **Injury report:** 12:00 and 19:15 US Eastern every day, 5 minutes before to 20 minutes after (OWN-063).
- **Each wake task** (`-Hold`):
  - It is set to wake the computer, and runs with no window (`conhost --headless`).
  - It makes sure WSL is running, then holds the PC awake until the window ends. Windows would otherwise put a timer-woken PC back to sleep after about two minutes.
  - At the end it puts the PC to sleep only if this task woke it (a wake within 10 minutes of the window's start) and nobody has used the keyboard or mouse since. If anyone used the PC, or it was already awake, it stays awake.
- **Log:** every step goes to `%LOCALAPPDATA%\Arbit\wake.log`.

A typical Sunday in Phoenix time: 5:30–8:00 AM for a London game, 9:00–11:30 AM, 12:05–2:55 PM and 4:20–6:50 PM. Weekdays: 9:55–10:20 AM and 5:10–5:35 PM.

## Requirements

- **Wake timers:** "Allow wake timers" must be on for AC power in the active power plan. It is on (index 1) in High performance, as checked on 2026-11-10.
- **User session:** the owner must stay signed in. The tasks run only when the user is logged on, which sleep preserves, so no password is stored.
- **Windows version:** Windows 11, for `conhost --headless`.

## Commands

From Windows PowerShell (or `powershell.exe` from WSL), with the repo's copy of the script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra\windows\arbit-wake.ps1 -Preview     # show the coming windows; changes nothing
powershell -NoProfile -ExecutionPolicy Bypass -File infra\windows\arbit-wake.ps1 -Install     # copy to %LOCALAPPDATA%\Arbit, register the planner, plan now
powershell -NoProfile -ExecutionPolicy Bypass -File infra\windows\arbit-wake.ps1 -Uninstall   # remove every \Arbit\ task and the installed copy
```

Re-run `-Install` after changing the script; the tasks run the installed copy, not the repo's.

## Checking that it worked

- **Did Windows wake on time?** Windows' System log, event 1 from `Power-Troubleshooter`, gives "Wake Source: Timer" and the time.
- **Did the task run?** `wake.log` shows `woken by this task: True` and how the window ended.
- **Did Arbit read?** The worker's league reads (`source_capture`) should appear inside each window. `scripts/model/espn_status_timing.py <season> <week>` shows whether ESPN's status was current before each kickoff.

Tests: `services/worker/tests/test_windows_wake.py` runs the real planner through WSL interop: a Sunday slate, a day with no games in daylight time, and windows that are already over.

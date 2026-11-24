#!/bin/sh
# Installs the M3-3 DvP prospective sweep as a systemd user timer (research only; not a service the
# app needs). Owner approval required before installing (it outlives the session).
#   sh infra/systemd/install-dvp-prospective.sh            install and start the timer
#   sh infra/systemd/install-dvp-prospective.sh --remove   stop and remove it
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
name=arbit-dvp-prospective
if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now "$name.timer" 2>/dev/null || true
  rm -f "$unit_dir/$name.service" "$unit_dir/$name.timer"
  systemctl --user daemon-reload
  echo "Removed: $name.timer"
  exit 0
fi
[ -f "$root/.env.local" ] || { echo "Run make local-env first." >&2; exit 1; }
uv_path=$(command -v uv) || { echo "uv is required." >&2; exit 1; }
mkdir -p "$unit_dir"
for kind in service timer; do
  sed -e "s|@ROOT@|$root|g" -e "s|@UV@|$uv_path|g" -e "s|@PATH@|$(dirname "$uv_path"):/usr/local/bin:/usr/bin:/bin|g" \
    "$root/infra/systemd/$name.$kind.template" > "$unit_dir/$name.$kind"
done
systemctl --user daemon-reload
systemctl --user enable --now "$name.timer"
echo "Timer running: systemctl --user list-timers $name.timer; logs: journalctl --user -u $name"

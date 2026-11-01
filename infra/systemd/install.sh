#!/bin/sh
# Installs the sync worker and member API as systemd user services. Local-first until a host is
# chosen (OWN-014). Both restart on failure and survive logout.
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
units="arbit-worker arbit-api"
if [ "${1:-}" = "--remove" ]; then
  for name in $units; do
    systemctl --user disable --now "$name.service" 2>/dev/null || true
    rm -f "$unit_dir/$name.service"
  done
  systemctl --user daemon-reload
  echo "Removed: $units"
  exit 0
fi
[ -f "$root/.env.local" ] || { echo "Run make local-env first." >&2; exit 1; }
[ -f "$root/.env.auth.local" ] || { echo "Create .env.auth.local first; see docs/engineering/member-application.md." >&2; exit 1; }
uv_path=$(command -v uv) || { echo "uv is required." >&2; exit 1; }
mkdir -p "$unit_dir"
for name in $units; do
  sed -e "s|@ROOT@|$root|g" -e "s|@UV@|$uv_path|g" -e "s|@PATH@|$(dirname "$uv_path"):/usr/local/bin:/usr/bin:/bin|g" \
    "$root/infra/systemd/$name.service.template" > "$unit_dir/$name.service"
done
systemctl --user daemon-reload
for name in $units; do systemctl --user enable --now "$name.service"; done
loginctl enable-linger "$(id -un)" 2>/dev/null || echo "Could not enable linger; services stop when you log out." >&2
echo "Running: $units. Logs: journalctl --user -u arbit-worker -f"

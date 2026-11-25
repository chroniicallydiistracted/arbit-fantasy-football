#!/bin/sh
# Installs the M3-3 DvP prospective sweep as a systemd user timer: research only, for the 2026
# weeks 12-18 window. Owner-authorized (OWN-077, DEC-02). It stops itself after the window.
#   sh infra/systemd/install-dvp-prospective.sh            install and start the timer
#   sh infra/systemd/install-dvp-prospective.sh --check    show its state and the next runs
#   sh infra/systemd/install-dvp-prospective.sh --remove   stop and remove it
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
evidence="${XDG_CONFIG_HOME:-$HOME/.config}/arbit/research-evidence"
name=arbit-dvp-prospective
slug=chroniicallydiistracted/arbit-fantasy-football
if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now "$name.timer" 2>/dev/null || true
  rm -f "$unit_dir/$name.service" "$unit_dir/$name.timer"
  systemctl --user daemon-reload
  echo "Removed: $name.timer (the archive and evidence key are kept)"
  exit 0
fi
if [ "${1:-}" = "--check" ]; then
  systemctl --user list-timers "$name.timer" --all --no-pager
  systemctl --user status "$name.service" --no-pager || true
  loginctl show-user "$(id -un)" -p Linger
  exit 0
fi
[ -f "$root/.env.local" ] || { echo "Run make local-env first." >&2; exit 1; }
uv_path=$(command -v uv) || { echo "uv is required." >&2; exit 1; }
[ "$(loginctl show-user "$(id -un)" -p Linger --value)" = yes ] || {
  echo "Linger is off: user timers stop at logout. Run: loginctl enable-linger $(id -un)" >&2; exit 1; }
# Publication: a key that can write to this repository only. Created here if missing; the owner
# registers it once: gh repo deploy-key add "$evidence/id_ed25519.pub" --allow-write
mkdir -p "$evidence" && chmod 700 "$evidence"
[ -f "$evidence/id_ed25519" ] || ssh-keygen -q -t ed25519 -N "" -C "arbit research evidence" -f "$evidence/id_ed25519"
[ -f "$evidence/env" ] || cat > "$evidence/env" <<ENV
ARBIT_EVIDENCE_REMOTE=git@github.com:$slug.git
ARBIT_EVIDENCE_SLUG=$slug
ARBIT_EVIDENCE_KEY=$evidence/id_ed25519
ENV
mkdir -p "$unit_dir"
for kind in service timer; do
  sed -e "s|@ROOT@|$root|g" -e "s|@UV@|$uv_path|g" -e "s|@PATH@|$(dirname "$uv_path"):/usr/local/bin:/usr/bin:/bin|g" \
    "$root/infra/systemd/$name.$kind.template" > "$unit_dir/$name.$kind"
done
systemctl --user daemon-reload
systemctl --user enable --now "$name.timer"
if ssh -i "$evidence/id_ed25519" -o IdentitiesOnly=yes -o BatchMode=yes -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  echo "Evidence key: registered."
else
  echo "Evidence key: NOT registered yet. Commitments will fail and be retried until it is:"
  echo "  gh repo deploy-key add $evidence/id_ed25519.pub --allow-write --title 'Arbit research evidence'"
fi
echo "Timer running: systemctl --user list-timers $name.timer; logs: journalctl --user -u $name"

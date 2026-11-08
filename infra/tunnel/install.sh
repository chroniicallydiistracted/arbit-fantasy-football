#!/bin/sh
# Serves Arbit at its public address through a dedicated Cloudflare Tunnel, run by the
# `arbit-tunnel` systemd user service. Needs cloudflared and a Cloudflare login for the domain's zone
# (~/.cloudflared/cert.pem). Other tunnels in the account are left alone. It doesn't touch arbit-api
# or arbit-worker; the app's own address changes separately (docs/engineering/member-application.md).
# `--remove` stops and removes the service; the tunnel and its DNS record stay in Cloudflare.
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
conf_dir="${XDG_CONFIG_HOME:-$HOME/.config}/arbit-tunnel"
host="${ARBIT_TUNNEL_HOST:-ffa.westfam.media}"
name="${ARBIT_TUNNEL_NAME:-arbit}"

if [ "${1:-}" = "--remove" ]; then
  systemctl --user disable --now arbit-tunnel.service 2>/dev/null || true
  rm -f "$unit_dir/arbit-tunnel.service"
  systemctl --user daemon-reload
  echo "Removed arbit-tunnel. The tunnel '$name' and the DNS record for $host remain in Cloudflare."
  exit 0
fi

cloudflared=$(command -v cloudflared) || { echo "Install cloudflared first." >&2; exit 1; }
[ -f "$HOME/.cloudflared/cert.pem" ] || { echo "Run 'cloudflared tunnel login' first." >&2; exit 1; }

tunnel_id() {
  "$cloudflared" tunnel list --name "$name" --output json 2>/dev/null | python3 -I -c '
import json, sys
live = [t["id"] for t in json.load(sys.stdin) or [] if t["deleted_at"].startswith("0001-")]
print(live[0] if len(live) == 1 else "")'
}

id=$(tunnel_id)
if [ -z "$id" ]; then
  "$cloudflared" tunnel create "$name" >/dev/null
  id=$(tunnel_id)
fi
[ -n "$id" ] || { echo "Couldn't find exactly one tunnel named '$name'." >&2; exit 1; }
credentials="$HOME/.cloudflared/$id.json"
[ -f "$credentials" ] || { echo "Tunnel '$name' exists, but $credentials is missing." >&2; exit 1; }

umask 077
mkdir -p "$conf_dir"
config="$conf_dir/config.yml"
sed -e "s|@TUNNEL_ID@|$id|g" -e "s|@CREDENTIALS@|$credentials|g" -e "s|@HOST@|$host|g" \
  "$root/infra/tunnel/config.yml.template" > "$config"
"$cloudflared" tunnel --config "$config" ingress validate >/dev/null 2>&1 \
  || { echo "The tunnel's ingress rules didn't validate." >&2; exit 1; }
"$cloudflared" tunnel --config "$config" ingress rule "https://$host/internal/league/current" 2>&1 \
  | grep -q 'service: http_status:404' || { echo "Operator reads aren't blocked; stopping." >&2; exit 1; }
"$cloudflared" tunnel --config "$config" ingress rule "https://$host/live" 2>&1 \
  | grep -q 'service: http://127.0.0.1:8000' || { echo "The app isn't the tunnel's origin." >&2; exit 1; }

mkdir -p "$unit_dir"
sed -e "s|@CLOUDFLARED@|$cloudflared|g" -e "s|@CONFIG@|$config|g" -e "s|@HOST@|$host|g" \
  "$root/infra/tunnel/arbit-tunnel.service.template" > "$unit_dir/arbit-tunnel.service"
systemctl --user daemon-reload
systemctl --user enable arbit-tunnel.service
systemctl --user restart arbit-tunnel.service

"$cloudflared" tunnel route dns "$name" "$host"
echo "Tunnel '$name' ($id) serves https://$host. Logs: journalctl --user -u arbit-tunnel -f"

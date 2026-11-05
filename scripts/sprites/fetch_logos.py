"""Fetch every NFL team's logo for the stadium board (slice 5, OWN-039), into private data/.

The owner asked for each team's logo on the board, drawn in its LED dots. Logos are the teams'
trademarks, so like the Gridiron art (OWN-015) they are kept for personal use inside the private
app only: stored under the ignored data/logos/, never committed or served publicly. The 32
current teams and their ESPN logo addresses come from nflverse's teams table. ESPN publishes each
logo for light backgrounds and for dark ones ("500-dark"); both are kept, and the board, which is
black, uses the dark one. A manifest records each file's address, hash and when it was read.
Reads are plain, cookie-free GETs.

Usage: uv run python scripts/sprites/fetch_logos.py
"""

import hashlib
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/live"))
import positions as depth  # noqa: E402

OUT = ROOT / "data/logos/espn"
RETIRED = ("OAK", "SD", "STL", "LAR")  # nflverse keeps old franchises; the Rams are "LA"
VARIANTS = {"dark": "/500-dark/", "light": "/500/"}


def main() -> None:
    teams = [row for row in depth._table("teams/teams_colors_logos") if row["team_abbr"] not in RETIRED]
    assert len(teams) == 32, len(teams)
    manifest = []
    for row in teams:
        url = row["team_logo_espn"]
        assert url.startswith("https://a.espncdn.com/i/teamlogos/nfl/500"), url
        code = url.rsplit("/", 1)[1].removesuffix(".png").upper()  # ESPN's code, such as WSH
        for variant, path in VARIANTS.items():
            address = f"https://a.espncdn.com/i/teamlogos/nfl{path}{code.lower()}.png"
            request = urllib.request.Request(address, headers={"User-Agent": "arbit-logo-fetch"})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
            assert body[:8] == b"\x89PNG\r\n\x1a\n", address
            target = OUT / variant / f"{code}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
            manifest.append(
                {
                    "team": code,
                    "nflverse": row["team_abbr"],
                    "variant": variant,
                    "url": address,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "read_at": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(manifest)} logos for {len(teams)} teams in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

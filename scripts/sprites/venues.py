"""Each NFL stadium's design for the live field's surround (OWN-050), measured from the owner's
private midfield references in data/nfl_stadium_mockups/.

The full-field camera sees the far-side stands and the stands behind both end zones. In each
reference frame, which looks down at the field from an elevated midfield seat as our camera does,
this measures those stands as a stack of bands from the field's edge up: wall, seats, concrete
aisles and fascia, suites, LED ribbons, and open sky. Heights are in yards as they appear at the
field's edge (pixels over the frame's pixels per yard there), so `stadium.py` can lay the same
stack over its own bowl at the same apparent heights. Only these measurements are kept, as a
design spec: no pixels of the references are used in the art (the owner's choice, 2026-11-08).

The spec is private like the references: data/stadiums/venues.json.

Usage:
  uv run --offline python scripts/sprites/venues.py            # measure every venue
  uv run --offline python scripts/sprites/venues.py --show SLUG
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/nfl_stadium_mockups"
SPEC = ROOT / "data/stadiums/venues.json"

# nflverse schedule stadium IDs to the references, for home games. Shared buildings use the
# home team's configuration. International and other neutral sites keep the generic stadium.
BY_STADIUM: dict[str, str | dict[str, str]] = {
    "PIT00": "acrisure-stadium",
    "VEG00": "allegiant-stadium",
    "KAN00": "arrowhead-stadium",
    "DAL00": "att-stadium",
    "CAR00": "bank-of-america-stadium",
    "NOR00": "caesars-superdome",
    "DEN00": "empower-field",
    "JAX00": "everbank-stadium",
    "DET00": "ford-field",
    "BOS00": "gillette-stadium",
    "MIA00": "hard-rock-stadium",
    "BUF00": "highmark-stadium",
    "CLE00": "huntington-bank-field",
    "GNB00": "lambeau-field",
    "SFO01": "levis-stadium",
    "PHI00": "lincoln-financial-field",
    "IND00": "lucas-oil-stadium",
    "SEA00": "lumen-field",
    "ATL97": "mercedes-benz-stadium",
    "NYC01": {"NYG": "metlife-stadium", "NYJ": "metlife-stadium:jets"},
    "BAL00": "mt-bank-stadium",
    "NAS00": "nissan-stadium",
    "WAS00": "northwest-stadium",
    "HOU00": "nrg-stadium",
    "CIN00": "paycor-stadium",
    "TAM00": "raymond-james-stadium",
    "LAX01": {"LA": "sofi-stadium:rams", "LAC": "sofi-stadium:chargers"},
    "CHI98": "soldier-field",
    "PHO00": "state-farm-stadium",
    "MIN01": "us-bank-stadium",
}


# Under a fixed or retractable roof, what reads as sky in a reference is the roof.
INDOOR = {
    "allegiant-stadium", "att-stadium", "caesars-superdome", "ford-field", "lucas-oil-stadium",
    "mercedes-benz-stadium", "nrg-stadium", "sofi-stadium", "state-farm-stadium", "us-bank-stadium",
}


def _end(end: list[dict], far: list[dict]) -> list[dict]:
    """An end zone's stack, cleaned: its own seats, ribbons and thin concrete are kept, but a thick
    slab of suites or concrete (a video board, a structure or a shadow beside the end zone, which
    the camera sees large) takes the far stands' design at that height instead."""
    out = []
    for band in end:
        thick = band["to"] - band["from"]
        if (band["kind"] == "suites" and thick > 2.5) or (band["kind"] == "concrete" and thick > 4.0):
            middle = (band["from"] + band["to"]) / 2
            like = next((b for b in far if b["from"] <= middle < b["to"]), None)
            if like is not None:
                band = {**band, "kind": like["kind"], "color": like["color"]}
        out.append(band)
    return out


def _kind(color: np.ndarray, start: float, top: float) -> str:
    r, g, b = (float(v) for v in color)
    high, low = max(r, g, b), min(r, g, b)
    light = (high + low) / 2 / 255
    saturation = (high - low) / high if high else 0.0
    if start < 6 and g > r + 8 and g > b + 8:
        return "apron"
    if start > 18 and b > r + 12 and g > r + 6 and light > 0.5:
        return "open"  # sky over an open bowl or an open end: light, and cyan rather than purple
    if light < 0.12:
        return "suites"  # dark glass, lit for a night game
    if light > 0.72 and saturation > 0.3:
        return "ribbon"  # an LED ribbon or a lit band
    if saturation < 0.16 and light > 0.5:
        return "concrete"
    return "seats"


def profile(img: np.ndarray, x0: int, x1: int, top_row: int, ppy: float, jump: float = 28.0) -> list[dict]:
    """The stack of bands in columns x0..x1, from `top_row` (the field's edge) up the frame."""
    rows = [np.median(img[y, x0:x1], axis=0) for y in range(top_row, -1, -1)]
    raw, start = [], 0
    for i in range(1, len(rows) + 1):
        if i == len(rows) or np.abs(rows[i] - np.median(rows[start:i], axis=0)).max() > jump:
            raw.append([start, i, np.median(rows[start:i], axis=0)])
            start = i
    merged: list[list] = []
    for band in raw:
        if merged and band[1] - band[0] < 5:  # a few rows of seam: part of the band below
            merged[-1][1] = band[1]
        else:
            merged.append(band)
    out = []
    for a, b, color in merged:
        start_yd, end_yd = a / ppy, b / ppy
        # The band's color as it reads: from its lit pixels, between the 50th and 90th
        # percentile of brightness, since seat rows alternate lit tops and shadowed risers.
        pixels = img[top_row - b + 1 : top_row - a + 1, x0:x1].reshape(-1, 3)
        if len(pixels) >= 8:
            light = pixels.mean(axis=1)
            low, high = np.percentile(light, [50, 90])
            chosen = pixels[(light >= low) & (light <= high)]
            if len(chosen):
                color = chosen.mean(axis=0)
        out.append(
            {
                "from": round(start_yd, 2),
                "to": round(end_yd, 2),
                "color": [int(c) for c in color],
                "kind": _kind(color, start_yd, len(rows) / ppy),
            }
        )
    # Once open sky starts, everything above it is open.
    for i, band in enumerate(out):
        if band["kind"] == "open":
            for later in out[i:]:
                later["kind"] = "open"
            break
    return [b for b in out if b["kind"] != "apron" or b["from"] > 6]


def measure(view: dict) -> dict:
    meta = json.loads((SOURCE / view["metadata"]).read_text())
    corners = meta["frame"]["estimated_visible_corners_px"]
    img = np.asarray(Image.open(SOURCE / view["frame"]).convert("RGB"), dtype=np.float64)
    (lx, ly), (rx, ry) = corners["far_left"], corners["far_right"]
    span = rx - lx
    ppy = span / 120.0  # the far edge spans both end zones
    far = int(round(min(ly, ry))) - 2
    width = img.shape[1]
    left = (max(0, int(lx - 0.36 * span)), max(1, int(lx - 0.12 * span)))
    right = (min(width - 1, int(rx + 0.12 * span)), min(width, int(rx + 0.36 * span)))
    return {
        "name": view["name"],
        "section": view.get("section"),
        "pixels_per_yard": round(ppy, 2),
        "pitch_deg": meta["frame"].get("aim_pitch_deg"),
        "far": profile(img, int(lx + 0.2 * span), int(lx + 0.8 * span), far, ppy),
        "left": profile(img, *left, far, ppy),
        "right": profile(img, *right, far, ppy),
    }


def key(view: dict) -> str:
    return view["venue_slug"] + (f":{view['configuration']}" if view["configuration"] not in (None, "giants") and view["is_alternate"] else "")


def build() -> dict:
    views = json.loads((SOURCE / "index.json").read_text())["views"]
    venues = {}
    for view in views:
        if view["region"] != "domestic":
            continue
        name = view["venue_slug"]
        if view["configuration"]:
            name += f":{view['configuration']}"
        measured = measure(view)
        measured["left"] = _end(measured["left"], measured["far"])
        measured["right"] = _end(measured["right"], measured["far"])
        measured["indoor"] = view["venue_slug"] in INDOOR
        venues[name] = measured
    # The primary configuration of a shared building is also its plain slug.
    for shared in ("metlife-stadium:giants", "sofi-stadium:rams"):
        if shared in venues:
            venues[shared.split(":")[0]] = venues[shared]
    return {"source": "data/nfl_stadium_mockups", "venues": venues, "by_stadium": BY_STADIUM}


def venue_for(stadium_id: str | None, home: str | None, spec: dict | None = None) -> dict | None:
    """The measured design of a home game's stadium, or None for a neutral or unknown site."""
    if not stadium_id:
        return None
    spec = spec if spec is not None else (json.loads(SPEC.read_text()) if SPEC.is_file() else None)
    if spec is None:
        return None
    found = spec["by_stadium"].get(stadium_id)
    if isinstance(found, dict):
        found = found.get(home or "")
    return spec["venues"].get(found) if found else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show")
    args = parser.parse_args()
    spec = build()
    SPEC.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    SPEC.write_text(json.dumps(spec, indent=1) + "\n")
    print(f"wrote {SPEC.relative_to(ROOT)}: {len(spec['venues'])} venues")
    if args.show:
        venue = spec["venues"][args.show]
        for side in ("far", "left", "right"):
            print(side)
            for band in venue[side]:
                print(f"   {band['from']:5.1f}-{band['to']:5.1f} {band['kind']:<9} {band['color']}")


if __name__ == "__main__":
    sys.exit(main())

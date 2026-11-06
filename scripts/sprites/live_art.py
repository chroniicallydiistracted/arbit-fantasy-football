"""Build one game's art for the browser's live field (OWN-042), into private data/live-art/<event>/.

The browser draws plays from their scripts in the full-field view, the standard (OWN-030). Its
camera is fixed, so the field is drawn here once, warped for that camera, exactly as the review
renderer draws it. Each team's sprites are painted here with the colors measured from the
Gridiron sheet listed for the game (OWN-028), in every pose and both skin sets, with the anchors
the browser needs to stand them and put the ball in their hands. The officials, the ball, the
teams' logo dots for the board and their name tag colors go with them. Everything is the owner's
private art (OWN-015, OWN-039): it stays in ignored data/ and the API serves it only behind a
session.

Usage:
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/live_art.py EVENT \\
      --home CODE=SHEET --away CODE=SHEET --field FIELD.png \\
      [--uniforms listed|usual] [--field-status listed|usual|plain]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(ROOT / "scripts/live"))
import board as B  # noqa: E402
import name_tag_preview as N  # noqa: E402
import positions as depth  # noqa: E402
import preview as P  # noqa: E402
import uniforms as U  # noqa: E402

OUT = ROOT / "data/live-art"
SKIN_SETS = (0, 32)  # as the review renders: chosen by ESPN ID (R-037, OWN-043)


def atlas(images: dict[str, Image.Image]) -> tuple[Image.Image, dict[str, list[int]]]:
    """Pack sprites into one image, row by row. Returns the sheet and each one's [x, y, w, h]."""
    width = 1024
    x = y = row = 0
    rects: dict[str, list[int]] = {}
    for name, image in images.items():
        if x + image.width > width:
            x, y, row = 0, y + row + 1, 0
        rects[name] = [x, y, image.width, image.height]
        x += image.width + 1
        row = max(row, image.height)
    sheet = Image.new("RGBA", (width, y + row + 1), (0, 0, 0, 0))
    for name, image in images.items():
        sheet.paste(image, tuple(rects[name][:2]))
    return sheet, rects


def team_sprites(uniform: dict | None, folder: Path, name: str) -> dict:
    images = {}
    for pose in P.FRAMES:
        if pose.startswith("off_"):
            continue
        for skin in SKIN_SETS:
            images[f"{pose}|{skin}"] = P.painted(pose, uniform, skin) if uniform else P.rgba(P.FRAMES[pose], skin)
    sheet, rects = atlas(images)
    sheet.save(folder / f"{name}.png")
    return {"image": f"{name}.png", "rects": rects}


def frame_info() -> dict:
    """Each pose's size, where its torso is (it stands there), and its hands for the ball."""
    info = {}
    for pose, rows in P.FRAMES.items():
        anchors = P.ANCHORS.get(pose.removesuffix("_e"), {})
        info[pose] = {
            "w": max(map(len, rows)),
            "h": len(rows),
            "torso": P.torso_x(rows),
            "near_hand": anchors.get("near_hand"),
            "chest": anchors.get("chest"),
        }
    return info


def ball_offsets() -> dict:
    """Where a passer or kicker holds the ball for a flight that starts at his hand (yards)."""
    found = {}
    for pose in P.FRAMES:
        try:
            found[pose] = list(P.ball_offset(pose))
        except (KeyError, ValueError, ZeroDivisionError):
            continue
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("event")
    parser.add_argument("--home", required=True, help="CODE=sheet path, or CODE for plain kits")
    parser.add_argument("--away", required=True)
    parser.add_argument("--field", help="the field image; omitted for the plain field")
    parser.add_argument("--uniforms", default="listed", choices=("listed", "usual", "plain"))
    parser.add_argument("--field-status", default="listed", choices=("listed", "usual", "plain"))
    args = parser.parse_args()
    folder = OUT / args.event
    folder.mkdir(parents=True, exist_ok=True)

    if args.field:
        P.FIELD = Image.open(args.field).convert("RGB").resize((1024 * P.SCALE, 486 * P.SCALE), Image.LANCZOS)
    P.SHOT = P.WIDE
    camera = P.Camera(P.WIDE.fixed_x, 0.0, P.WIDE)
    far = min(y for _x, y in camera.field_corners())
    board_height = (B.HEIGHT + 2 * B.HOUSING) * B.DOT
    board_top = round(far - 16 - board_height)
    top, bottom = camera.band()
    top = max(0, min(top, board_top - 10) - 60)  # room above the board for a punt's arc
    ground = camera.ground().crop((0, top, P.WIDE.width, bottom))
    ground.save(folder / "field.png")

    colors = depth.team_colors()
    teams = {}
    for side, spec in (("home", args.home), ("away", args.away)):
        code, _, sheet = spec.partition("=")
        uniform = U.measure_file(Path(sheet)) if sheet else None
        nflverse = depth.ESPN_TO_NFLVERSE.get(code, code)
        fill, second, _ = N.pair(colors[nflverse])
        teams[side] = {
            "code": code,
            "sprites": team_sprites(uniform, folder, f"sprites-{code}"),
            "tag": [list(fill), list(second)],
            "logo": [[x, y, *rgb] for (x, y), rgb in sorted(B.logo(code).items())],
        }
    officials = {pose: P.official_rgba(rows) for pose, rows in P.FRAMES.items() if pose.startswith("off_")}
    sheet, rects = atlas(officials)
    sheet.save(folder / "officials.png")
    ball = P.rgba(P.BALL, 0)
    ball.save(folder / "ball.png")
    shot = P.WIDE
    meta = {
        "version": 1,
        "event_id": args.event,
        "camera": {
            "width": shot.width,
            "height": shot.height,
            "rise": shot.rise,
            "back": shot.back,
            "look": list(shot.look),
            "focal": shot.focal,
            "x": shot.fixed_x,
            "min_art": shot.min_art,
            "ball_radius": shot.ball_radius,
            "tag_size": shot.tag_size,
            "caption_size": shot.caption_size,
        },
        "band": {"top": top, "bottom": bottom},
        "board": {"top": board_top},
        "art_pixel_yards": P.ART_PIXEL_YARDS,
        "cycles": {name: {"frames": frames, "step": step} for name, (frames, step) in P.CYCLES.items()},
        "frames": frame_info(),
        "ball_offsets": ball_offsets(),
        "ball": {"image": "ball.png", "half": P.BALL_HALF, "width": P.BALL_WIDTH},
        "posts": {"z": P.POST_Z, "half": P.POST_HALF, "crossbar": P.CROSSBAR, "top": P.POST_TOP, "at": [-10.0, 110.0]},
        "officials": {"image": "officials.png", "rects": rects},
        "skin_sets": list(SKIN_SETS),
        "teams": teams,
        "labels": {
            "uniforms": {"listed": None, "usual": "Usual uniforms; this game's not listed yet", "plain": "Uniforms not listed yet"}[args.uniforms],
            "field": {"listed": None, "usual": "Usual field; this game's not listed yet", "plain": "Field not listed yet"}[args.field_status],
        },
    }
    (folder / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f"wrote {folder}: field {ground.size}, {len(teams['home']['sprites']['rects'])} sprites a team")


if __name__ == "__main__":
    main()

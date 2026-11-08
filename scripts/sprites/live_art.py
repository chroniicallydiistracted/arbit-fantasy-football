"""Build one game's art for the browser's live field (OWN-042), into private data/live-art/<event>/.

The browser draws plays from their scripts in the full-field view, the standard (OWN-030). Its
camera is fixed, so the field is drawn here once, warped for that camera exactly as the review
renderer draws it, inside a stadium in the home team's colors (`stadium.py`). Each team's
sprites are painted here with the colors measured from the Gridiron sheet listed for the game
(OWN-028), in every pose and both skin sets, with the anchors the browser needs to stand them and
put the ball in their hands. The officials, the ball, the teams' logo dots for the board and
their name tag colors go with them. Everything is the owner's private art (OWN-015, OWN-039): it
stays in ignored data/ and the API serves it only behind a session.

Usage:
  uv run --with pillow --with numpy --with pyarrow python scripts/sprites/live_art.py EVENT \\
      --home CODE=SHEET --away CODE=SHEET --field FIELD.png \\
      [--uniforms listed|usual] [--field-status listed|usual|plain]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
sys.path.insert(0, str(ROOT / "scripts/live"))
import board as B  # noqa: E402
import name_tag_preview as N  # noqa: E402
import positions as depth  # noqa: E402
import preview as P  # noqa: E402
import stadium as S  # noqa: E402
import venues as V  # noqa: E402
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


def plain_uniform(side: str) -> dict:
    """Neutral contrasting practice kits for games without verified uniform art."""
    dark, light = (35, 39, 46), (218, 223, 230)
    base, trim = (dark, light) if side == "home" else (light, dark)
    return {
        "helmet": base,
        "helmet_stripe": None,
        "jersey": base,
        "numbers": trim,
        "pants": base,
        "pants_stripe": None,
        "socks": [base] * 10,
        "facemask": trim,
        "cleats": dark,
    }


def team_sprites(uniform: dict, folder: Path, name: str) -> dict:
    images = {}
    for pose in P.FRAMES:
        if pose.startswith("off_"):
            continue
        for skin in SKIN_SETS:
            images[f"{pose}|{skin}"] = P.painted(pose, uniform, skin)
    sheet, rects = atlas(images)
    sheet.save(folder / f"{name}.png")
    return {"image": f"{name}.png", "rects": rects}


def frame_band(camera: P.Camera) -> tuple[int, int, int]:
    """The rows the browser draws (top, bottom) and the board's top row, in frame rows."""
    far = min(y for _x, y in camera.field_corners())
    board_height = (B.HEIGHT + 2 * B.HOUSING) * B.DOT
    board_top = round(far - 16 - board_height)
    top, bottom = camera.band()
    top = max(0, min(top, board_top - 10) - 60)  # room above the board for a punt's arc
    return top, bottom, board_top


def team_rgb(colors: dict[str, list[str]], spec: str) -> tuple[S.RGB, ...]:
    """A team's colors from nflverse, first to last, for its stadium and its fans."""
    code = spec.partition("=")[0]
    return tuple(S.rgb(value) for value in colors[depth.ESPN_TO_NFLVERSE.get(code, code)])


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
    parser.add_argument("--uniforms", choices=("listed", "usual", "plain"))
    parser.add_argument("--home-uniform-status", choices=("listed", "usual", "plain"))
    parser.add_argument("--away-uniform-status", choices=("listed", "usual", "plain"))
    parser.add_argument("--field-status", choices=("listed", "usual", "plain"))
    parser.add_argument("--output-root", type=Path, default=OUT)
    args = parser.parse_args()
    if not args.event.isascii() or not args.event.isdecimal() or args.event.startswith("0"):
        parser.error("event must be a positive decimal ID")
    target = args.output_root / args.event
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".stage-", dir=target) as work:
        stage = Path(work) / "bundle"
        stage.mkdir()
        build(args, stage)
        sha = hashlib.sha256()
        for file in sorted(stage.iterdir()):
            sha.update(file.name.encode())
            sha.update(file.read_bytes())
        revision = sha.hexdigest()
        destination = target / revision
        try:
            stage.rename(destination)
        except OSError:
            if not destination.is_dir():
                raise
        pointer = Path(work) / "current.txt"
        pointer.write_text(revision + "\n")
        pointer.replace(target / "current.txt")
    print(f"published {target} ({revision})")


def build(args: argparse.Namespace, folder: Path) -> None:
    if args.field:
        P.FIELD = Image.open(args.field).convert("RGB").resize((1024 * P.SCALE, 486 * P.SCALE), Image.LANCZOS)
    P.SHOT = P.WIDE
    camera = P.Camera(P.WIDE.fixed_x, 0.0, P.WIDE)
    top, bottom, board_top = frame_band(camera)
    colors = depth.team_colors()
    palette = S.Colors(
        home=team_rgb(colors, args.home),
        away=team_rgb(colors, args.away),
        turf=S.turf_color(P.FIELD),
        neutral=args.event in depth.neutral_sites(),
    )
    # The home stadium's own design (OWN-050), measured from the owner's references; neutral and
    # international sites, and any stadium without a measured design, keep the generic bowl.
    stadium_id, home_team, neutral = depth.venues().get(args.event, (None, None, True))
    design = None if neutral else V.venue_for(stadium_id, home_team)
    S.surround(camera, P.FIELD, (top, bottom), palette, seed=int(args.event), venue=design).save(folder / "field.png")

    teams = {}
    labels = {}
    for side, spec in (("home", args.home), ("away", args.away)):
        code, _, sheet = spec.partition("=")
        status = getattr(args, f"{side}_uniform_status") or args.uniforms
        if not sheet:
            status = "plain"
        elif status in (None, "plain"):
            status = "listed"
        labels[f"{side}_uniform"] = {
            "listed": None,
            "usual": f"{code} usual uniform",
            "plain": f"{code} plain uniform",
        }[status]
        uniform = U.measure_file(Path(sheet)) if sheet else plain_uniform(side)
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
    field_status = (args.field_status or "listed") if args.field else "plain"
    labels["field"] = {
        "listed": None,
        "usual": "Usual field",
        "plain": "Plain field",
    }[field_status]
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
        "labels": labels,
    }
    (folder / "meta.json").write_text(json.dumps(meta, separators=(",", ":")))


if __name__ == "__main__":
    main()

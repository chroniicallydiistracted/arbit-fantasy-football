"""Review GIFs: every motion played in order, two teams side by side, the ball drawn where it is held.
Reads the installed frames. Usage: showcase.py OUTDIR"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
import frames as F  # noqa: E402

PAL = F.palette()
ANCHORS = F.anchors()
BALL = [line for line in (F.ASSETS / "ball.txt").read_text().splitlines() if line and not line.startswith("==")]
SEQUENCES = {
    "run": (["run1", "run_pass", "run_knee", "run_float", "run3", "run_far_pass", "run2", "run_far_float"] * 3, 70, "chest"),
    "dropback and throw": (["ready", "drop_a", "drop_b", "drop_c", "drop_b", "throw_cock", "throw_mid", "throw_rel", "throw_follow", "throw_follow", "stand"], 110, "hand_until_release"),
    "catch": (["run1", "run_pass", "catch_reach", "catch_high", "catch_secure", "run3", "run_far_pass", "run2"], 110, "after_catch"),
    "low and diving catch": (["run1", "catch_low", "catch_low", "dive_catch", "dive_catch", "ground", "ground"], 140, "after_catch"),
    "tackled": (["run1", "run_pass", "hit", "stumble", "fall_30", "fall_60", "ground", "ground", "rise_1", "rise_2", "rise_3", "stand"], 110, "chest"),
    "tackler": (["run3", "run_far_pass", "lunge", "wrap", "drive", "tackle_dive", "fall_60", "ground", "ground"], 120, None),
    "knocked back": (["run1", "hit_back", "fall_back_30", "fall_back_60", "ground_back", "ground_back", "rise_1", "rise_2", "rise_3"], 120, None),
    "fumble recovery": (["run3", "catch_low", "recover", "recover", "recover", "rise_2", "rise_3"], 140, "from_recover"),
    "field goal kick": (["stand", "run_pass", "kick_plant", "kick_swing", "kick_strike", "kick_follow", "kick_follow", "stand", "arms_up", "arms_jump", "arms_up", "arms_jump"], 110, None),
    "punt": (["ready", "punt_hold", "punt_hold", "punt_drop", "punt_strike", "punt_follow", "punt_follow", "stand"], 120, "until_strike"),
    "snap and hold": (["snap_ready", "snap_ready", "snap_release", "ready", "hold_ready", "hold_ready", "hold_catch", "hold_place", "hold_place", "hold_ready"], 130, None),
    "celebrate": (["stand", "arm", "arms_up", "arms_jump", "arms_up", "point", "spike"], 160, None),
    "quarterback slide": (["run1", "run_pass", "slide", "slide", "slide", "rise_2", "rise_3"], 140, "chest"),
}
SCALE, CELL, BG = 6, 64, (92, 104, 92, 255)


def rgba(rows, color_set):
    w = max(map(len, rows))
    im = Image.new("RGBA", (w, len(rows)), (0, 0, 0, 0))
    px = im.load()
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c != ".":
                px[x, y] = (*PAL[c][color_set], 255)
    return im


def holds(rule, i, seq):
    name = seq[i]
    if rule == "chest":
        return True
    if rule == "hand_until_release":
        return seq.index("throw_rel") > i
    if rule == "after_catch":
        return name in ("catch_secure", "run3", "run_far_pass", "run2", "ground") or (name == "dive_catch" and i > seq.index("dive_catch"))
    if rule == "from_recover":
        return i >= seq.index("recover")
    if rule == "until_strike":
        return i < seq.index("punt_strike")
    return False


def frame_image(name, color_set, with_ball):
    frames = F.all_frames()
    sprite = rgba(frames[name], color_set)
    lift = ANCHORS.get(name, {}).get("lift", 0)
    cell = Image.new("RGBA", (CELL, CELL), BG)
    x0 = round(CELL / 2 - F.torso_x(frames[name]))
    y0 = CELL - 4 - sprite.height - int(lift)
    cell.alpha_composite(sprite, (max(0, x0), y0))
    if with_ball and name in ANCHORS:
        spot = ANCHORS[name]["near_hand" if name.startswith(("throw", "punt")) else "chest"]
        ball = rgba(BALL, 0)
        cell.alpha_composite(ball, (round(max(0, x0) + spot[0] - ball.width / 2), round(y0 + spot[1] - ball.height / 2)))
    return cell


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    teams = (11, 28 + 32)  # Green Bay, darker skin; Seattle, lighter skin
    for title, (seq, ms, rule) in SEQUENCES.items():
        images = []
        for i, name in enumerate(seq):
            pair = Image.new("RGBA", (CELL * len(teams), CELL), BG)
            for j, team in enumerate(teams):
                pair.alpha_composite(frame_image(name, team, holds(rule, i, seq)), (CELL * j, 0))
            big = pair.resize((pair.width * SCALE, pair.height * SCALE), Image.NEAREST)
            ImageDraw.Draw(big).text((8, 6), f"{title}: {name}", fill=(255, 255, 255))
            images.append(big.convert("P", palette=Image.ADAPTIVE))
        images[0].save(out / f"{title.replace(' ', '-')}.gif", save_all=True, append_images=images[1:], duration=ms, loop=0, disposal=2)
    print("wrote", len(SEQUENCES), "motion GIFs to", out)

"""Every pose the plays need, as COCO-18 skeletons for PixelLab's skeleton animator.

Coordinates are pixels on a square canvas with the ground 4 pixels above the bottom edge. Players
face east, so RIGHT limbs are the near ones. Angles are measured from straight down, positive
toward east: 90 is forward, 180 straight up, -90 backward.
"""

import json
import math
import sys
from pathlib import Path

TORSO, UPPER, FORE, THIGH, SHIN = 8.5, 4.5, 4.0, 7.5, 6.8
LABELS = ["NOSE", "NECK", "RIGHT SHOULDER", "RIGHT ELBOW", "RIGHT ARM", "LEFT SHOULDER", "LEFT ELBOW", "LEFT ARM",
          "RIGHT HIP", "RIGHT KNEE", "RIGHT LEG", "LEFT HIP", "LEFT KNEE", "LEFT LEG", "RIGHT EYE", "LEFT EYE", "RIGHT EAR", "LEFT EAR"]
Z = {"RIGHT": 4, "LEFT": 0}

# Joints placed by hand from each original's pixels, on a 48 canvas with the ground at y=44.
HAND = {
    "run1": {"NOSE": (34.5, 21.0), "RIGHT EYE": (34.0, 20.0), "LEFT EYE": (34.4, 20.1), "RIGHT EAR": (31.6, 19.8), "LEFT EAR": (32.0, 20.0),
             "NECK": (30.5, 22.5), "RIGHT SHOULDER": (29.0, 21.5), "LEFT SHOULDER": (25.0, 20.5), "RIGHT ELBOW": (29.5, 25.5), "RIGHT ARM": (33.0, 24.5),
             "LEFT ELBOW": (21.5, 23.5), "LEFT ARM": (22.5, 26.0), "RIGHT HIP": (25.0, 29.5), "RIGHT KNEE": (19.5, 35.5), "RIGHT LEG": (13.5, 38.0),
             "LEFT HIP": (24.0, 29.0), "LEFT KNEE": (30.0, 34.5), "LEFT LEG": (31.0, 41.0)},
    "run2": {"NOSE": (32.0, 19.5), "RIGHT EYE": (31.2, 18.6), "LEFT EYE": (31.6, 18.7), "RIGHT EAR": (28.5, 18.5), "LEFT EAR": (29.0, 18.7),
             "NECK": (28.0, 21.5), "RIGHT SHOULDER": (26.5, 21.5), "LEFT SHOULDER": (22.5, 20.5), "RIGHT ELBOW": (23.5, 25.0), "RIGHT ARM": (27.5, 27.5),
             "LEFT ELBOW": (20.5, 24.5), "LEFT ARM": (21.0, 26.5), "RIGHT HIP": (21.0, 28.0), "RIGHT KNEE": (20.5, 33.0), "RIGHT LEG": (18.0, 38.5),
             "LEFT HIP": (23.0, 28.0), "LEFT KNEE": (26.5, 32.5), "LEFT LEG": (24.5, 36.5)},
    "run3": {"NOSE": (35.0, 20.5), "RIGHT EYE": (34.2, 19.6), "LEFT EYE": (34.6, 19.7), "RIGHT EAR": (31.5, 19.5), "LEFT EAR": (32.0, 19.7),
             "NECK": (30.5, 22.5), "RIGHT SHOULDER": (24.0, 20.0), "LEFT SHOULDER": (28.5, 21.0), "RIGHT ELBOW": (22.5, 23.5), "RIGHT ARM": (23.0, 26.5),
             "LEFT ELBOW": (29.0, 24.5), "LEFT ARM": (31.5, 25.5), "RIGHT HIP": (25.0, 29.0), "RIGHT KNEE": (31.0, 33.5), "RIGHT LEG": (32.0, 41.0),
             "LEFT HIP": (23.5, 29.0), "LEFT KNEE": (21.0, 34.5), "LEFT LEG": (14.0, 37.0)},
    "stand": {"NOSE": (29.0, 16.0), "RIGHT EYE": (28.5, 15.4), "LEFT EYE": (29.2, 15.5), "RIGHT EAR": (26.0, 14.5), "LEFT EAR": (26.5, 14.8),
              "NECK": (27.5, 17.5), "RIGHT SHOULDER": (21.5, 18.5), "LEFT SHOULDER": (28.0, 18.5), "RIGHT ELBOW": (18.5, 21.5), "RIGHT ARM": (16.8, 23.5),
              "LEFT ELBOW": (29.0, 22.0), "LEFT ARM": (30.0, 25.5), "RIGHT HIP": (21.5, 28.0), "RIGHT KNEE": (21.5, 34.5), "RIGHT LEG": (21.5, 41.5),
              "LEFT HIP": (26.0, 28.0), "LEFT KNEE": (27.0, 34.5), "LEFT LEG": (27.5, 40.5)},
    "kneel": {"NOSE": (29.5, 23.0), "RIGHT EYE": (28.8, 22.2), "LEFT EYE": (29.2, 22.3), "RIGHT EAR": (26.0, 22.0), "LEFT EAR": (26.5, 22.2),
              "NECK": (25.5, 24.5), "RIGHT SHOULDER": (24.5, 25.5), "LEFT SHOULDER": (21.5, 25.0), "RIGHT ELBOW": (26.0, 30.0), "RIGHT ARM": (31.5, 29.5),
              "LEFT ELBOW": (23.0, 29.5), "LEFT ARM": (29.0, 29.0), "RIGHT HIP": (21.0, 33.5), "RIGHT KNEE": (20.5, 42.0), "RIGHT LEG": (16.0, 40.5),
              "LEFT HIP": (22.5, 33.0), "LEFT KNEE": (31.0, 34.5), "LEFT LEG": (30.0, 40.0)},
}


def angle(a, b):
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1]))


def fit(s):
    """FK parameters that reproduce a hand skeleton: hips, lean, and each limb's two angles."""
    hip = ((s["RIGHT HIP"][0] + s["LEFT HIP"][0]) / 2, (s["RIGHT HIP"][1] + s["LEFT HIP"][1]) / 2)
    lean = math.degrees(math.atan2(s["NECK"][0] - hip[0], hip[1] - s["NECK"][1]))
    limb = lambda a, b, c: (angle(s[a], s[b]), angle(s[b], s[c]))
    return {"hip": hip, "t": lean,
            "na": limb("RIGHT SHOULDER", "RIGHT ELBOW", "RIGHT ARM"), "fa": limb("LEFT SHOULDER", "LEFT ELBOW", "LEFT ARM"),
            "nl": limb("RIGHT HIP", "RIGHT KNEE", "RIGHT LEG"), "fl": limb("LEFT HIP", "LEFT KNEE", "LEFT LEG")}


def v(a, n):
    r = math.radians(a)
    return math.sin(r) * n, math.cos(r) * n


def pose(hip, t, na, fa, nl, fl):
    """Joints from hip centre, torso lean and limb angles (near arm, far arm, near leg, far leg)."""
    hx, hy = hip
    tr = math.radians(t)
    up, fwd = (math.sin(tr), -math.cos(tr)), (math.cos(tr), math.sin(tr))
    neck = (hx + up[0] * TORSO, hy + up[1] * TORSO)
    head = (neck[0] + up[0] * 2.5, neck[1] + up[1] * 2.5)
    j = {"NECK": neck, "NOSE": (head[0] + fwd[0] * 2.4, head[1] + fwd[1] * 2.4),
         "RIGHT EYE": (head[0] + fwd[0] * 1.8 + up[0] * 0.8, head[1] + fwd[1] * 1.8 + up[1] * 0.8),
         "LEFT EYE": (head[0] + fwd[0] * 2.0 + up[0] * 0.7, head[1] + fwd[1] * 2.0 + up[1] * 0.7),
         "RIGHT EAR": (head[0] - fwd[0] * 0.6, head[1] - fwd[1] * 0.6), "LEFT EAR": (head[0] - fwd[0] * 0.3, head[1] - fwd[1] * 0.3)}
    for side, (a1, a2), off in (("RIGHT", na, 0.6), ("LEFT", fa, -2.0)):
        sh = (neck[0] - up[0] * 1.2 + fwd[0] * off, neck[1] - up[1] * 1.2 + fwd[1] * off)
        el = (sh[0] + v(a1, UPPER)[0], sh[1] + v(a1, UPPER)[1])
        j[f"{side} SHOULDER"], j[f"{side} ELBOW"], j[f"{side} ARM"] = sh, el, (el[0] + v(a2, FORE)[0], el[1] + v(a2, FORE)[1])
    for side, (b1, b2), off in (("RIGHT", nl, 0.5), ("LEFT", fl, -0.5)):
        hp = (hx + fwd[0] * off, hy + fwd[1] * off)
        kn = (hp[0] + v(b1, THIGH)[0], hp[1] + v(b1, THIGH)[1])
        j[f"{side} HIP"], j[f"{side} KNEE"], j[f"{side} LEG"] = hp, kn, (kn[0] + v(b2, SHIN)[0], kn[1] + v(b2, SHIN)[1])
    return j


def P(p):
    return pose(p["hip"], p["t"], p["na"], p["fa"], p["nl"], p["fl"])


def mix(a, b, k):
    lerp = lambda x, y: x + (y - x) * k
    pair = lambda x, y: (lerp(x[0], y[0]), lerp(x[1], y[1]))
    return {"hip": pair(a["hip"], b["hip"]), "t": lerp(a["t"], b["t"]), **{key: pair(a[key], b[key]) for key in ("na", "fa", "nl", "fl")}}


def swap(p):
    """The opposite phase of a stride: near and far limbs trade angles."""
    return {**p, "na": p["fa"], "fa": p["na"], "nl": p["fl"], "fl": p["nl"]}


def keypoints(j, size, shift=(0.0, 0.0)):
    out = []
    for label in LABELS:
        x, y = j[label]
        side = label.split()[0]
        z = Z.get(side, 2) if "EYE" not in label and "EAR" not in label else (3 if side == "RIGHT" else 1)
        out.append({"label": label, "x": round((x + shift[0]) / size, 4), "y": round((y + shift[1]) / size, 4), "z_index": z})
    return out


R1, R2, R3 = fit(HAND["run1"]), fit(HAND["run2"]), fit(HAND["run3"])
ST, KN = fit(HAND["stand"]), fit(HAND["kneel"])
F6 = R2                      # far knee drive, near leg pushing off: run2
F2 = swap(R2)                # near knee drive
F1 = {**mix(R1, F2, 0.5), "nl": (5, -75), "fl": (2, -3)}            # near leg passes under the hip, far leg in stance
F3 = {**mix(F2, R3, 0.5), "hip": (25.0, 28.0), "nl": (40, 20), "fl": (-45, -85)}   # float, near leg reaching
F5 = {**swap(F1), "hip": F1["hip"]}
F7 = {**swap(F3), "hip": F3["hip"]}


def stand_like(dx=0.0, dy=0.0, **kw):
    base = {"hip": (24.0 + dx, 28.0 + dy), "t": 8, "na": (-20, 10), "fa": (15, 10), "nl": (0, 0), "fl": (8, 2)}
    base.update(kw)
    return base


BATCHES = {
    # The approved fall, redrawn in the key colours. Same poses and seed as the first test.
    "run": ("run1", 48, "sprint, running cycle", [
        ("run_pass", F1), ("run_knee", F2), ("run_float", F3), ("run3_g", R3), ("run_far_pass", F5), ("run2_g", R2), ("run_far_float", F7), ("run1_g", R1)]),
    "qb": ("stand", 56, "quarterback takes the snap, drops back and throws, then a center snap", [
        ("ready", stand_like(dy=2.0, t=18, na=(60, 150), fa=(55, 140), nl=(-12, 8), fl=(18, -6))),
        ("drop_a", stand_like(dx=-1.0, dy=0.5, t=6, na=(45, 150), fa=(40, 145), nl=(-25, 5), fl=(20, -10))),
        ("drop_b", stand_like(dx=-3.0, dy=0.5, t=6, na=(45, 150), fa=(40, 145), nl=(18, -12), fl=(-22, 3))),
        ("drop_c", stand_like(dx=-5.0, dy=1.5, t=10, na=(45, 150), fa=(40, 145), nl=(-25, -10), fl=(22, 4))),
        ("throw_cock", stand_like(dx=-5.0, dy=1.0, t=-6, na=(-115, 175), fa=(85, 100), nl=(-28, -12), fl=(28, 10))),
        ("throw_mid", stand_like(dx=-4.0, dy=1.5, t=8, na=(175, 140), fa=(60, 30), nl=(-30, -20), fl=(30, 8))),
        ("throw_rel", stand_like(dx=-3.0, dy=2.0, t=24, na=(115, 95), fa=(10, -20), nl=(-38, -45), fl=(32, 6))),
        ("throw_follow", stand_like(dx=-2.0, dy=2.5, t=34, na=(35, 0), fa=(-20, -30), nl=(-20, -70), fl=(30, 8))),
        ("snap_ready", stand_like(dx=0.0, dy=3.0, t=78, na=(5, 0), fa=(0, -5), nl=(-35, 15), fl=(35, -15))),
        ("snap_release", stand_like(dx=0.0, dy=2.5, t=72, na=(-35, -70), fa=(-30, -65), nl=(-35, 15), fl=(35, -15))),
    ]),
    "kick": ("stand", 56, "kicker and punter kicking a football, then celebrating", [
        ("kick_plant", stand_like(dx=1.0, dy=1.0, t=-4, na=(-70, -60), fa=(95, 90), nl=(-45, -105), fl=(8, 0))),
        ("kick_swing", stand_like(dx=1.5, dy=1.0, t=-6, na=(-60, -40), fa=(100, 95), nl=(10, -55), fl=(6, 0))),
        ("kick_strike", stand_like(dx=2.0, dy=0.5, t=-12, na=(-80, -70), fa=(105, 100), nl=(55, 65), fl=(4, 0))),
        ("kick_follow", stand_like(dx=3.0, dy=0.0, t=-18, na=(-100, -90), fa=(110, 120), nl=(115, 125), fl=(0, 0))),
        ("punt_hold", stand_like(dx=0.0, dy=0.5, t=6, na=(75, 88), fa=(70, 85), nl=(-15, -5), fl=(15, 2))),
        ("punt_drop", stand_like(dx=1.5, dy=1.0, t=4, na=(70, 60), fa=(-40, -30), nl=(-30, -40), fl=(10, 0))),
        ("punt_strike", stand_like(dx=2.5, dy=0.5, t=-8, na=(-60, -50), fa=(95, 100), nl=(80, 90), fl=(4, 0))),
        ("punt_follow", stand_like(dx=3.5, dy=0.0, t=-20, na=(-90, -80), fa=(110, 125), nl=(140, 150), fl=(0, 0))),
        ("arms_up", stand_like(dy=0.0, t=2, na=(172, 178), fa=(-172, -178), nl=(-5, 0), fl=(8, 2))),
        ("arms_jump", stand_like(dy=-5.0, t=4, na=(165, 175), fa=(-165, -175), nl=(-20, -45), fl=(10, -35))),
    ]),
    "catch_tackle": ("run1", 48, "receiver catches, dives; defender lunges, dives and tackles", [
        ("catch_reach", {**F1, "na": (95, 100), "fa": (88, 95), "t": 30}),
        ("catch_high", {"hip": (25.0, 24.5), "t": 8, "na": (165, 172), "fa": (160, 168), "nl": (35, -30), "fl": (-15, -55)}),
        ("catch_secure", {**R3, "na": (35, 155), "fa": (30, 150)}),
        ("catch_low", {"hip": (24.0, 32.0), "t": 62, "na": (40, 45), "fa": (30, 40), "nl": (-40, -95), "fl": (45, -10)}),
        ("dive_catch", {"hip": (20.0, 34.0), "t": 84, "na": (96, 96), "fa": (90, 92), "nl": (-82, -86), "fl": (-76, -90)}),
        ("lunge", {"hip": (23.0, 31.5), "t": 52, "na": (80, 70), "fa": (72, 62), "nl": (-45, -55), "fl": (40, -5)}),
        ("tackle_dive", {"hip": (19.0, 36.5), "t": 86, "na": (100, 112), "fa": (92, 104), "nl": (-80, -90), "fl": (-72, -95)}),
        ("wrap", {"hip": (23.0, 31.0), "t": 46, "na": (92, 165), "fa": (84, 158), "nl": (-32, -62), "fl": (22, -2)}),
        ("drive", {"hip": (23.5, 31.0), "t": 60, "na": (70, 150), "fa": (64, 145), "nl": (-48, -72), "fl": (12, -22)}),
    ]),
    "recover": ("run1", 48, "player falls backward, lies on the ground, gets up; recovers a fumble", [
        ("hit_back", {"hip": (24.0, 30.0), "t": -18, "na": (110, 130), "fa": (100, 125), "nl": (30, 8), "fl": (-8, -2)}),
        ("fall_back_30", {"hip": (22.5, 32.5), "t": -45, "na": (120, 150), "fa": (110, 140), "nl": (60, 25), "fl": (50, 60)}),
        ("fall_back_60", {"hip": (22.0, 37.5), "t": -70, "na": (130, 165), "fa": (120, 160), "nl": (95, 120), "fl": (80, 100)}),
        ("ground_back", {"hip": (27.0, 41.0), "t": -90, "na": (-60, -100), "fa": (-75, -95), "nl": (88, 92), "fl": (84, 96)}),
        ("rise_1", {"hip": (21.0, 38.5), "t": 68, "na": (0, 2), "fa": (-4, -2), "nl": (-75, -88), "fl": (-72, -92)}),
        ("rise_2", {**KN, "na": (20, 30), "fa": (10, 20), "t": KN["t"] + 6}),
        ("rise_3", stand_like(dx=0.0, dy=1.0, t=18, na=(10, 30), fa=(0, 20), nl=(-8, -4), fl=(12, 0))),
        ("recover", {"hip": (24.0, 39.0), "t": 82, "na": (60, 170), "fa": (55, 165), "nl": (85, -95), "fl": (80, -100)}),
    ]),
    "redo_stand": ("stand", 56, "football player celebrates with both arms raised, spikes the ball, points forward", [
        ("arms_up", stand_like(t=3, na=(150, 168), fa=(140, 162), nl=(-6, 0), fl=(8, 2))),
        ("spike", stand_like(dx=1.0, dy=1.5, t=16, na=(70, 25), fa=(-25, -10), nl=(-22, -8), fl=(20, 4))),
        ("point", stand_like(t=4, na=(92, 94), fa=(10, 5), nl=(-6, 0), fl=(8, 2))),
    ]),
    "redo_run": ("run1", 48, "defender dives to tackle; runner stiff-arms; quarterback slides feet first", [
        ("tackle_dive", {"hip": (19.0, 35.5), "t": 86, "na": (78, 84), "fa": (112, 118), "nl": (-80, -90), "fl": (-72, -95)}),
        ("stiff_arm", {**R3, "na": (90, 92), "fa": (30, 150)}),
        ("slide", {"hip": (22.0, 40.0), "t": -35, "na": (-30, 10), "fa": (-45, -20), "nl": (86, 92), "fl": (80, 95)}),
    ]),
    "hold": ("kneel", 48, "holder kneels and places a football for a field goal", [
        ("hold_ready", {**KN, "na": (60, 80), "fa": (55, 75)}),
        ("hold_catch", {**KN, "t": KN["t"] + 4, "na": (88, 105), "fa": (82, 100)}),
        ("hold_place", {**KN, "t": KN["t"] + 14, "na": (40, 15), "fa": (70, 120)}),
    ]),
}


def batch(name):
    ref, size, action, frames = BATCHES[name]
    shift = ((size - 48) / 2, size - 48.0)
    first = keypoints(HAND[ref], size, shift)
    return ref, size, shift, action, first, [(n, keypoints(P(p), size, shift)) for n, p in frames]


if __name__ == "__main__":
    out = Path(sys.argv[1])
    for name in BATCHES:
        ref, size, shift, action, first, frames = batch(name)
        for n, kps in frames:
            xs = [k["x"] * size for k in kps]
            ys = [k["y"] * size for k in kps]
            if min(xs) < 1 or max(xs) > size - 1 or min(ys) < 1 or max(ys) > size - 3:
                print(f"  {name}/{n} near the edge: x {min(xs):.1f}-{max(xs):.1f} y {min(ys):.1f}-{max(ys):.1f}")
        json.dump({"ref": ref, "size": size, "shift": shift, "action": action, "first": first, "frames": frames}, open(out / f"{name}.json", "w"))
        print(name, ref, size, len(frames), "frames")

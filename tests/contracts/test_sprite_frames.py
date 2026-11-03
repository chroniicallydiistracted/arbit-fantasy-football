"""The sprite art must stay loadable by anything that plays it."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("frames", ROOT / "scripts/sprites/frames.py")
assert SPEC is not None and SPEC.loader is not None
frames = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(frames)

# Every motion a play can ask for. Removing a frame breaks these plays.
MOTIONS = {
    "stance": ["stand", "ready", "kneel"],
    "run": [
        "run1",
        "run_pass",
        "run_knee",
        "run_float",
        "run3",
        "run_far_pass",
        "run2",
        "run_far_float",
    ],
    "dropback": ["drop_a", "drop_b", "drop_c"],
    "throw": ["throw_cock", "throw_mid", "throw_rel", "throw_follow"],
    "catch": ["catch_reach", "catch_high", "catch_secure", "catch_low", "dive_catch"],
    "tackle": ["lunge", "tackle_dive", "wrap", "drive"],
    "tackled": ["hit", "stumble", "fall_30", "fall_60", "ground"],
    "knocked back": ["hit_back", "fall_back_30", "fall_back_60", "ground_back"],
    "get up": ["rise_1", "rise_2", "rise_3"],
    "fumble": ["recover"],
    "kick": ["kick_plant", "kick_swing", "kick_strike", "kick_follow"],
    "punt": ["punt_hold", "punt_drop", "punt_strike", "punt_follow"],
    "specialists": ["hold_ready", "hold_catch", "hold_place", "snap_ready", "snap_release"],
    "quarterback extras": ["slide", "spike"],
    "celebrate": ["arm", "arms_up", "arms_jump", "point"],
}


def test_frames_use_only_palette_colors_and_have_no_stray_pixels():
    assert frames.problems(frames.all_frames(), frames.palette()) == []


def test_every_motion_has_its_frames():
    available = frames.all_frames()
    missing = [name for names in MOTIONS.values() for name in names if name not in available]
    assert missing == []


def test_palette_has_every_color_set_for_every_class():
    assert {len(sets) for sets in frames.palette().values()} == {64}


def test_frames_drawn_without_the_ball_say_where_the_hand_is():
    anchors = frames.anchors()
    groups = frames.load_groups()
    drawn = [name for group, found in groups.items() if group != "base" for name in found]
    missing = [name for name in drawn if "near_hand" not in anchors.get(name, {})]
    assert missing == []

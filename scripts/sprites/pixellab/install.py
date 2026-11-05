"""Copy staged frames into assets/sprites/frames, grouped by motion, with their anchors.
The six originals in base.txt are never touched. Usage: install.py STAGING_DIR"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from teams import load  # noqa: E402

ASSETS = Path("/home/andre/arbit-fantasy-football/assets/sprites")
GROUPS = {
    "run": ["run_pass", "run_knee", "run_float", "run_far_pass", "run_far_float"],
    "qb": ["ready", "drop_a", "drop_b", "drop_c", "throw_cock", "throw_mid", "throw_rel", "throw_follow", "spike", "slide"],
    "catch": ["catch_reach", "catch_high", "catch_secure", "catch_low", "dive_catch"],
    "tackle": ["lunge", "tackle_dive", "wrap", "drive", "hit", "stumble", "fall_30", "fall_60", "ground"],
    "recover": ["hit_back", "fall_back_30", "fall_back_60", "ground_back", "rise_1", "rise_2", "rise_3", "recover"],
    "kick": ["kick_plant", "kick_swing", "kick_strike", "kick_follow", "punt_hold", "punt_drop", "punt_strike", "punt_follow",
             "snap_ready", "snap_release", "hold_ready", "hold_catch", "hold_place"],
    "celebrate": ["arms_up", "arms_jump", "point"],
    # OWN-037: waiting and idle poses that aren't the quarterback's, the backpedal and the handoff.
    "situational": ["stance_1", "stance_2", "idle_1", "idle_2", "bp_1", "bp_2", "bp_3", "bp_4",
                    "handoff_give", "handoff_follow", "take"],
}

if __name__ == "__main__":
    staging = Path(sys.argv[1])
    frames = {}
    for f in sorted(staging.glob("*.txt")):
        if f.name != "ball.txt":
            frames.update(load(f))
    placed = [n for names in GROUPS.values() for n in names]
    missing, extra = sorted(set(placed) - set(frames)), sorted(set(frames) - set(placed))
    if missing or extra:
        raise SystemExit(f"missing {missing} extra {extra}")
    for group, names in GROUPS.items():
        text = "".join(f"== {n}\n" + "\n".join(frames[n]) + "\n" for n in names)
        (ASSETS / "frames" / f"{group}.txt").write_text(text)
    (ASSETS / "ball.txt").write_text((staging / "ball.txt").read_text())
    anchors = json.loads((staging / "anchors.json").read_text())
    keep = placed + ["stand", "run1", "run2", "run3", "kneel"]
    (ASSETS / "anchors.json").write_text(json.dumps({n: anchors[n] for n in keep}, indent=1, sort_keys=True) + "\n")
    print("installed", len(placed), "frames in", len(GROUPS), "files")

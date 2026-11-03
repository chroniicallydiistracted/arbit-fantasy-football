"""Re-create real plays from CHI at SEA (2026-11-02, event 401873036) with the sprite frames.

Facts come from the stored play-by-play: spots, yardage, players and their roles. Only players the
play names are drawn (OWN-021); motion between ESPN's spots is generated, so every frame carries the
re-creation label (ENG-023). The field is the owner's Gridiron art, so output stays in ignored data/.
Offense always attacks to the right; the feed does not say which end each team defended.

Usage: uv run --no-project --with pillow --with numpy python scripts/sprites/real_plays.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/sprites"))
import preview as P  # noqa: E402

FIELD_PATH = ROOT / "data/Gridiron_2026_Fields/Seattle_Seahawks/SEA_2023-2026_1.png"
P.OUT = ROOT / "data/sprites/review/real-plays"
P.FIELD = Image.open(FIELD_PATH).convert("RGB").resize((1024 * P.SCALE, 486 * P.SCALE), Image.LANCZOS)
MID = 26.67


def away_whites(home: int) -> tuple[int, int]:
    """The sheet only has home colors. Approximate a road uniform: white jersey and socks, the home
    jersey's navy and the trim's orange moved onto the trim. Stand-in until real uniform recoloring."""
    white = {"e": (255, 255, 255), "c": (232, 232, 236), "f": (196, 196, 204), "h": (150, 150, 160)}
    added = []
    for skin in (0, 32):
        for cls, sets in P.PALETTE.items():
            color = list(sets[home + skin])
            if cls in white:
                color = list(white[cls])
            elif cls in "ki":
                color = list(P.PALETTE["e" if cls == "k" else "c"][home + skin])  # home jersey navy
            sets.append(color)
        added.append(len(P.PALETTE["#"]) - 1)
    return added[0], added[1]


SEA = (28, 28 + 32)  # rows of the owner's sheet: darker and lighter skin
CHI = away_whites(5)


def player(name: str, team: tuple[int, int], espn_id: int, x: float, z: float, facing_left: bool = False) -> P.Actor:
    # Skin tone is a placeholder: alternated by ESPN id, not taken from the real player.
    actor = P.Actor(team[espn_id % 2], x, z, facing_left)
    actor.label = name
    return actor


def tackled(actor: P.Actor, spot: float, z: float, way: int = 1) -> P.Actor:
    """Carrier going `way` (+1 right, -1 left) is brought down forward at `spot`."""
    actor.move("hit", 0.1, spot - way * 0.4, z).move("stumble", 0.1, spot - way * 0.25, z)
    actor.move("fall_30", 0.1, spot - way * 0.1, z).move("fall_60", 0.15, spot, z)
    return actor.hold("ground", 6)


def tackler(actor: P.Actor, wait: float, contact: float, spot: float, z: float, side: int) -> P.Actor:
    """Defender meets the carrier at `contact`, arriving from the right (side=1) or left (side=-1)."""
    actor.hold("ready", wait).move("RUN", contact - 0.45 - wait, spot + 2.4 * side, z - 0.3)
    actor.move("lunge", 0.2, spot + 1.1 * side, z - 0.2).move("wrap", 0.15, spot + 0.5 * side, z - 0.2)
    actor.move("drive", 0.1, spot + 0.3 * side, z - 0.2).move("fall_60", 0.2, spot + 0.2 * side, z - 0.2)
    actor.hold("ground", 1.4).hold("rise_1", 0.3).hold("rise_2", 0.3).hold("rise_3", 0.3)
    return actor.hold("ready", 6)


def throw(passer: P.Actor, ready: float, drop_to: float, z: float) -> float:
    """Shotgun drop and throw. Returns the release time."""
    passer.hold("ready", ready).move("DROP", 0.6, drop_to, z).hold("drop_b", 0.15)
    passer.hold("throw_cock", 0.3).hold("throw_mid", 0.1)
    release = ready + 0.6 + 0.15 + 0.3 + 0.1
    passer.hold("throw_rel", 0.15).hold("throw_follow", 0.45).hold("stand", 8)
    return release


def catch(receiver: P.Actor, catch_time: float, x: float, z: float, run_from: float) -> None:
    receiver.move("RUN", catch_time - 0.27 - run_from, x - 1.3, z)
    receiver.move("catch_reach_e", 0.15, x, z).move("catch_reach", 0.12, x + 1, z).carry(catch_time)


def lines(los: float, to_gain: float | None = None) -> list[tuple[float, tuple[int, int, int, int]]]:
    out = [(los, P.LOS_COLOR)]
    if to_gain is not None:
        out.append((to_gain, P.FIRST_DOWN_COLOR))
    return out


def touchdown_pass() -> None:  # 193900
    los, cx, cz, catch_time = 57, 92, 31, 4.2
    passer = player("S.Darnold", SEA, 3912547, los - 5, MID)
    release = throw(passer, 0.7, los - 7, MID)
    passer.carry(0, release)
    receiver = player("J.Smith-Njigba", SEA, 4430878, los, 34).hold("ready", 0.7)
    catch(receiver, catch_time, cx, cz, 0.7)
    receiver.move("catch_secure", 0.2, cx + 2.8, cz - 0.5).move("RUN", 0.85, 104, 26)
    receiver.carries[-1] = (catch_time, catch_time + 1.05)
    for pose, seconds in (("spike", 0.35), ("arms_up", 0.35), ("arms_jump", 0.3), ("arms_up", 0.3), ("arms_jump", 0.3), ("point", 3)):
        receiver.hold(pose, seconds)
    dx, dy = P.ball_offset("throw_mid")
    bx, by = P.ball_offset("catch_reach")
    path = P.flight(release, catch_time, (los - 7 + dx, dy, MID), (cx + bx, by, cz))

    def follow(t: float) -> float:
        return 58 if t < release else path(min(t, catch_time))[0] + 2 if t < catch_time else min(101, receiver.where(t)[0])

    P.render("td-pass", 8.0, [passer, receiver], lambda t: path(t) if release <= t < catch_time else None, follow,
             lines(los, 67), "Q2 0:30 · 3rd & 10 · S.Darnold deep left to J.Smith-Njigba, 43-yard TOUCHDOWN")


def pass_and_tackle() -> None:  # 124000
    los, cx, cz, catch_time, spot, contact = 28, 47, 29, 3.4, 51, 4.15
    passer = player("C.Williams", CHI, 4431611, los - 5, MID)
    release = throw(passer, 0.7, los - 7, MID)
    passer.carry(0, release)
    receiver = player("L.Burden", CHI, 4685278, los, 36).hold("ready", 0.7)
    catch(receiver, catch_time, cx, cz, 0.7)
    receiver.move("catch_secure", 0.2, cx + 2, cz - 0.4).move("RUN", contact - 0.13 - catch_time - 0.2, spot - 0.7, 28.4)
    tackled(receiver, spot, 28.4)
    defender = tackler(player("J.Love", SEA, 4046675, 62, 22, True), 1.4, contact, spot, 28.4, 1)
    dx, dy = P.ball_offset("throw_mid")
    bx, by = P.ball_offset("catch_reach")
    path = P.flight(release, catch_time, (los - 7 + dx, dy, MID), (cx + bx, by, cz))

    def follow(t: float) -> float:
        return 30 if t < release else path(min(t, catch_time))[0] + 2 if t < catch_time else receiver.where(t)[0] + 1

    P.render("pass-tackle", 6.8, [passer, receiver, defender], lambda t: path(t) if release <= t < catch_time else None,
             follow, lines(los, 38), "Q2 9:34 · 1st & 10 · C.Williams deep middle to L.Burden for 23 yards (J.Love)")


def run_two_tacklers() -> None:  # 41000
    los, spot, z, contact = 60, 69, 23, 2.4
    runner = player("R.Johnson", CHI, 4426386, los - 6, MID).carry(0).hold("ready", 0.7)
    runner.move("RUN", contact - 0.13 - 0.7, spot - 0.7, z)
    tackled(runner, spot, z)
    first = tackler(player("T.Okada", SEA, 4247808, 67, 31, True), 0.8, contact, spot, z, 1)
    second = tackler(player("E.Jones", SEA, 4362851, 76, 14, True), 0.7, contact + 0.08, spot + 0.3, z - 1.6, 1)
    P.render("run", 5.6, [runner, first, second], lambda _t: None, lambda t: runner.where(t)[0] + 2,
             lines(los, 70), "Q1 8:08 · 2nd & 10 · R.Johnson right tackle for 9 yards (T.Okada; E.Jones)")


def sack() -> None:  # 231600
    los, spot, contact = 27, 19, 2.5
    passer = player("S.Darnold", SEA, 3912547, los - 5, MID).carry(0).hold("ready", 0.7)
    passer.move("DROP", 0.6, los - 7, MID).hold("drop_b", contact - 0.13 - 1.3)
    passer.move("hit_back", 0.1, spot + 0.6, MID).move("fall_back_30", 0.12, spot + 0.3, MID)
    passer.move("fall_back_60", 0.15, spot, MID).hold("ground_back", 6)
    rusher = tackler(player("M.Sweat", CHI, 3134690, los + 1, 19, True), 0.55, contact, spot + 0.4, MID + 0.3, 1)
    P.render("sack", 5.6, [passer, rusher], lambda _t: None, lambda _t: 22, lines(los, 37),
             "Q3 13:27 · 2nd & 10 · S.Darnold sacked at SEA 19 for -8 yards (M.Sweat)")


def goalposts(draw: ImageDraw.ImageDraw, camera: P.Camera) -> None:
    yellow, x = (250, 210, 40, 255), 110.0
    base = camera.project(x, 0, MID)
    bar = camera.project(x, 3.33, MID)
    draw.line([base[:2], bar[:2]], fill=yellow, width=max(2, round(base[2] * 0.18)))
    left, right = camera.project(x, 3.33, MID - 3.08), camera.project(x, 3.33, MID + 3.08)
    draw.line([left[:2], right[:2]], fill=yellow, width=max(2, round(bar[2] * 0.14)))
    for z in (MID - 3.08, MID + 3.08):
        low, high = camera.project(x, 3.33, z), camera.project(x, 11.7, z)
        draw.line([low[:2], high[:2]], fill=yellow, width=max(2, round(low[2] * 0.12)))


def field_goal() -> None:  # 140700
    los, hold_x, z = 75, 68, MID
    snapper = player("S.Daly", CHI, 2980138, los, z).hold("snap_ready", 0.8).hold("snap_release", 0.5).hold("ready", 6)
    holder = player("T.Taylor", CHI, 4686889, hold_x, z - 0.6)
    holder.hold("hold_ready", 1.0).hold("hold_catch", 0.15).hold("hold_place", 0.45).hold("hold_ready", 6)
    kicker = player("C.Santos", CHI, 17427, hold_x - 3.6, z + 1.4).hold("ready", 0.75)
    kicker.move("RUN", 0.55, hold_x - 1.8, z + 0.8).move("kick_plant", 0.12, hold_x - 1.4, z + 0.6)
    kicker.move("kick_swing", 0.08, hold_x - 1.1, z + 0.4).move("kick_strike", 0.12, hold_x - 0.9, z + 0.3)
    kicker.move("kick_follow", 0.5, hold_x - 0.6, z + 0.3).hold("stand", 1.3)
    for pose in ("arms_up", "arms_jump", "arms_up", "arms_jump", "point"):
        kicker.hold(pose, 0.3)
    kicker.hold("arms_up", 3)
    sx, sy = P.ball_offset("snap_ready")
    hx, hy = P.ball_offset("hold_place")
    snap = P.flight(0.8, 1.15, (los + sx, sy, z), (hold_x + hx, hy, z), g=2.0)
    kick = P.flight(1.62, 3.9, (hold_x + hx, hy, z), (110, 6.5, MID))

    def ball(t: float) -> P.Point | None:
        if 0.8 <= t < 1.15:
            return snap(t)
        if 1.15 <= t < 1.62:
            return (hold_x + hx, 0.25, z)
        if 1.62 <= t < 3.9:
            return kick(t)
        return (min(113, 110 + (t - 3.9) * 8), max(0.2, 6.5 - (t - 3.9) * 5), MID) if t >= 3.9 else None

    def follow(t: float) -> float:
        return 74 if t < 1.62 else 74 + (min(t, 3.9) - 1.62) * 12.5

    P.render("field-goal", 6.0, [snapper, holder, kicker], ball, follow, lines(los), "Q2 6:07 · 4th & 4 · C.Santos 44-yard field goal is GOOD",
             tilted=True, overlay=goalposts)


def punt_return() -> None:  # 226000
    los, punter_x, z, landing, spot = 25, 10.5, MID, 82, 73
    snap_end, kick_time, hang = 1.15, 1.66, 4.4
    arrival = kick_time + hang
    contact = arrival + 0.32 + 1.1
    snapper = player("S.Daly", CHI, 2980138, los, z).hold("snap_ready", 0.7).hold("snap_release", 0.45).hold("ready", 12)
    punter = player("T.Taylor", CHI, 4686889, punter_x, z).hold("ready", snap_end).carry(snap_end, kick_time)
    punter.hold("punt_hold", 0.3).move("punt_drop", 0.15, punter_x + 0.6, z).move("punt_strike", 0.12, punter_x + 1.2, z)
    punter.move("punt_follow", 0.6, punter_x + 1.6, z).hold("stand", 12)
    returner = player("T.Horton", SEA, 4597703, landing, 30, True).hold("ready", arrival - 0.3).carry(arrival)
    returner.hold("catch_high_e", 0.3).hold("catch_high", 0.12).move("catch_secure", 0.2, landing - 0.3, 30)
    returner.move("RUN", contact - 0.13 - arrival - 0.32, spot + 0.7, 30)
    tackled(returner, spot, 30, -1)
    cover = tackler(player("J.Blackwell", CHI, 4240459, los, 20), 0.9, contact, spot, 30, -1)
    sx, sy = P.ball_offset("snap_ready")
    snap = P.flight(0.7, snap_end, (los + sx, sy, z), (punter_x + 0.3, 1.2, z), g=3.0)
    bx, by = P.ball_offset("catch_high")
    path = P.flight(kick_time, arrival, (punter_x + 1.6, 1.1, z), (landing - bx, by, 30))

    def ball(t: float) -> P.Point | None:
        if 0.7 <= t < snap_end:
            return snap(t)
        return path(t) if kick_time <= t < arrival else None

    def follow(t: float) -> float:
        if t < kick_time:
            return 20
        return min(80, path(min(t, arrival))[0] + 1) if t < arrival else returner.where(t)[0] - 1

    P.render("punt-return", contact + 2.4, [snapper, punter, returner, cover], ball, follow, lines(los),
             "Q3 13:41 · 4th & 2 · T.Taylor punts 57 yards, T.Horton returns 9 (J.Blackwell)", tilted=True)


def interception() -> None:  # 367900
    los, catch_x, cz, spot, z = 25, 22.6, 26.0, 6, 25.5
    passer = player("S.Darnold", SEA, 3912547, los - 5, MID).hold("ready", 0.7).hold("drop_b", 0.3)
    passer.hold("throw_cock", 0.2).hold("throw_mid", 0.1)
    release = 1.3
    passer.carry(0, release).hold("throw_rel", 0.15).hold("throw_follow", 0.45).hold("stand", 8)
    catch_time = 1.8
    contact = catch_time + 0.2 + 2.05
    picker = player("J.Lynch", CHI, 4259181, los + 2, 27, True).hold("ready", 0.8)
    picker.move("RUN", catch_time - 0.37 - 0.8, catch_x + 0.6, cz).hold("catch_high_e", 0.25).hold("catch_high", 0.12)
    picker.carry(catch_time).move("catch_secure", 0.2, catch_x - 0.4, cz)
    picker.move("RUN", contact - 0.13 - catch_time - 0.2, spot + 0.7, z)
    tackled(picker, spot, z, -1)
    chaser = tackler(player("A.Lucas", SEA, 4245171, 25, 18, True), 1.6, contact, spot, z, 1)  # chases from behind
    dx, dy = P.ball_offset("throw_mid")
    bx, by = P.ball_offset("catch_high")
    path = P.flight(release, catch_time, (los - 5 + dx, dy, MID), (catch_x - bx, by, cz), g=6.0)

    def follow(t: float) -> float:
        return 22 if t < catch_time else max(10, picker.where(t)[0] - 1)

    P.render("interception", contact + 2.4, [passer, picker, chaser], lambda t: path(t) if release <= t < catch_time else None,
             follow, lines(los, 32), "Q4 6:01 · 3rd & 7 · S.Darnold INTERCEPTED by J.Lynch, returned 16 yards (A.Lucas)")


if __name__ == "__main__":
    P.OUT.mkdir(parents=True, exist_ok=True)
    for play in (touchdown_pass, pass_and_tackle, run_two_tacklers, sack, field_goal, punt_return, interception):
        play()

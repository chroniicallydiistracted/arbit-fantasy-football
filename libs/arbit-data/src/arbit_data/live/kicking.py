"""Play scripts for kicks (automation slice 3): field goals, punts, kickoffs and the try after a
touchdown.

Built on the slice 2 choreographer, in the same frame and with the same natural motion. The kick
unit follows the measured game: the holder sets up 8 yards behind the line (a field goal's
distance is the yards to the goal line plus 18 on 50 of 57 captured kicks), a punter takes a
15-yard snap, and on a kickoff the coverage waits at the receiving team's 40 until the ball is
caught, as the 2025 kickoff rules require. A good place kick tumbles end over end between the
uprights and above the bar into the net behind them (ENG-029, ENG-030); a miss passes outside the
upright on its side, where for the kicking team the left is the near sideline; a kick that hits an
upright or the crossbar comes back off it. Punts spiral. Players the text names without an ESPN
ID, such as a long snapper, appear under that name.
"""

import math
import re

from arbit_data.live import choreography as C
from arbit_data.live.choreography import FIELD_WIDTH, BallEnd, PlayScript, _Play, settle
from arbit_data.live.play_facts import KickFacts, PassFacts, PlayerRole, PlayFacts, RunFacts

GRAVITY = 10.7  # yards a second squared, the renderer's
POST_Z, POST_HALF, CROSSBAR, END_LINE, NET = 80 / 3, 3.08, 3.33, 110.0, 113.0
HOLD = 8.0  # yards behind the line, measured
HOLD_AHEAD = 0.4  # the ball sits this far ahead of the holder
PUNT_DEPTH = 15.0
# Kickoff coverage lines up 25 yards past the tee: the receiving team's 40 on a kickoff from the
# 35, and as far past the 20 on a free kick after a safety. The 2026 rule (OWN-035).
KICKOFF_SETUP = 25.0
_UNIT = re.compile(r"\b(Center|Holder)-([A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]*)")


def build(play: _Play) -> _Play | None:
    kick = play.facts.kick
    if kick is None:
        return None
    if play.facts.template == "field_goal":
        return _place_kick(play, kick)
    if play.facts.template == "punt":
        return _punt(play, kick)
    if play.facts.template == "kickoff":
        return _kickoff(play, kick)
    return None


def _first(play: _Play, *roles: str) -> str | None:
    return next((espn_id for role in roles for espn_id in play.ids(role)), None)


def _long_snapper(play: _Play, unit: dict[str, str]) -> tuple[str | None, str | None]:
    """The snapper (OWN-037): ESPN's snapper role, else the team's long snapper from the depth
    chart when the text's "Center-" name is his or the text names none."""
    espn_id, text = _first(play, "snapper"), unit.get("Center")
    team = play.unit("long_snapper")
    if espn_id:
        return espn_id, text
    if team is not None and (text is None or text == team[1]):
        return team[0], text or play.names.get(team[0]) or team[1]
    return None, text


def _unit(play: _Play) -> dict[str, str]:
    return dict(_UNIT.findall(play.facts.text))


# Place kicks ---------------------------------------------------------------------------------


def _place_kick(
    play: _Play, kick: KickFacts, result: str | None = None, miss: str | None = None
) -> _Play | None:
    """Snap, hold and kick from 8 yards behind the line, and the ball's path for the result."""
    kicker_id = _first(play, "kicker", "patScorer")
    if kicker_id is None:
        return None
    result = result or kick.result
    miss = miss or kick.miss
    los, z = play.los, play.z
    hold_x = los - HOLD
    unit = _unit(play)
    snap_t = C.SNAP + 0.2
    caught = snap_t + 0.38
    placed = caught + 0.15 + 0.3
    kick_t = placed + 0.12
    spot = (hold_x + HOLD_AHEAD, 0.25, z)
    (snapper_id, snapper_name), holder_id = _long_snapper(play, unit), _first(play, "holder")
    if snapper_id or snapper_name:
        snapper = play.add(
            "snapper",
            snapper_id,
            "snapper",
            "offense",
            play.track(los, z, "defense"),
            "right",
            snapper_name,
        )
        # He snaps and stays down in his snapping stance (OWN-037).
        snapper.hold("snap_ready", snap_t).hold("snap_release", 0.5).hold("snap_ready", 0.3)
    holder_named = bool(holder_id or unit.get("Holder"))
    play.rest(0.0, snap_t, (los, 0.15, z))
    if holder_named:
        holder = play.add(
            "holder",
            holder_id,
            "holder",
            "offense",
            play.track(hold_x, z - 0.6, "defense"),
            "right",
            unit.get("Holder"),
        )
        holder.hold("hold_ready", caught - 0.05).hold("hold_catch", 0.15).hold(
            "hold_place", placed - holder.t
        )
        holder.hold("hold_ready", 0.3)
        play.fly(
            snap_t, caught, BallEnd(point=(los, 0.3, z)), BallEnd(actor="holder", hold="hands")
        )
        play.hold_ball("holder", caught, placed)
    else:
        play.fly(snap_t, placed, BallEnd(point=(los, 0.3, z)), BallEnd(point=spot))
    play.rest(placed, kick_t, spot)
    play.ball[-1] = play.ball[-1].model_copy(update={"spin": "upright"})
    kicker = play.add(
        "kicker",
        kicker_id,
        "kicker",
        "offense",
        play.track(hold_x - 3.8, z + 2.3, "quarterback"),
        "right",
    )
    # Two steps back and two over, soccer style; he goes at his own pace and plants as the ball
    # is set down, so the approach starts when it must rather than slowing to fit.
    approach = math.hypot(2.0, 1.5) / kicker.speed
    kicker.hold(C.STANCE, kick_t - 0.32 - approach)
    kicker.run(hold_x - 1.8, z + 0.8).move("kick_plant", 0.12, hold_x - 1.4, z + 0.6)
    kicker.move("kick_swing", 0.08, hold_x - 1.1, z + 0.4).move(
        "kick_strike", 0.12, hold_x - 0.9, z + 0.3
    )
    kicker.move("kick_follow", 0.5, hold_x - 0.6, z + 0.3)
    settle(kicker, kicker.t + 1.0)  # watches the kick with a step, not frozen
    if result == "good":
        for pose in ("arms_up", "arms_jump", "arms_up", "arms_jump", "point"):
            kicker.hold(pose, 0.3)
        kicker.hold("arms_up", 0.3)
    else:
        kicker.hold("stand", 0.3)
    if result == "blocked":
        return _blocked(play, kick_t, spot)
    _place_kick_flight(play, kick_t, spot, result, miss)
    return play


def _place_kick_flight(
    play: _Play,
    kick_t: float,
    spot: tuple[float, float, float],
    result: str | None,
    miss: str | None,
) -> None:
    rng = play.rng
    t_cross = 0.85 + 0.032 * (END_LINE - spot[0])
    if result == "good" or miss in ("wide_left", "wide_right"):
        if result == "good":
            cz = POST_Z + rng.uniform(-1.4, 1.4)
        elif miss == "wide_left":  # the kicker's left, toward the near sideline
            cz = POST_Z - POST_HALF - rng.uniform(0.6, 2.8)
        else:
            cz = POST_Z + POST_HALF + rng.uniform(0.6, 2.8)
        cross = (END_LINE, rng.uniform(5.0, 8.5), cz)
        play.fly(kick_t, kick_t + t_cross, BallEnd(point=spot), BallEnd(point=cross), "tumble")
        net, more = _onward(spot, cross, t_cross, NET)
        play.fly(
            kick_t + t_cross,
            kick_t + t_cross + more,
            BallEnd(point=cross),
            BallEnd(point=net),
            "tumble",
        )
        drop = math.sqrt(max(0.0, 2 * (net[1] - 0.15) / GRAVITY))
        floor = (NET, 0.15, net[2])
        landed = kick_t + t_cross + more + drop
        play.fly(
            kick_t + t_cross + more, landed, BallEnd(point=net), BallEnd(point=floor), "tumble"
        )
        play.rest(landed, 1e9, floor)
        return
    if miss in ("hit_left_upright", "hit_right_upright", "hit_crossbar"):
        if miss == "hit_crossbar":
            post = (END_LINE, CROSSBAR + 0.1, POST_Z + rng.uniform(-1.5, 1.5))
        else:
            side = -1 if miss == "hit_left_upright" else 1
            post = (END_LINE, rng.uniform(4.2, 8.0), POST_Z + side * POST_HALF)
        play.fly(kick_t, kick_t + t_cross, BallEnd(point=spot), BallEnd(point=post), "tumble")
        back = (END_LINE - rng.uniform(2.0, 6.0), 0.12, post[2] + rng.uniform(-2.0, 2.0))
        play.fly(
            kick_t + t_cross,
            kick_t + t_cross + 0.8,
            BallEnd(point=post),
            BallEnd(point=back),
            "tumble",
        )
        play.rest(kick_t + t_cross + 0.8, 1e9, back)
        return
    # Short, or no good without a reason given: it comes down in front of the posts.
    landing = (END_LINE - rng.uniform(1.0, 7.0), 0.12, POST_Z + rng.uniform(-2.0, 2.0))
    flight = 0.85 + 0.032 * (landing[0] - spot[0])
    play.fly(kick_t, kick_t + flight, BallEnd(point=spot), BallEnd(point=landing), "tumble")
    play.rest(kick_t + flight, 1e9, landing)


def _onward(
    origin: tuple[float, float, float],
    through: tuple[float, float, float],
    seconds: float,
    to_x: float,
) -> tuple[tuple[float, float, float], float]:
    """Where a ball that left `origin` and passed `through` after `seconds` is when it reaches
    x = `to_x`, on the same arc, and how much later. It can't go below the turf."""
    vx = (through[0] - origin[0]) / seconds
    vz = (through[2] - origin[2]) / seconds
    vy = (through[1] - origin[1] + 0.5 * GRAVITY * seconds * seconds) / seconds - GRAVITY * seconds
    more = (to_x - through[0]) / vx
    y = through[1] + vy * more - 0.5 * GRAVITY * more * more
    return (to_x, max(0.15, y), through[2] + vz * more), more


def _blocked(play: _Play, kick_t: float, spot: tuple[float, float, float]) -> _Play:
    """The ball comes off the blocker's hands a yard or two in front of the hold and drops."""
    rng = play.rng
    deflect = (spot[0] + 1.3, 1.3, spot[2])
    play.fly(kick_t, kick_t + 0.1, BallEnd(point=spot), BallEnd(point=deflect), "tumble")
    landing = (spot[0] + rng.uniform(-5.0, 4.0), 0.12, spot[2] + rng.uniform(-5.0, 5.0))
    play.fly(kick_t + 0.1, kick_t + 1.0, BallEnd(point=deflect), BallEnd(point=landing), "tumble")
    play.rest(kick_t + 1.0, 1e9, landing)
    blocker = _first(play, "other")
    named = re.search(rf"BLOCKED \(({C._NAME})\)", play.facts.text)
    if blocker and named:
        play.labels["blocker"] = play.names.get(blocker) or named.group(1)
    if blocker:
        track = play.add(
            "blocker",
            blocker,
            "blocker",
            "defense",
            play.track(play.los + 1.0, spot[2] + 2.0, "defense"),
            "left",
        )
        C._close(play, track, deflect[0] + 0.4, spot[2] + 0.3, kick_t - 0.1, C.SNAP + 0.2)
        track.move("lunge", 0.2, deflect[0] + 0.1, spot[2] + 0.2).hold("stand", 0.3)
    return play


# Punts ----------------------------------------------------------------------------------------


def _punt(play: _Play, kick: KickFacts) -> _Play | None:
    punter_id = _first(play, "punter")
    blocked = kick.result == "blocked"
    named = re.search(rf"({C._NAME}) punt is BLOCKED", play.facts.text) if blocked else None
    if (punter_id is None and not named) or kick.result is None:
        return None
    rng = play.rng
    los, z = play.los, play.z
    unit = _unit(play)
    snap_t = C.SNAP + 0.2
    caught = snap_t + 0.75
    snapper_id, snapper_name = _long_snapper(play, unit)
    if snapper_id or snapper_name:
        snapper = play.add(
            "snapper",
            snapper_id,
            "snapper",
            "offense",
            play.track(los, z, "defense"),
            "right",
            snapper_name,
        )
        snapper.hold("snap_ready", snap_t).hold("snap_release", 0.45).hold("snap_ready", 0.3)
    punter = play.add(
        "punter",
        punter_id,
        "punter",
        "offense",
        play.track(los - PUNT_DEPTH, z, "defense"),
        "right",
        named.group(1) if named and punter_id is None else None,
    )
    play.rest(0.0, snap_t, (los, 0.15, z))
    play.fly(snap_t, caught, BallEnd(point=(los, 0.3, z)), BallEnd(actor="punter", hold="hand"))
    play.hold_ball("punter", caught)
    settle(punter, caught)
    punter.hold("punt_hold", 0.3).move("punt_drop", 0.15, punter.x + 0.6, z)
    if blocked:
        play.note = (
            "The punt setup is shown. The block and recovery are described in the play text."
        )
        return play
    punter.move("punt_strike", 0.12, punter.x + 0.6, z)
    kick_t = punter.t
    punter.move("punt_follow", 0.6, punter.x + 0.4, z).hold("stand", 0.3)
    play.release("punter", kick_t)
    distance = float(kick.distance or ((kick.landing or los + 40) - punter.x))
    landing_x = float(kick.landing if kick.landing is not None else punter.x + distance)
    if kick.result == "touchback" and landing_x >= 100:
        landing_x = 100 + rng.uniform(2.0, 8.0)
    land_z = min(49.0, max(4.0, z + rng.uniform(-9.0, 9.0)))
    if kick.result == "out_of_bounds":
        land_z = -0.8 if land_z < FIELD_WIDTH / 2 else FIELD_WIDTH + 0.8
    hang = min(5.2, max(3.2, 2.6 + 0.04 * distance))
    origin = BallEnd(actor="punter", hold="hand")
    # The coverage lines up on the line and releases at the snap, as gunners do.
    return _receive(
        play, kick, kick_t, hang, landing_x, land_z, "spiral", origin, los, C.SNAP + 0.2
    )


# Kickoffs -------------------------------------------------------------------------------------


def _kickoff(play: _Play, kick: KickFacts) -> _Play | None:
    kicker_id = _first(play, "kicker")
    if kicker_id is None or kick.result in (None, "blocked"):
        return None
    rng = play.rng
    tee_x = play.los
    z = FIELD_WIDTH / 2 + rng.uniform(-1.0, 1.0)
    tee = (tee_x, 0.25, z)
    kicker = play.add(
        "kicker",
        kicker_id,
        "kicker",
        "offense",
        play.track(tee_x - 6.4, z - 1.6, "rusher"),
        "right",
    )
    kicker.hold(C.STANCE, C.SNAP)
    approach_to = (tee_x - 1.8, z - 0.8)
    kicker.run(*approach_to)
    kicker.move("kick_plant", 0.12, tee_x - 1.4, z - 0.6).move(
        "kick_swing", 0.08, tee_x - 1.1, z - 0.4
    )
    kicker.move("kick_strike", 0.12, tee_x - 0.9, z - 0.3)
    kick_t = kicker.t
    kicker.move("kick_follow", 0.5, tee_x - 0.6, z - 0.3).hold("stand", 0.3)
    play.rest(0.0, kick_t, tee)
    play.ball[-1] = play.ball[-1].model_copy(update={"spin": "upright"})
    distance = float(kick.distance or ((kick.landing or tee_x + 60) - tee_x))
    landing_x = float(kick.landing if kick.landing is not None else tee_x + distance)
    if kick.result == "touchback" and landing_x >= 100:
        landing_x = 100 + rng.uniform(1.0, 9.0)
    land_z = min(46.0, max(7.0, z + rng.uniform(-12.0, 12.0)))
    if kick.result == "out_of_bounds":
        land_z = -0.8 if land_z < FIELD_WIDTH / 2 else FIELD_WIDTH + 0.8
    hang = 1.1 if kick.onside else min(4.4, max(3.0, 3.3 + 0.012 * distance))
    # The coverage lines up at the receiving 40 and can't move until the ball is caught.
    return _receive(
        play,
        kick,
        kick_t,
        hang,
        landing_x,
        land_z,
        "tumble",
        BallEnd(point=tee),
        tee_x + KICKOFF_SETUP,
        kick_t + hang,
    )


# Catching, returning and what else a kick can do ---------------------------------------------


def _receive(
    play: _Play,
    kick: KickFacts,
    kick_t: float,
    hang: float,
    landing_x: float,
    land_z: float,
    spin: str,
    origin: BallEnd,
    start_line: float,
    released: float,
) -> _Play:
    rng = play.rng
    land_t = kick_t + hang
    returner_id = _first(play, "returner")
    landing = (landing_x, 0.12, land_z)
    caught_by = kick.result in ("returned", "fair_catch", "muffed") and returner_id
    if not caught_by:
        play.fly(kick_t, land_t, origin, BallEnd(point=landing), spin)
        roll = (
            (landing_x + rng.uniform(0.5, 2.5), 0.12, land_z)
            if kick.result in ("downed", "touchback")
            else landing
        )
        if roll != landing:
            play.fly(land_t, land_t + 0.6, BallEnd(point=landing), BallEnd(point=roll), "flat")
            land_t += 0.6
        play.rest(land_t, 1e9, roll)
        if returner_id:  # he let it go: he stands where it came down
            watcher = play.add(
                "returner",
                returner_id,
                "returner",
                "defense",
                play.track(min(landing_x, 99.0) - 4.0, land_z + 3.0, "receiver"),
                "left",
            )
            settle(watcher, land_t, facing="left")
        return play
    returner = play.add(
        "returner",
        returner_id,
        "returner",
        "defense",
        play.track(landing_x + 1.0, land_z, "receiver"),
        "left",
    )
    if kick.result == "fair_catch":
        settle(returner, land_t - 0.82, facing="left")
        returner.hold("arms_up", 0.4, "left")
    else:
        settle(returner, land_t - 0.42, facing="left")
    returner.hold("catch_high_e", 0.3, "left").hold("catch_high", 0.12, "left")
    play.fly(kick_t, land_t, origin, BallEnd(actor="returner", hold="hands"), spin)
    if kick.result == "muffed":
        loose = (landing_x - rng.uniform(1.0, 3.0), 0.12, land_z + rng.uniform(-1.5, 1.5))
        play.fly(
            land_t,
            land_t + 0.5,
            BallEnd(actor="returner", hold="hands"),
            BallEnd(point=loose),
            "tumble",
        )
        play.rest(land_t + 0.5, 1e9, loose)
        returner.hold("stand", 0.3)
        return play
    play.hold_ball("returner", land_t)
    if kick.result == "fair_catch":
        returner.hold("stand", 0.3)
        return play
    returner.move("catch_secure", 0.2, landing_x - 0.4, land_z, "left")
    C._carry(play, returner, "returner", land_z, way=-1, start_line=start_line, released=released)
    return play


# The try after a touchdown -----------------------------------------------------------------------


# The try's sentence: names hold periods ("Center-C.Stoll"), so it ends at a period before a space.
_TRY = re.compile(
    r"[A-Z][a-z]{0,3}\.\S+ extra point is .*?(?:\.(?=\s|$)|$)"
    r"|TWO-POINT CONVERSION ATTEMPT\..*?ATTEMPT (?:SUCCEEDS|FAILS)"
)
_TWO_PASS = re.compile(r"TWO-POINT CONVERSION ATTEMPT\. .*?pass to (\S+) is (complete|incomplete)")
_TWO_RUN = re.compile(
    r"TWO-POINT CONVERSION ATTEMPT\. \S+ rushes (?:(left|right) (end|tackle|guard)|(up the middle))"
)


def choreograph_try(
    facts: PlayFacts,
    seed: str,
    names: dict[str, str] | None = None,
    positions: dict[str, tuple[str, ...]] | None = None,
    units: C.Units | None = None,
    real_seconds: float | None = None,
) -> PlayScript | None:
    """The extra point or two-point try that follows a touchdown, as its own script, from the 15
    or the 2 in the scoring team's frame, built to the try's own real time (OWN-052)."""
    token = C.REAL_SECONDS.set(real_seconds)
    try:
        return _choreograph_try(facts, seed, names, positions, units)
    finally:
        C.REAL_SECONDS.reset(token)


def _choreograph_try(
    facts: PlayFacts,
    seed: str,
    names: dict[str, str] | None,
    positions: dict[str, tuple[str, ...]] | None,
    units: C.Units | None,
) -> PlayScript | None:
    after = facts.point_after
    if after is None or not facts.touchdown or facts.offense is None:
        return None
    scorer = facts.defense if facts.turnover else facts.offense
    other = facts.offense if facts.turnover else facts.defense
    pat_roles = {"patScorer", "patPasser", "patRusher", "kicker"}
    players = tuple(p for p in facts.players if p.role in pat_roles)
    text = facts.text
    sentence = _TRY.search(text)
    said = sentence.group(0).rstrip(".") if sentence else ""
    kind = "Extra point" if after.kind == "extra_point" else "Two-point try"
    clock = f"Q{facts.period} {facts.clock}" if facts.period and facts.clock else ""
    words = re.sub(r"^TWO-POINT CONVERSION ATTEMPT\.\s*", "", said)
    caption = C.fit(clock, kind, re.sub(r", (?:Center|Holder)-[^,]*", "", words))
    base = facts.model_copy(
        update={
            "provider_id": facts.provider_id + ":try",
            "offense": scorer,
            "defense": other,
            "down": None,
            "distance": None,
            "line_to_gain": None,
            "players": players,
            "penalties": (),
            "fumble": None,
            "turnover": False,
            "out_of_bounds": False,
            "review": None,
            "point_after": None,
            "text": words,  # the try's own words, so its kicker or passer is named from them
        }
    )
    if after.kind == "extra_point":
        try_facts = base.model_copy(
            update={
                "shape": "field_goal",
                "template": "field_goal",
                "start": 85,
                "end": 85,
                "action_end": 85,
                "touchdown": False,
            }
        )
        play = _Play(try_facts, seed + ":try", names or {}, positions, units)
        built = _place_kick(
            play,
            KickFacts(distance=33, result="good" if after.good else "no_good"),
            "good" if after.good else "no_good",
            after.miss if after.miss != "blocked" else None,
        )
        return C._finish(built, "extra_point", caption) if built else None
    good = bool(after.good)
    thrown = _TWO_PASS.search(text)
    rushed = _TWO_RUN.search(text)
    roles = {p.role: p.espn_id for p in facts.players}
    if thrown and roles.get("patPasser"):
        receiver_id = roles.get("patScorer") if good else None
        if receiver_id is None:  # the try failed, so ESPN names no scorer: it falls in the end zone
            play = _Play(
                base.model_copy(update={"start": 98, "end": 98, "action_end": 98}),
                seed + ":try",
                names or {},
                positions,
                units,
            )
            return C._finish(
                _failed_try_pass(play, roles["patPasser"], thrown.group(1)), "two_point", caption
            )
        mapped = (
            PlayerRole(role="passer", espn_id=roles["patPasser"]),
            PlayerRole(role="receiver", espn_id=receiver_id),
        )
        try_facts = base.model_copy(
            update={
                "shape": "pass",
                "template": "pass",
                "start": 98,
                "end": 100,
                "action_end": 100,
                "touchdown": True,
                "players": mapped,
                "passing": PassFacts(result="complete", depth="short", air_yards=4),
            }
        )
        built = C._pass(_Play(try_facts, seed + ":try", names or {}, positions, units))
        return C._finish(built, "two_point", caption) if built else None
    if rushed and (roles.get("patRusher") or roles.get("patScorer")):
        rusher = roles.get("patRusher") or roles["patScorer"]
        side = rushed.group(1) or ("middle" if rushed.group(3) else None)
        gap = rushed.group(2) or ("middle" if rushed.group(3) else None)
        try_facts = base.model_copy(
            update={
                "shape": "run",
                "template": "run",
                "start": 98,
                "end": 100 if good else 99,
                "action_end": 100 if good else 99,
                "touchdown": good,
                "players": (PlayerRole(role="rusher", espn_id=rusher),),
                "run": RunFacts(style="run", side=side, gap=gap),  # type: ignore[arg-type]
            }
        )
        play = _Play(try_facts, seed + ":try", names or {}, positions, units)
        built = C._run(play)
        return C._finish(built, "two_point", caption) if built else None
    return None


def _failed_try_pass(play: _Play, passer_id: str, target: str) -> _Play:
    """A two-point pass that fails: thrown toward the named target in the end zone, it falls."""
    rng = play.rng
    qb = C._snap(
        play,
        "passer",
        passer_id,
        "passer",
        play.los - (5.0 if play.facts.shotgun else 1.0),
        play.facts.shotgun,
    )
    C._drop(play, qb, 1)
    release = qb.t + 0.55 + rng.uniform(0.3, 0.9)
    C._throw(qb, release)
    play.release("passer", release)
    landing = (100.0 + rng.uniform(1.0, 5.0), 0.12, play.lane(None))
    flight = C._flight(play, landing[0], landing[2], qb.x, 4.0)
    play.fly(
        release, release + flight, BallEnd(actor="passer", hold="hand"), BallEnd(point=landing)
    )
    play.rest(release + flight, 1e9, landing)
    del target  # named in the text only; no one is drawn for him
    return play

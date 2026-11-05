"""Play scripts for fumbles and penalties (automation slice 3).

A fumble is drawn as the play the text describes up to it (`PlayFacts.before`), then the ball
coming loose at the hit and rolling to where ESPN says it was recovered, and the recoverer falling
on it. A penalty that wipes out the play is the play as described, a flag thrown during it and a
caption that says "No Play"; a foul before the snap is the penalized player at the line, his
motion if the foul has one, and the flag. Penalties on a play that counts, accepted or declined,
get a flag where the foul happened. Officials aren't drawn: a flag comes from the nearest one,
on the sideline for a foul near it, otherwise the umpire or back judge in the middle.
"""

import math
import re
from collections.abc import Mapping

from arbit_data.live import alignment as A
from arbit_data.live import choreography as C
from arbit_data.live.choreography import FIELD_WIDTH, BallEnd, PlayScript, _Play, _Track, settle
from arbit_data.live.play_facts import PenaltyFacts, PlayerRole, PlayFacts

_PENALTY = re.compile(r"(?:PENALTY|Penalty) on ([A-Z]{2,3}(?:-[^,]+)?), ([^,.]+)")


def choreograph(
    facts: PlayFacts,
    seed: str,
    names: Mapping[str, str],
    positions: Mapping[str, tuple[str, ...]] | None = None,
    units: C.Units | None = None,
) -> PlayScript | None:
    if facts.shape == "fumble":
        return _fumble(facts, seed, names, positions or {}, units or {})
    if facts.shape == "penalty":
        return _penalty(facts, seed, names, positions or {}, units or {})
    return None


def flags(play: _Play, facts: PlayFacts | None = None) -> None:
    """A flag for each penalty on a play that counts, accepted or declined: the flag was thrown.
    `facts` is the whole play's when `play` draws only the part before a fumble."""
    for penalty in (facts or play.facts).penalties:
        if not penalty.no_play:
            _flag_for(play, penalty)


def caption(facts: PlayFacts) -> str | None:
    """The play's caption with the flag on it, for a play that counts; None when there's none."""
    flagged = [p for p in facts.penalties if not p.no_play]
    return C.fit(C._caption(facts), _penalty_words(facts, flagged[0])) if flagged else None


def _penalty_words(facts: PlayFacts, penalty: PenaltyFacts) -> str:
    found = _PENALTY.search(facts.text)
    words = f"PENALTY on {found.group(1)}, {found.group(2).strip()}" if found else "PENALTY"
    return f"{words}, {penalty.status}" if penalty.status in ("declined", "offsetting") else words


def _ends(play: _Play) -> float:
    return max(seg.end for *_, track, _ in play.actors for seg in track.segments)


def _kick(play: _Play) -> tuple[float, float, float] | None:
    """When and where the kick comes down, or is caught: the end of the longest flight."""
    flights = [seg for seg in play.ball if seg.state == "flight" and seg.end < 1e8]
    if play.facts.template not in ("punt", "kickoff", "field_goal") or not flights:
        return None
    longest = max(flights, key=lambda seg: seg.end - seg.start)
    if longest.target and longest.target.point:
        return longest.end, longest.target.point[0], longest.target.point[2]
    track = play.find(longest.target.actor or "") if longest.target else None
    return (longest.end, track.x, track.z) if track else None


def _near(play: _Play, keys: tuple[str, ...], t: float) -> tuple[float, float] | None:
    """Where the first of these players who is drawn stands at time t."""
    for key in keys:
        track = next((track for k, *_, track, _ in play.actors if k == key), None)
        if track and track.segments:
            seg = next((s for s in track.segments if s.start <= t < s.end), track.segments[-1])
            share = (
                0.0
                if seg.end <= seg.start
                else min(1.0, max(0.0, (t - seg.start) / (seg.end - seg.start)))
            )
            return seg.x0 + (seg.x1 - seg.x0) * share, seg.z0 + (seg.z1 - seg.z0) * share
    return None


def _pass_release(play: _Play) -> float | None:
    thrown = [
        s for s in play.ball if s.state == "flight" and s.origin and s.origin.actor == "passer"
    ]
    return thrown[0].start if thrown else None


def _pass_arrival(play: _Play) -> float | None:
    thrown = [
        s for s in play.ball if s.state == "flight" and s.origin and s.origin.actor == "passer"
    ]
    return thrown[0].end if thrown else None


_CONTACTS = {
    "defensive pass interference": ("dpi",),
    "offensive pass interference": ("opi",),
    "defensive holding": ("holding",),
    "illegal contact": ("contact",),
}


def _flag_for(play: _Play, penalty: PenaltyFacts) -> None:
    """Throw the flag about where and when this kind of foul happens."""
    rng = play.rng
    kind = (penalty.type or "").lower()
    offense_foul = penalty.team == play.facts.offense
    kick = _kick(play)
    seen = next((at for name, at in play.contact.items() if name in _CONTACTS.get(kind, ())), None)
    if seen is not None:  # the official saw the contact drawn in the play: the flag comes then
        play.flag(seen[0] + rng.uniform(0.15, 0.4), seen[1], seen[2])
        return
    if kick and any(word in kind for word in ("out of bounds", "landing zone")):
        thrown, x, z = kick[0] + rng.uniform(0.1, 0.4), kick[1], kick[2]  # marks where it landed
    elif kick:  # a block or a hold in the coverage, while the ball is in the air
        thrown = kick[0] - rng.uniform(0.3, 1.2)
        x = play.los + (kick[1] - play.los) * rng.uniform(0.5, 0.85)
        z = play.z + rng.uniform(-12.0, 12.0)
    elif any(word in kind for word in ("interference", "illegal contact", "defensive holding")):
        # On the receiver: interference as the ball arrives, contact and holding early in the route.
        target = _pass_arrival(play)
        late = "interference" in kind and target is not None
        thrown = target + rng.uniform(0.0, 0.3) if late else C.SNAP + rng.uniform(1.0, 1.6)  # type: ignore[operator]
        x, z = _near(play, ("receiver", "defender"), thrown - 0.2) or (
            play.los + rng.uniform(5.0, 12.0),
            play.z + rng.uniform(-9.0, 9.0),
        )
    elif "roughing the passer" in kind:
        release = _pass_release(play)
        thrown = (release if release is not None else C.SNAP + 2.0) + rng.uniform(0.4, 0.7)
        x, z = _near(play, ("passer",), thrown - 0.3) or (play.los - 6.0, play.z)
    elif offense_foul and any(word in kind for word in ("holding", "block", "chop")):
        thrown = C.SNAP + rng.uniform(1.0, 1.6)
        x, z = play.los - rng.uniform(0.5, 3.0), play.z + rng.uniform(-4.0, 4.0)
    else:  # after the play: a personal foul, a late hit, anything else where the action ended
        thrown = max(C.SNAP + 0.8, _ends(play) - 1.2)
        held = [seg for seg in play.ball if seg.state == "held" and seg.actor]
        ended = _near(play, (held[-1].actor,), thrown) if held else None  # type: ignore[arg-type]
        x, z = ended or (play.end, play.z)
    x, z = x + rng.uniform(-1.5, 1.5), z + rng.uniform(-1.5, 1.5)
    play.flag(thrown, x, z)


# Penalties that wipe out the play -------------------------------------------------------------


def _penalty(
    facts: PlayFacts,
    seed: str,
    names: Mapping[str, str],
    positions: Mapping[str, tuple[str, ...]],
    units: C.Units,
) -> PlayScript | None:
    if facts.start is None or facts.offense is None:
        return None
    penalty = next(
        (p for p in facts.penalties if p.no_play), facts.penalties[0] if facts.penalties else None
    )
    if penalty is None:
        return None
    before = facts.before
    if before is not None and before.template in C.TEMPLATES and not before.missing:
        # The play happened as the text describes it, with a flag during it, and didn't count.
        play = _Play(before, seed, names, positions, units)
        play.fouls = (penalty,)  # the flag that wiped it out is drawn in the play (OWN-037)
        built = C._build(play)
        if built is not None:
            _penalized_in_coverage(built, penalty)
            _flag_for(built, penalty)
            words = _penalty_words(facts, penalty)
            return C._finish(built, "penalty", C.fit(C._caption(before), words, "No Play"))
    return _before_the_snap(facts, penalty, seed, names, positions, units)


def _penalized_in_coverage(play: _Play, penalty: PenaltyFacts) -> None:
    """A defender flagged for holding or illegal contact on a play with no receiver drawn, such as
    a sack: he drops into coverage from his spot, where the flag lands (OWN-037)."""
    kind = (penalty.type or "").lower()
    flagged = next(iter(play.ids("penalized")), None)
    if not flagged or kind not in ("defensive holding", "illegal contact"):
        return
    if any(espn_id == flagged for _, espn_id, *_ in play.actors) or play.contact:
        return
    track = play.add(
        "penalized",
        flagged,
        "penalized",
        "defense",
        play.track(play.los + 6.0, play.z + 8.0, "defense"),
        "left",
        play.names.get(flagged) or penalty.player,
    )
    C._place(play, track, play.los + 6.0, play.z + 8.0, C.SNAP + 2.0, C.SNAP)
    track.hold(C.STANCE, C.SNAP + 0.2)
    track.move("BACKPEDAL", 0.7, track.x + 3.0, track.z)
    grab = track.t + 0.2
    track.move("wrap", 0.3, track.x + 0.3, track.z + 0.3).hold(C.STANCE, 0.3)
    play.contact["holding" if "holding" in kind else "contact"] = (grab, track.x, track.z)


def _before_the_snap(
    facts: PlayFacts,
    penalty: PenaltyFacts,
    seed: str,
    names: Mapping[str, str],
    positions: Mapping[str, tuple[str, ...]],
    units: C.Units,
) -> PlayScript:
    """The penalized player at the line, his motion if the foul has one, and the flag."""
    play = _Play(facts, seed, names, positions, units)
    rng = play.rng
    los, z = play.los, play.z
    play.rest(0.0, 1e9, (los, 0.15, z))
    kind = (penalty.type or "").lower()
    offense_foul = penalty.team == facts.offense
    flagged = play.ids("penalized")
    spot = (los, z)
    if flagged:
        x0 = los - 1.4 if offense_foul else los + 1.4
        z0 = min(FIELD_WIDTH - 3.0, max(3.0, z + rng.choice((-1, 1)) * rng.uniform(1.2, 6.0)))
        code = play.position(flagged[0], "offense" if offense_foul else "defense")
        aligned = A.spot(code, play.context(), chance=0.5) if code else None
        if aligned is not None:  # where his position lines up (OWN-036)
            x0, z0 = C._snap_spot(play, "offense" if offense_foul else "defense", *aligned)
        side = "offense" if offense_foul else "defense"
        facing = "right" if offense_foul else "left"
        track = play.add(
            "penalized",
            flagged[0],
            "penalized",
            side,
            play.track(x0, z0, "defense"),
            facing,
            names.get(flagged[0]) or penalty.player,
        )
        track.hold(C.STANCE, C.SNAP - 0.1)
        if "false start" in kind:
            track.move("lunge", 0.22, x0 + 0.6, z0).hold("stand", 0.3)  # flinches before the snap
        elif any(word in kind for word in ("offside", "encroachment", "neutral zone")):
            track.run(los - 0.4, z0).hold("stand", 0.3)  # across the line, at his pace
        else:
            track.hold(C.STANCE, 0.3)
        spot = (track.x, track.z)
    # With no penalized player named, such as a delay of game, the ball, the lines and the flag
    # tell it.
    play.flag(C.SNAP + 0.15, spot[0] + rng.uniform(-0.8, 0.8), spot[1] + rng.uniform(-1.0, 1.0))
    return C._finish(play, "penalty")


# Fumbles ---------------------------------------------------------------------------------------


_RECOVERED = re.compile(
    rf"\b(?:RECOVERED|recovered) by [A-Z]{{2,3}}-({C._NAME}) at (?:[A-Z]{{2,3}} )?-?\d+"
)
_RETURN = re.compile(rf"\s*({C._NAME}) (to|pushed ob at|ran ob at) [^()]*?(?:\(([^)]*)\))?(?=\.|$)")


def _fumble(
    facts: PlayFacts,
    seed: str,
    names: Mapping[str, str],
    positions: Mapping[str, tuple[str, ...]],
    units: C.Units,
) -> PlayScript | None:
    """The play up to the hit, the ball coming loose to ESPN's recovery spot, the recovery, and a
    return when the text has one."""
    before, fumble = facts.before, facts.fumble
    if (
        before is None
        or fumble is None
        or fumble.spot is None
        or before.template not in C.TEMPLATES
    ):
        return None
    recoverer_id = next((p.espn_id for p in facts.players if p.role == "recoverer"), None)
    recovered_text = _RECOVERED.search(facts.text)
    returned = _RETURN.match(facts.text[recovered_text.end() + 1 :]) if recovered_text else None
    if returned and returned.group(1) != recovered_text.group(1):  # type: ignore[union-attr]
        returned = None
    tacklers = _before_tacklers(facts, before)
    kept = tuple(p for p in before.players if p.role not in _TACKLE_ROLES)
    play = _Play(
        before.model_copy(update={"players": kept + tacklers}), seed, names, positions, units
    )
    built = C._build(play)
    if built is None:
        return None
    held = [seg for seg in play.ball if seg.state == "held"]
    if not held or held[-1].actor is None:
        return None
    carrier_key = held[-1].actor
    carrier = play.find(carrier_key)
    hit = next((seg for seg in carrier.segments if seg.pose in ("hit", "hit_back")), None)
    if hit is None:
        return None
    rng = play.rng
    pop = hit.start + 0.08
    play.release(carrier_key, pop)
    loose = (
        float(fumble.spot),
        0.12,
        min(FIELD_WIDTH - 1.0, max(1.0, hit.z1 + rng.uniform(-1.5, 1.5))),
    )
    rolled = _bounce(play, carrier_key, pop, loose)
    caption = _fumble_caption(facts)
    if recoverer_id is None:
        play.rest(rolled, 1e9, loose)
        flags(play, facts)
        return C._finish(play, "fumble", caption)
    lost = bool(fumble.lost)
    way = -1 if lost else 1  # the recovering team runs toward the goal it attacks
    drawn = {espn_id: key for key, espn_id, *_ in play.actors}
    if recoverer_id in drawn:
        key = drawn[recoverer_id]
        track = play.find(key)
        _back_on_feet(track, key == carrier_key, pop)
    else:
        key = "recoverer"
        offset = rng.uniform(4.0, 7.0) * rng.choice((-1, 1))
        track = play.add(
            key,
            recoverer_id,
            "recoverer",
            "defense" if lost else "offense",
            play.track(loose[0] + offset, loose[2] + rng.uniform(-5.0, 5.0), "defense"),
            "left" if offset > 0 else "right",
        )
        C._close(
            play, track, loose[0] + 1.0 * (1 if offset > 0 else -1), loose[2], rolled - 0.1, pop
        )
    if recovered_text and key not in play.labels:
        play.labels[key] = names.get(recoverer_id) or recovered_text.group(1)
    if returned:
        _scoop_and_return(play, facts, track, key, loose, rolled, way, returned)
    else:
        _fall_on(play, track, key, loose, rolled)
    flags(play, facts)
    return C._finish(play, "fumble", caption)


_TACKLE_ROLES = frozenset({"tackler", "assistedBy", "forcedBy", "recoverer", "other", "fumbler"})


def _before_tacklers(facts: PlayFacts, before: PlayFacts) -> tuple[PlayerRole, ...]:
    """Who tackles the ball carrier before the fumble. ESPN lists the play's tacklers together,
    the return's among them, so this takes the player who forced it and, when the text names a
    shared tackle, the other assisting player."""
    named = len(C._text_names(before.text).get("tackler", []))
    forcer = next((p.espn_id for p in facts.players if p.role == "forcedBy"), None)
    ids = [p.espn_id for p in facts.players if p.role == "assistedBy"] + [
        p.espn_id for p in facts.players if p.role == "tackler"
    ]
    chosen = [forcer] if forcer else []
    for espn_id in dict.fromkeys(ids):
        if len(chosen) >= max(1, named) or (forcer and named < 2):
            break
        if espn_id not in chosen:
            chosen.append(espn_id)
    return tuple(
        PlayerRole(role="tackler" if index == 0 else "assistedBy", espn_id=espn_id)
        for index, espn_id in enumerate(chosen)
    )


def _bounce(play: _Play, carrier: str, pop: float, loose: tuple[float, float, float]) -> float:
    """The ball out of the carrier's arms and bouncing to where it was recovered, in hops that
    get shorter. Returns when it comes to rest."""
    hit = play.find(carrier)
    at = next((seg for seg in hit.segments if seg.start <= pop < seg.end), hit.segments[-1])
    distance = math.hypot(loose[0] - at.x1, loose[2] - at.z1)
    hops = max(1, min(5, math.ceil(distance / 2.5)))
    seconds = [0.42 * 0.82**index for index in range(hops)]
    scale = max(1.0, (0.35 + distance / 8.0) / sum(seconds))
    seconds = [s * scale if index else s for index, s in enumerate(seconds)]
    share = [s / sum(seconds) for s in seconds]
    t, origin, travelled = pop, BallEnd(actor=carrier, hold="chest"), 0.0
    for index, (length, part) in enumerate(zip(seconds, share, strict=True)):
        travelled += part
        point = (
            at.x1 + (loose[0] - at.x1) * travelled,
            0.12,
            at.z1 + (loose[2] - at.z1) * travelled,
        )
        if index == hops - 1:
            point = loose
        play.fly(t, t + length, origin, BallEnd(point=point), "tumble")
        t += length
        origin = BallEnd(point=point)
    return t


def _back_on_feet(track: _Track, fumbler: bool, pop: float) -> None:
    """A player already drawn goes after the ball: the one who forced it stays up out of his
    tackle; the fumbler gets up from where he fell."""
    if fumbler:
        track.hold("rise_1", 0.15).hold("rise_2", 0.15).hold("rise_3", 0.15)
        return
    drive = next(
        (i for i, seg in enumerate(track.segments) if seg.pose == "drive" and seg.end > pop), None
    )
    if drive is not None:
        del track.segments[drive + 1 :]
        last = track.segments[-1]
        track.t, track.x, track.z = last.end, last.x1, last.z1
        track.hold(C.STANCE, 0.15)


def _fall_on(
    play: _Play, track: _Track, key: str, loose: tuple[float, float, float], rolled: float
) -> None:
    """Get to the ball and dive on it."""
    side = 1 if track.x > loose[0] else -1
    near = (loose[0] + side * 1.2, loose[2])
    if math.hypot(track.x - near[0], track.z - near[1]) > 0.3:
        track.run(*near)
    if track.t < rolled - 0.25:
        settle(track, rolled - 0.25)
    facing = "left" if side > 0 else "right"
    track.move("tackle_dive", 0.25, loose[0] + side * 0.1, loose[2], facing)
    track.hold("recover", 1.2, facing)
    got = track.t - 1.2
    play.rest(_ball_end(play), got, loose)
    play.hold_ball(key, got)


def _scoop_and_return(
    play: _Play,
    facts: PlayFacts,
    track: _Track,
    key: str,
    loose: tuple[float, float, float],
    rolled: float,
    way: int,
    returned: re.Match[str],
) -> None:
    """Pick the ball up from the side he comes from, turn with it and return it to ESPN's spot,
    tackled by the player the text names when exactly one remains unaccounted for among ESPN's
    tacklers."""
    side = 1 if track.x > loose[0] else -1
    near = (loose[0] + side * 0.5, loose[2])
    if math.hypot(track.x - near[0], track.z - near[1]) > 0.3:
        track.run(*near)
    if track.t < rolled - 0.15:
        settle(track, rolled - 0.15)
    track.hold("catch_low", 0.15, "left" if side > 0 else "right")  # hands to the ball
    got = track.t
    facing = "right" if way > 0 else "left"
    track.move("catch_secure", 0.2, loose[0] + way * 0.3, loose[2], facing)
    play.rest(_ball_end(play), got, loose)
    play.hold_ball(key, got)
    named = [n.strip() for n in re.split(r"[;,]", returned.group(3) or "") if n.strip()]
    used = {espn_id for _, espn_id, *_ in play.actors}
    left = [
        p.espn_id
        for p in facts.players
        if p.role in ("tackler", "assistedBy", "other") and p.espn_id not in used
    ]
    left = list(dict.fromkeys(left))
    tackler = left[0] if len(named) == 1 and len(left) == 1 else None
    out = returned.group(2) != "to"
    saved = play.facts, play.end
    play.facts = play.facts.model_copy(
        update={
            "players": (PlayerRole(role="tackler", espn_id=tackler),) if tackler else (),
            "touchdown": facts.touchdown,
            "out_of_bounds": out,
        }
    )
    play.end = float(facts.action_end if facts.action_end is not None else loose[0])
    before = len(play.actors)
    C._carry(play, track, key, loose[2], way)
    play.facts, play.end = saved
    for index in range(before, len(play.actors)):
        _, espn_id, role, team_side, added, faces = play.actors[index]
        renamed = f"return_tackler_{index - before + 1}"  # the play's own tacklers keep theirs
        play.actors[index] = (renamed, espn_id, role, team_side, added, faces)
        play.labels[renamed] = play.names.get(espn_id or "") or named[0]


def _ball_end(play: _Play) -> float:
    return max(seg.end for seg in play.ball if seg.end < 1e8)


def _fumble_caption(facts: PlayFacts) -> str:
    """The play, then the fumble and who came up with it."""
    sentences = re.split(C._SENTENCE, C._body(facts.text))
    at = next((i for i, part in enumerate(sentences) if "FUMBLES" in part), None)
    loose = sentences[at] if at is not None else ""
    loose = re.sub(r"\s*\[[^\]]*\]|,? touched at [A-Z]{2,3} \d+", "", loose).rstrip(".")
    recovered = _RECOVERED.search(loose)
    after = sentences[at + 1].rstrip(".") if at is not None and at + 1 < len(sentences) else ""
    back = after if recovered and after.startswith(recovered.group(1) + " ") else ""
    flagged = [p for p in facts.penalties if not p.no_play]
    words = _penalty_words(facts, flagged[0]) if flagged else ""
    full = C.fit(C._caption(facts), loose, back, words)
    if back and full.endswith("…"):
        # The return says where it ended, so the recovery's spot and the repeated name can go:
        # "RECOVERED by SEA-D.Lawrence, to CHI 25 for no gain".
        loose = re.sub(r" at (?:[A-Z]{2,3} )?-?\d+$", "", loose)
        return C.fit(C._caption(facts), f"{loose}, {back.split(' ', 1)[1]}", words)
    return full

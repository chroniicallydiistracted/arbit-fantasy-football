"""Facts about one ESPN play, for animating it (automation slice 1).

`interpret(play, teams)` reads a stored `LivePlay` and returns `PlayFacts`. Everything comes from
ESPN's own fields first (type, spots, yards, yards after catch, named players and their roles,
penalty, review, turnover) and from its description text only where nothing structured says it:
pass depth and side, run gap, kick distance, landing and result, QB hits and the extra point.
A fact the play doesn't state stays None, and a play missing a fact its template needs lists it
in `missing`, so the app shows the text with that reason instead of guessing (LV-003).

Spots are integers in the offense's frame, yards from its own goal line: 0 is its goal line,
100 the opponent's, and a kick can land as deep as 110. They come from ESPN's `yardLine`, which
counts from the home team's goal line. ESPN's `yardsToEndzone` repeats `yardLine` on some plays
instead of flipping it for the home team, about half of punts among them, so it is only the
fallback for plays stored before `yardLine` was kept (ENG-033).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import Field

from arbit_data.live.contracts import FieldPoint, LiveModel, LivePlay

Shape = Literal[
    "pass",
    "spike",
    "interception",
    "sack",
    "run",
    "scramble",
    "kneel",
    "punt",
    "kickoff",
    "field_goal",
    "extra_point",
    "two_point",
    "fumble",
    "penalty",
    "timeout",
    "other",
]
# The shapes the choreographer has a template for (slices 2 and 3). Fumbles and no-play
# penalties get theirs in slice 3; until then they keep their facts and show their text.
TEMPLATES: frozenset[str] = frozenset(
    {
        "pass",
        "spike",
        "interception",
        "sack",
        "run",
        "scramble",
        "kneel",
        "punt",
        "kickoff",
        "field_goal",
        "extra_point",
        "two_point",
    }
)
Side = Literal["left", "middle", "right"]
KickResult = Literal[
    "good",
    "no_good",
    "blocked",
    "touchback",
    "fair_catch",
    "out_of_bounds",
    "downed",
    "returned",
    "muffed",
    "recovered",
    "short_of_landing_zone",
]
Miss = Literal[
    "wide_left", "wide_right", "short", "hit_left_upright", "hit_right_upright", "hit_crossbar"
]

# Gamebook codes in ESPN's text that differ from its team directory.
TEXT_CODES = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "LA": "LAR",
    "WAS": "WSH",
    "JAC": "JAX",
    "SD": "LAC",
    "OAK": "LV",
}
_SPOT = r"(?:(?P<{0}code>[A-Z]{{2,3}}) (?P<{0}yard>-?\d{{1,2}})|(?P<{0}mid>50))\b"
# A spot in running text: only after the words ESPN puts before one, so "for 50 yards" isn't a spot.
_AFTER = r"(?:(?<=\bto )|(?<=\bat )|(?<=\bfrom )|(?<=\bthe ))"
_NAME = r"[A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]*(?:\.? [A-Z][A-Za-z'\-]+)?"


def text_codes(texts: Iterable[str]) -> set[str]:
    """Team codes a game's play text uses for spots, such as "BLT" in "to BLT 35"."""
    return {
        m.group(1)
        for text in texts
        for m in re.finditer(_AFTER + r"([A-Z]{2,3}) -?\d{1,2}\b", text)
    }


@dataclass(frozen=True)
class GameTeams:
    """The two teams of a game and the codes its description text uses for each."""

    home: str
    away: str
    codes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def build(
        cls, home: str, away: str, home_code: str, away_code: str, seen: Iterable[str] = ()
    ) -> "GameTeams":
        """`seen` is the team codes the game's text uses, from `text_codes`."""
        codes = {home_code: home, away_code: away}
        for alias, code in TEXT_CODES.items():
            if code in codes:
                codes[alias] = codes[code]
        seen = set(seen)
        unknown = sorted(seen - codes.keys())
        named = {codes[c] for c in seen if c in codes}
        # One team always appears under its directory code; the other code belongs to the other team.
        if len(unknown) == 1 and len(named) == 1:
            codes[unknown[0]] = away if named == {home} else home
        return cls(home, away, codes)

    def other(self, team: str | None) -> str | None:
        return self.away if team == self.home else self.home if team == self.away else None


class PlayerRole(LiveModel):
    role: str
    espn_id: str


class PassFacts(LiveModel):
    result: Literal["complete", "incomplete", "intercepted", "spiked"]
    depth: Literal["short", "deep"] | None = None
    side: Side | None = None
    air_yards: int | None = None
    yards_after_catch: int | None = None
    catch_spot: int | None = None  # where a completion was caught or an interception made
    qb_hit_by: tuple[str, ...] = ()  # names in brackets in the text; ESPN gives no ID for them


class RunFacts(LiveModel):
    style: Literal["run", "sneak", "scramble", "kneel"]
    side: Side | None = None
    gap: Literal["end", "tackle", "guard", "middle"] | None = None


class KickFacts(LiveModel):
    distance: int | None = None
    landing: int | None = None  # offense frame; 100 to 110 is in the opponent's end zone
    result: KickResult | None = None
    miss: Miss | None = None
    return_yards: int | None = None
    onside: bool = False


class PenaltyFacts(LiveModel):
    team: str | None = None
    player: str | None = None
    type: str | None = None
    yards: int | None = None
    status: Literal["accepted", "declined", "offsetting"] = "accepted"
    no_play: bool = False


class FumbleFacts(LiveModel):
    forced: bool
    recovered_by: str | None = None  # team
    lost: bool | None = None
    spot: int | None = None


class PointAfter(LiveModel):
    kind: Literal["extra_point", "two_point"]
    good: bool | None = None
    miss: Miss | Literal["blocked"] | None = None


class PlayFacts(LiveModel):
    version: Literal[1] = 1
    event_id: str
    provider_id: str
    sequence: str | None
    period: int | None
    clock: str | None
    shape: Shape
    template: Shape | None = None
    missing: tuple[str, ...] = ()
    reason: str | None = None
    offense: str | None = None
    defense: str | None = None
    start: int | None = None
    end: int | None = None
    action_end: int | None = None  # where the play itself ended, before any penalty yards
    spot_source: Literal["yard_line", "yards_to_endzone"] | None = None
    down: int | None = None
    distance: int | None = None
    line_to_gain: int | None = None
    yards: int | None = None
    players: tuple[PlayerRole, ...] = ()
    shotgun: bool = False
    no_huddle: bool = False
    passing: PassFacts | None = None
    run: RunFacts | None = None
    kick: KickFacts | None = None
    fumble: FumbleFacts | None = None
    penalties: tuple[PenaltyFacts, ...] = ()
    point_after: PointAfter | None = None
    touchdown: bool = False
    safety: bool = False
    turnover: bool = False
    out_of_bounds: bool = False
    review: Literal["upheld", "reversed"] | None = None
    text: str = Field(default="", max_length=2000)
    # The play as the text tells it before a fumble or a flag that wiped it out, read like any
    # other play, so it can be drawn up to the fumble or the flag.
    before: "PlayFacts | None" = None


def interpret(play: LivePlay, teams: GameTeams) -> PlayFacts:
    text, review = _effective_text(play.text)
    main, penalties_text = _split_penalties(text)
    offense = play.start.team_id if play.start.team_id in (teams.home, teams.away) else None
    shape = _shape(play, main)
    facts: dict[str, object] = {
        "event_id": play.event_id,
        "provider_id": play.provider_id,
        "sequence": play.sequence,
        "period": play.period,
        "clock": play.clock,
        "shape": shape,
        "offense": offense,
        "defense": teams.other(offense),
        "players": tuple(PlayerRole(role=p.role, espn_id=p.espn_id) for p in play.participants),
        "shotgun": bool(re.search(r"^\((?:[^)]*\b)?Shotgun\)", main)),
        "no_huddle": bool(re.search(r"^\((?:[^)]*\b)?No Huddle\b", main)),
        "turnover": bool(play.source_flags.get("isTurnover")),
        "review": review or _review(play),
        "text": text[:2000],
        "yards": _int(play.stat_yardage),
        "penalties": _penalties(penalties_text, teams),
    }
    if shape in ("timeout", "other"):
        return PlayFacts.model_validate({**facts, "reason": "not_a_play"})
    start, source = _position(play.start, offense, teams)
    end, _ = _position(play.end, offense, teams)
    facts |= {"start": start, "end": end, "spot_source": source}
    if play.start.down is not None and play.start.distance is not None and start is not None:
        facts |= {
            "down": play.start.down,
            "distance": play.start.distance,
            "line_to_gain": min(100, start + play.start.distance),
        }
    spots = [_spot(m, "", offense, teams) for m in re.finditer(_AFTER + _SPOT.format(""), main)]
    facts["action_end"] = next((s for s in reversed(spots) if s is not None), end)
    facts["touchdown"] = "TOUCHDOWN" in main.upper() and "NULLIFIED" not in text.upper()
    facts["safety"] = bool(re.search(r"\bSAFETY\b", main))
    facts["out_of_bounds"] = bool(re.search(r"\b(?:ran|pushed|sacked) ob\b|out of bounds", main))
    facts["point_after"] = _point_after(play, text)
    if shape == "kickoff":
        facts["players"] = _kicker_from_penalty(play, main, facts["penalties"])  # type: ignore[arg-type]
    if shape in ("pass", "spike", "interception"):
        facts["passing"] = _pass(play, main, shape, start, offense, teams)
    elif shape in ("run", "scramble", "kneel"):
        facts["run"] = _run(play, main, shape)
    elif shape in ("punt", "kickoff", "field_goal", "extra_point"):
        facts["kick"] = _kick(play, main, shape, offense, teams)
    if "FUMBLE" in main.upper():
        facts["fumble"] = _fumble(main, offense, teams)
    judged = _judge(PlayFacts.model_validate(facts), play, main)
    if judged.reason in ("fumble", "no_play"):
        judged = judged.model_copy(update={"before": _before(play, main, teams)})
    return judged


_KINDS: tuple[tuple[str, str, str], ...] = (
    (r"\bINTERCEPTED\b", "interception", "Pass Interception Return"),
    (r"\bsacked\b", "sack", "Sack"),
    (r"\bpass incomplete\b", "pass", "Pass Incompletion"),
    (r"\bpass\b", "pass", "Pass Reception"),
    (r"\bpunts\b", "punt", "Punt"),
    (r"\bkicks\b", "kickoff", "Kickoff"),
    (r"\bfield goal\b", "field_goal", "Field Goal Good"),
    (
        r"\b(?:left|right) (?:end|tackle|guard)\b|\bup the middle\b|\bscrambles\b|\bkneels\b",
        "rush",
        "Rush",
    ),
)


def _before(play: LivePlay, main: str, teams: GameTeams) -> PlayFacts | None:
    """The play the text describes before a fumble or a no-play flag, or None if it describes none."""
    text = re.split(r"\s*\bFUMBLES\b", main)[0].strip()
    if not text:
        return None
    found = next(
        ((kind, label) for pattern, kind, label in _KINDS if re.search(pattern, text)), None
    )
    if found is None:
        return None
    kind, label = found
    gained = re.search(r"\bfor (-?\d+) yards?\b|\bfor (no gain)\b", text)
    yards = None if gained is None else "0" if gained.group(2) else gained.group(1)
    inner = play.model_copy(
        update={
            "kind": kind,
            "provider_type_text": label,
            "text": text,
            "cancelled": False,
            "stat_yardage": yards,
            "penalty": None,
            "end": play.start,  # where it ended comes from the text's own spot
            "source_flags": {"isTurnover": False, "isPenalty": False},
        }
    )
    facts = interpret(inner, teams)
    return facts if facts.template is not None else None


def _effective_text(text: str) -> tuple[str, Literal["upheld", "reversed"] | None]:
    """The play as finally ruled. After a reversal ESPN restates the play; that restatement counts."""
    text = re.sub(r"\s+", " ", text).strip()
    if re.search(r"and the play was REVERSED\.", text):
        after = re.split(r"and the play was REVERSED\.", text)[-1].strip()
        return re.sub(r"^\(\d{1,2}:\d{2}\)\s*", "", after) or text, "reversed"
    upheld = re.search(
        r"and the play was Upheld|ruling on the field (?:stands|was confirmed)", text
    )
    # A challenge sentence starts with the team's name, at most three words, right after a sentence.
    note = re.search(
        r"(?:^|(?<=[.)]))\s*((?:[A-Z][a-z]+ ){0,2}[A-Z][a-z]+ challenged|The Replay Official)", text
    )
    if note and note.start(1) > 0:
        text = text[: note.start(1)].strip()
    return text, "upheld" if upheld else None


def _split_penalties(text: str) -> tuple[str, str]:
    text = re.sub(r"\b[A-Z][\w.'-]* reported in as eligible\.\s*", "", text)
    at = re.search(r"\b(?:PENALTY|Penalty) on\b", text)
    return (text[: at.start()].strip(), text[at.start() :]) if at else (text, "")


def _shape(play: LivePlay, main: str) -> Shape:
    if play.kind == "administrative":
        return "timeout"
    if play.kind in ("penalty",) or (play.cancelled and not main):
        return "penalty"
    if play.kind == "pass":
        return "spike" if re.search(r"\bspiked\b", main) else "pass"
    if play.kind in ("rush", "sneak"):
        if re.search(r"\bkneels\b", main):
            return "kneel"
        return "scramble" if re.search(r"\bscrambles\b", main) else "run"
    mapping: dict[str, Shape] = {
        "sack": "sack",
        "interception": "interception",
        "punt": "punt",
        "kickoff": "kickoff",
        "field_goal": "field_goal",
        "pat": "extra_point",
        "two_point": "two_point",
        "fumble": "fumble",
    }
    return mapping.get(play.kind, "other")


def _position(
    point: FieldPoint, offense: str | None, teams: GameTeams
) -> tuple[int | None, Literal["yard_line", "yards_to_endzone"] | None]:
    if offense is None:
        return None, None
    if point.yard_line is not None:
        return (point.yard_line if offense == teams.home else 100 - point.yard_line), "yard_line"
    if point.yards_to_endzone is not None and point.team_id in (teams.home, teams.away):
        own = 100 - point.yards_to_endzone  # from that team's own goal line
        return (own if point.team_id == offense else point.yards_to_endzone), "yards_to_endzone"
    return None, None


def _spot(match: re.Match[str], prefix: str, offense: str | None, teams: GameTeams) -> int | None:
    if match.group(f"{prefix}mid"):
        return 50
    team = teams.codes.get(match.group(f"{prefix}code") or "")
    if team is None or offense is None:
        return None
    yard = int(match.group(f"{prefix}yard"))
    return yard if team == offense else 100 - yard


def _pass(
    play: LivePlay,
    main: str,
    shape: Shape,
    start: int | None,
    offense: str | None,
    teams: GameTeams,
) -> PassFacts:
    aim = re.search(r"\bpass (?:incomplete )?(short|deep) (left|middle|right)\b", main)
    hits = tuple(
        name.strip()
        for group in re.findall(r"\[([^\]]+)\]", main)
        for name in re.split(r"[;,]", group)
        if name.strip()
    )
    depth: Literal["short", "deep"] | None = (
        "deep" if aim and aim.group(1) == "deep" else "short" if aim else None
    )
    side: Side | None = _SIDES.get(aim.group(2)) if aim else None
    if shape == "spike":
        return PassFacts(result="spiked", qb_hit_by=hits)
    if shape == "interception":
        picked = re.search(
            rf"INTERCEPTED by {_NAME}(?: \([^)]*\))?(?: \[[^\]]*\])? at {_SPOT.format('a')}", main
        )
        spot = _spot(picked, "a", offense, teams) if picked else None
        air = spot - start if spot is not None and start is not None else None
        return PassFacts(
            result="intercepted",
            depth=depth,
            side=side,
            air_yards=air,
            catch_spot=spot,
            qb_hit_by=hits,
        )
    if play.provider_type_text in ("Pass Incompletion",) or re.search(r"\bpass incomplete\b", main):
        return PassFacts(result="incomplete", depth=depth, side=side, qb_hit_by=hits)
    yac = play.yards_after_catch
    # The catch's own gain is the text's "for N yards": ESPN's stat yardage is the net after an
    # accepted penalty. Yards after catch that don't fit the gain or the depth are ESPN's slip
    # and are dropped, so the catch falls back to the depth's range (ENG-032).
    said = re.search(r"\bfor (-?\d+) yards?\b|\bfor (no gain)\b", main)
    gained = (0 if said.group(2) else int(said.group(1))) if said else _int(play.stat_yardage)
    air = gained - yac if yac is not None and gained is not None else None
    if air is not None and (air < -10 or (depth == "deep" and air < 10)):
        yac = air = None
    catch = start + air if air is not None and start is not None else None
    return PassFacts(
        result="complete",
        depth=depth,
        side=side,
        air_yards=air,
        yards_after_catch=yac,
        catch_spot=catch,
        qb_hit_by=hits,
    )


def _run(play: LivePlay, main: str, shape: Shape) -> RunFacts:
    style = "kneel" if shape == "kneel" else "scramble" if shape == "scramble" else "run"
    if play.kind == "sneak":
        style = "sneak"
    lane = re.search(r"\b(left|right) (end|tackle|guard)\b", main)
    if lane:
        return RunFacts.model_validate(
            {"style": style, "side": lane.group(1), "gap": lane.group(2)}
        )
    if re.search(r"\bup the middle\b", main):
        return RunFacts.model_validate({"style": style, "side": "middle", "gap": "middle"})
    turn = re.search(r"\bscrambles (left|right)\b", main)
    return RunFacts.model_validate({"style": style, "side": turn.group(1) if turn else None})


_SIDES: dict[str, Side] = {"left": "left", "middle": "middle", "right": "right"}
_MISSES: dict[str, Miss] = {
    "wide left": "wide_left",
    "wide right": "wide_right",
    "short": "short",
    "hit left upright": "hit_left_upright",
    "hit right upright": "hit_right_upright",
    "hit crossbar": "hit_crossbar",
}


def _kick(
    play: LivePlay, main: str, shape: Shape, offense: str | None, teams: GameTeams
) -> KickFacts:
    if shape == "field_goal":
        made = re.search(
            r"(\d+) yard field goal is (GOOD|No Good|BLOCKED)(?: \([^)]*\))?(?:, ([A-Za-z ]+?))?(?:,|\.|$)",
            main,
        )
        blocked = bool(re.search(r"\bBLOCKED\b", main))
        outcome: KickResult | None = (
            "blocked"
            if blocked
            else ("good" if made.group(2) == "GOOD" else "no_good")
            if made
            else None
        )
        miss = _MISSES.get((made.group(3) or "").strip().lower()) if made else None
        return KickFacts(distance=int(made.group(1)) if made else None, result=outcome, miss=miss)
    if shape == "extra_point":
        return KickFacts(distance=None, result=_point_after_result(main))
    verb = "punts" if shape == "punt" else "kicks"
    sent = re.search(
        rf"\b{verb} (?:onside )?(\d+) yards?(?: from {_SPOT.format('f')})? to (?:landing zone to )?"
        rf"(?:(?P<endzone>end zone)|{_SPOT.format('l')})",
        main,
    )
    landing = None
    if sent:
        landing = 100 if sent.group("endzone") else _spot(sent, "l", offense, teams)
        if landing is not None and landing > 100:
            landing = min(landing, 110)
    returned = re.search(
        rf"\. {_NAME}(?: \([^)]*\))? (?:to|pushed ob at|ran ob at) .*? for (-?\d+|no gain)", main
    )
    result: KickResult | None
    if re.search(r"\bBLOCKED\b", main):
        result = "blocked"
    elif re.search(r"\bMUFFS\b", main):
        result = "muffed"
    elif re.search(r"\bfair catch\b", main):
        result = "fair_catch"
    elif re.search(r"\bTouchback\b", main, re.I):
        result = "touchback"
    elif re.search(r"\bshort of landing zone\b", main):
        result = "short_of_landing_zone"
    elif re.search(r"\bdowned by\b", main):
        result = "downed"
    elif re.search(r"\bout of bounds\b", main) and not returned:
        result = "out_of_bounds"
    elif re.search(r"\bRECOVERED by\b", main) and shape == "kickoff":
        result = "recovered"
    elif returned or any(p.role == "returner" for p in play.participants):
        result = "returned"
    else:
        result = None
    back = returned.group(1) if returned else None
    return KickFacts(
        distance=int(sent.group(1)) if sent else None,
        landing=landing,
        result=result,
        return_yards=0 if back == "no gain" else int(back) if back else None,
        onside=bool(re.search(r"\bkicks onside\b", main)),
    )


def _point_after_result(text: str) -> KickResult | None:
    made = re.search(r"extra point is (GOOD|No Good)", text)
    return ("good" if made.group(1) == "GOOD" else "no_good") if made else None


def _point_after(play: LivePlay, text: str) -> PointAfter | None:
    two = re.search(r"TWO-POINT CONVERSION ATTEMPT\..*?ATTEMPT (SUCCEEDS|FAILS)", text)
    if two:
        return PointAfter(kind="two_point", good=two.group(1) == "SUCCEEDS")
    kick = re.search(r"extra point is (GOOD|No Good)(?:, ([A-Za-z ]+?))?(?:,|\.|$)", text)
    if kick:
        reason = (kick.group(2) or "").strip().lower()
        miss: Miss | Literal["blocked"] | None = (
            "blocked" if "block" in reason else _MISSES.get(reason)
        )
        return PointAfter(kind="extra_point", good=kick.group(1) == "GOOD", miss=miss)
    if play.point_after:
        label = str(play.point_after.get("text", "")).lower()
        kind: Literal["extra_point", "two_point"] = "two_point" if "two" in label else "extra_point"
        good = True if "good" in label or "succeed" in label else False if label else None
        return PointAfter(kind=kind, good=good)
    return None


def _fumble(main: str, offense: str | None, teams: GameTeams) -> FumbleFacts:
    forced = bool(re.search(r"FUMBLES \(", main))
    other = re.search(
        rf"\b(?:RECOVERED|recovered) by ([A-Z]{{2,3}})-.*? at {_SPOT.format('r')}", main
    )
    if other:
        team = teams.codes.get(other.group(1))
        return FumbleFacts(
            forced=forced,
            recovered_by=team,
            lost=None if team is None or offense is None else team != offense,
            spot=_spot(other, "r", offense, teams),
        )
    own = re.search(rf"\band recovers at {_SPOT.format('r')}", main)
    if own:
        return FumbleFacts(
            forced=forced, recovered_by=offense, lost=False, spot=_spot(own, "r", offense, teams)
        )
    return FumbleFacts(forced=forced)


def _penalties(text: str, teams: GameTeams) -> tuple[PenaltyFacts, ...]:
    found = []
    for clause in re.split(r"(?=\b(?:PENALTY|Penalty) on\b)", text):
        hit = re.match(r"(?:PENALTY|Penalty) on ([A-Z]{2,3})(?:-([^,]+))?, ([^,.]+)", clause)
        if not hit:
            continue
        yards = re.search(r", (\d+) yards?, enforced", clause)
        status: Literal["accepted", "declined", "offsetting"] = (
            "declined"
            if "declined" in clause
            else "offsetting"
            if "offsetting" in clause.lower()
            else "accepted"
        )
        found.append(
            PenaltyFacts(
                team=teams.codes.get(hit.group(1)),
                player=(hit.group(2) or "").strip() or None,
                type=hit.group(3).strip(),
                yards=int(yards.group(1)) if yards and status == "accepted" else None,
                status=status,
                no_play="No Play" in clause,
            )
        )
    return tuple(found)


def _kicker_from_penalty(
    play: LivePlay, main: str, penalties: tuple[PenaltyFacts, ...]
) -> tuple[PlayerRole, ...]:
    """ESPN lists the kicker of an out-of-bounds or short kickoff only as the penalized player."""
    players = tuple(PlayerRole(role=p.role, espn_id=p.espn_id) for p in play.participants)
    kicker = re.match(rf"({_NAME}) kicks\b", main)
    flagged = [p for p in play.participants if p.role == "penalized"]
    if (
        kicker
        and not any(p.role == "kicker" for p in players)
        and len(flagged) == 1
        and any(f.player == kicker.group(1) for f in penalties)
    ):
        return (*players, PlayerRole(role="kicker", espn_id=flagged[0].espn_id))
    return players


def _review(play: LivePlay) -> Literal["upheld", "reversed"] | None:
    if play.review is None or play.review.upheld is None:
        return None
    return "upheld" if play.review.upheld else "reversed"


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


# What each template can't do without. Unknown names stay unknown; the app shows the text.
_NEEDS: dict[str, tuple[str, ...]] = {
    "pass": ("passer", "start", "end"),
    "spike": ("passer", "start"),
    "interception": ("passer", "start", "end", "interception_spot"),
    "sack": ("passer", "start", "end"),
    "run": ("rusher", "start", "end"),
    "scramble": ("rusher", "start", "end"),
    "kneel": ("rusher", "start", "end"),
    "punt": ("punter", "start", "landing", "kick_result"),
    "kickoff": ("kicker", "start", "landing", "kick_result"),
    "field_goal": ("kicker", "start", "distance", "kick_result"),
    "extra_point": ("kicker", "kick_result"),
    "two_point": ("start",),
}


def _judge(facts: PlayFacts, play: LivePlay, main: str) -> PlayFacts:
    if facts.shape not in TEMPLATES:
        reason = "no_play" if facts.shape == "penalty" else facts.shape
        return facts.model_copy(update={"reason": reason})
    if play.cancelled or any(p.no_play for p in facts.penalties):
        return facts.model_copy(update={"reason": "no_play"})
    if re.search(r"\bLateral\b", main):
        return facts.model_copy(update={"reason": "lateral"})
    if re.search(r"\(Aborted\)", main):
        return facts.model_copy(update={"reason": "aborted"})
    if facts.shape in ("pass", "spike", "interception", "sack") and re.search(
        r"\bDirect snap to\b", main
    ):
        # A trick play: someone else took the snap, so the passer's usual drop doesn't fit.
        return facts.model_copy(update={"reason": "trick_play"})
    roles = {p.role for p in facts.players}
    have = {
        "start": facts.start is not None,
        "end": facts.end is not None,
        "interception_spot": facts.passing is not None and facts.passing.catch_spot is not None,
        "landing": facts.kick is not None and facts.kick.landing is not None,
        "kick_result": facts.kick is not None and facts.kick.result is not None,
        "distance": facts.kick is not None and facts.kick.distance is not None,
    }
    if facts.shape == "pass" and facts.passing and facts.passing.result == "complete":
        needs = (*_NEEDS["pass"], "receiver")
    else:
        needs = _NEEDS[facts.shape]
    missing = tuple(need for need in needs if not have.get(need, need in roles))
    return facts.model_copy(update={"template": facts.shape, "missing": missing})

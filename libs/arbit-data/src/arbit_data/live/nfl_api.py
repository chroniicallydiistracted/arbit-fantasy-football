"""The NFL API as Arbit's primary live source (OWN-041): its game records as stored plays.

`api.nfl.com` is the raw source nflverse captures. Its v2 game details carry every play with the
game clock at the snap, the snap and whistle times, and each player's stats with his GSIS ID and
jersey number ([survey](docs/research/nfl-api-data-survey-2026-11-05.md)). This module turns
those records into the same `LivePlay` the ESPN lane stores, keyed by the same play ID, so the
Live page, the interpreter, the choreographer and the board work unchanged with the NFL as their
source. ESPN's live feed is the emergency fallback.

- **The play ID** is ESPN's event ID followed by the NFL play ID; this held on every football
  play of week 8 (152 of 152 in CHI at SEA).
- **Players' roles** come from their stats. Each stat type's ESPN role was learned by joining
  week 8's 14 games in both sources, such as 10 → rusher (769 of 769) and 79 → tackler (999 of
  1,006). GSIS IDs become ESPN IDs through nflverse's players table, which the caller passes.
- **Tries** are their own NFL plays. ESPN folds a try into its touchdown, so the converter does
  too: its text is appended, its players take ESPN's try roles, and its points count on the
  touchdown.
- **The clock at the whistle** is the snap clock minus the snap-to-whistle time on plays from
  scrimmage. It matched ESPN's clock on all 7 CHI at SEA scoring plays, which ESPN times after
  the play. A kickoff's clock starts at the touch, so it has none.
- **Every field** of the NFL record is kept on the play (`nfl`), with the try's.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from arbit_data.live.contracts import FieldPoint, LivePlay, Participant
from arbit_data.live.normalize import _kind
from arbit_data.live.play_facts import TEXT_CODES

# Each NFL stat type's ESPN participant roles, learned from week 8 in both sources.
STAT_ROLES: dict[int, tuple[str, ...]] = {
    10: ("rusher",),
    11: ("rusher", "scorer"),
    12: ("rusher",),
    13: ("rusher", "scorer"),
    14: ("passer",),
    15: ("passer",),
    16: ("passer",),
    19: ("passer",),
    20: ("passer",),
    111: ("passer",),
    112: ("passer",),
    21: ("receiver",),
    22: ("receiver", "scorer"),
    23: ("receiver",),
    24: ("receiver", "scorer"),
    113: ("receiver",),
    115: ("receiver",),
    25: ("passDefender", "returner"),
    26: ("passDefender", "returner", "scorer"),
    27: ("returner",),
    28: ("returner", "scorer"),
    29: ("punter",),
    30: ("punter",),
    31: ("punter",),
    32: ("punter",),
    33: ("returner",),
    34: ("returner", "scorer"),
    35: ("returner",),
    36: ("returner", "scorer"),
    39: ("returner",),
    41: ("kicker",),
    42: ("kicker",),
    43: ("kicker",),
    44: ("kicker",),
    410: ("kicker",),
    422: ("kicker",),
    426: ("kicker",),
    45: ("returner",),
    46: ("returner", "scorer"),
    47: ("returner",),
    48: ("returner", "scorer"),
    52: ("fumbler",),
    53: ("fumbler",),
    54: ("fumbler",),
    106: ("fumbler",),
    55: ("recoverer",),
    56: ("recoverer", "scorer"),
    57: ("recoverer",),
    58: ("recoverer", "scorer"),
    59: ("recoverer",),
    60: ("recoverer", "scorer"),
    61: ("recoverer",),
    62: ("recoverer", "scorer"),
    69: ("kicker",),
    70: ("kicker", "scorer"),
    71: ("kicker",),
    79: ("tackler",),
    80: ("other",),
    82: ("assistedBy",),
    83: ("sackedBy", "tackler"),
    84: ("sackedBy", "assistedBy"),
    85: ("passDefender",),
    86: ("other",),
    87: ("other",),
    88: ("other",),
    89: ("scorer",),
    91: ("forcedBy",),
    93: ("penalized",),
    110: ("other",),  # a quarterback hit: ESPN names the hitter "other"
}
# A try's stats, as ESPN names them on the touchdown.
TRY_ROLES: dict[int, tuple[str, ...]] = {
    72: ("patScorer", "kicker"),
    73: ("patScorer", "kicker"),
    74: ("patScorer", "kicker"),
    75: ("patRusher", "patScorer"),
    76: ("patRusher",),
    77: ("patPasser",),
    78: ("patPasser",),
    104: ("patScorer",),
    105: ("patScorer",),
}
INTERCEPTIONS = {19, 25, 26}
FUMBLES = {52, 53, 54, 106}
LOST = {59, 60, 61, 62, 106}
OWN = {55, 56, 57, 58}
SCORE_VALUES = {"TOUCHDOWN": 6, "FIELD_GOAL": 3, "PAT": 1, "PAT2": 2, "SAFETY": 2}
TRIES = ("XP_KICK", "PAT2")
SCRIMMAGE = ("PASS", "RUSH", "SACK", "PUNT", "FIELD_GOAL", "PENALTY")
# NFL and gamebook codes for a team, beyond ESPN's own: Arizona is "AZ" in NFL yard lines.
NFL_CODES = {**TEXT_CODES, "AZ": "ARI", "LA": "LAR", "WAS": "WSH", "LARC": "LAC"}
_CLOCK_PREFIX = re.compile(r"^\(\s*\d{0,2}:\d\d\)\s*")


@dataclass(frozen=True)
class GameLink:
    """One game in both sources: the NFL game's UUID and ESPN's event and teams."""

    game_id: str
    event_id: str
    home: str  # ESPN team IDs
    away: str
    home_code: str  # ESPN team codes
    away_code: str
    codes: dict[str, str] = field(default_factory=dict)

    def team(self, code: str | None) -> str | None:
        """The ESPN team ID for a code as NFL writes it ("AZ", "LAR", "SEA")."""
        if not code:
            return None
        espn = NFL_CODES.get(code, code)
        return (
            self.home if espn == self.home_code else self.away if espn == self.away_code else None
        )


def play_id(link: GameLink, record: Mapping[str, Any]) -> str:
    return f"{link.event_id}{record['playId']}"


def _seconds(clock: str | None) -> int | None:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", (clock or "").strip())
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def _clock(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    whole = max(0, round(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def _instant(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def duration(record: Mapping[str, Any]) -> float | None:
    """Seconds from the snap to the whistle, when the record has both."""
    start, end = _instant(record.get("playStartTime")), _instant(record.get("playEndTime"))
    if start is None or end is None or end < start:
        return None
    return (end - start).total_seconds()


def clock_end(record: Mapping[str, Any]) -> str | None:
    """The game clock at the whistle: the snap clock less the play's time. A kickoff's clock
    starts at the touch and a try's doesn't run, so they have none."""
    if record.get("playType") not in SCRIMMAGE:
        return None
    snap, took = _seconds(record.get("clockTime")), duration(record)
    return _clock(snap - took) if snap is not None and took is not None else None


def _point(link: GameLink, record: Mapping[str, Any] | None) -> FieldPoint:
    """A record's pre-snap state: possession from its summary ("SEA  1-15  SEA 45"), the spot
    from its yard line, both in ESPN's frames."""
    if record is None:
        return FieldPoint()
    # "SEA  1-15  SEA 45", "GB  2-Goal  CAR 2", "BUF  KO  BUF 35" for a kickoff, "BUF  XP  BAL 15".
    summary = re.match(
        r"\s*([A-Z]{2,4})\s+(?:\d-(?:\d+|Goal)|KO|XP|2P|2PT)\s", record.get("prePlayByPlay") or ""
    )
    team = link.team(summary.group(1)) if summary else None
    spot = re.fullmatch(r"\s*([A-Z]{2,4})?\s*(\d{1,2})\s*", record.get("yardLine") or "")
    yard_line = None
    if spot:
        yard = int(spot.group(2))
        side = link.team(spot.group(1)) if spot.group(1) else None
        if yard == 50:
            yard_line = 50
        elif side is not None:
            yard_line = yard if side == link.home else 100 - yard  # from the home goal line
    to_endzone = None
    if yard_line is not None and team is not None:
        to_endzone = 100 - yard_line if team == link.home else yard_line
    down = record.get("down")
    distance = record.get("yardsRemaining")
    return FieldPoint(
        yards_to_endzone=to_endzone,
        team_id=team,
        down=down if down in (0, 1, 2, 3, 4) else None,  # 0 on a kickoff, as ESPN has it
        source_down=str(down) if down is not None else None,
        distance=distance if isinstance(distance, int) and 0 <= distance <= 100 else None,
        yard_line=yard_line,
    )


def _label(record: Mapping[str, Any], text: str, stats: set[int]) -> str:
    """ESPN's play type for an NFL record, so the shared `_kind` reads it the same way."""
    kind = record.get("playType")
    scored = record.get("scoringPlayType") == "TOUCHDOWN"
    if stats & FUMBLES and kind in ("PASS", "RUSH", "SACK"):
        if 60 in stats or (scored and stats & LOST):
            return "Fumble Return Touchdown"
        if stats & LOST:
            return "Sack Opp Fumble Recovery" if kind == "SACK" else "Fumble Recovery (Opponent)"
        if stats & OWN:
            return "Fumble Recovery (Own)"
    if kind == "PASS":
        if stats & INTERCEPTIONS:
            return "Interception Return Touchdown" if 26 in stats else "Pass Interception Return"
        if scored:
            return "Passing Touchdown"
        return "Pass Incompletion" if re.search(r"\bincomplete\b", text) else "Pass Reception"
    if kind == "RUSH":
        return "Rushing Touchdown" if scored else "Rush"
    if kind == "SACK":
        return "Sack"
    if kind == "PUNT":
        return "Punt"
    if kind == "KICK_OFF":
        return "Kickoff Return Touchdown" if 46 in stats else "Kickoff"
    if kind == "FIELD_GOAL":
        if stats & {71, 88} or re.search(r"\bBLOCKED\b", text):
            return "Blocked Field Goal"
        return "Field Goal Good" if 70 in stats or "is GOOD" in text else "Field Goal Missed"
    if kind == "PENALTY" or (kind == "UNSPECIFIED" and re.search(r"\bpenalty\b", text, re.I)):
        return "Penalty"
    if kind == "TIMEOUT":
        if re.search(r"two-minute warning", text, re.I):
            return "Two-minute warning"
        return "Timeout" if re.search(r"\bTimeout #\d", text) else "Official Timeout"
    if kind == "END_QUARTER":
        return "End Period"
    if kind == "END_GAME":
        return "End of Game"
    return "Unknown"


def _participants(
    records: list[tuple[Mapping[str, Any], Mapping[int, tuple[str, ...]]]],
    ids: Mapping[str, str],
    interception: bool,
) -> tuple[tuple[Participant, ...], dict[str, str]]:
    found: list[Participant] = []
    jerseys: dict[str, str] = {}
    for record, roles in records:
        for stat in record.get("stats") or []:
            espn_id = ids.get(stat.get("gsisPlayerId") or "")
            if espn_id is None:
                continue
            if stat.get("gsisPlayerJerseyNumber"):
                jerseys[espn_id] = str(int(stat["gsisPlayerJerseyNumber"]))
            kinds = roles.get(stat.get("statType"), ())
            if interception and stat.get("statType") in (113, 115):
                kinds = ("other",)  # ESPN names an interception's intended receiver "other"
            for role in kinds:
                person = Participant(espn_id=espn_id, role=role)
                if person not in found:
                    found.append(person)
    return tuple(found), jerseys


_NUMBERED = r"(\d{1,2})-([A-Z][a-z]{0,3}\.[A-Z][A-Za-z'\-]*(?:\.? [A-Z][a-z][A-Za-z'\-]*)?)"
# A wiped-out play's roles as its text names them, in the shapes ESPN lists participants for.
_WIPED_ROLES = (
    (re.compile(rf"{_NUMBERED} pass\b"), ("passer",)),
    (
        re.compile(rf"\bpass (?:incomplete )?(?:short|deep) (?:left|middle|right) to {_NUMBERED}"),
        ("receiver",),
    ),
    (re.compile(rf"\bintended for {_NUMBERED}"), ("other",)),
    (
        re.compile(
            rf"{_NUMBERED} (?:left|right) (?:end|tackle|guard)\b|{_NUMBERED} up the middle\b"
        ),
        ("rusher",),
    ),
    (re.compile(rf"{_NUMBERED} (?:scrambles|kneels)\b"), ("rusher",)),
    (re.compile(rf"{_NUMBERED} sacked\b"), ("passer",)),
)
_TACKLERS = re.compile(rf"\({_NUMBERED}(?:[;,] {_NUMBERED})?\)")


def _game_players(
    records: list[Mapping[str, Any]], ids: Mapping[str, str]
) -> dict[tuple[str, str], str]:
    """Each player in the game's stats by (name as the text writes it, jersey number): his ESPN ID."""
    found: dict[tuple[str, str], str] = {}
    for record in records:
        for stat in record.get("stats") or []:
            espn_id = ids.get(stat.get("gsisPlayerId") or "")
            name, number = stat.get("gsisPlayerName"), stat.get("gsisPlayerJerseyNumber")
            if espn_id and name and number:
                found[(name, str(int(number)))] = espn_id
    return found


def _wiped_out(
    record: Mapping[str, Any], players: Mapping[tuple[str, str], str]
) -> list[Participant]:
    """The players of a play a flag wiped out. The NFL keeps no stats for it beyond the foul, but
    its text names each player with his number, and he appears in the game's other plays."""
    text = str(record.get("playDescriptionWithJerseyNumbers") or "")
    main = re.split(r"\b(?:PENALTY|Penalty) on\b", text)[0]
    found: list[Participant] = []

    def add(number: str | None, name: str | None, role: str) -> None:
        espn_id = players.get((name or "", str(int(number))) if number else ("", ""))
        if espn_id and Participant(espn_id=espn_id, role=role) not in found:
            found.append(Participant(espn_id=espn_id, role=role))

    for pattern, roles in _WIPED_ROLES:
        for match in pattern.finditer(main):
            groups = [g for g in match.groups()]
            for i in range(0, len(groups), 2):
                if groups[i]:
                    for role in roles:
                        add(groups[i], groups[i + 1], role)
    sacked = re.search(rf"\bsacked\b.*?\({_NUMBERED}", main)
    if sacked:
        add(sacked.group(1), sacked.group(2), "sackedBy")
    else:
        for match in _TACKLERS.finditer(main):
            add(match.group(1), match.group(2), "tackler")
            if match.group(3):
                add(match.group(3), match.group(4), "assistedBy")
    return found


def to_live_plays(
    game: Mapping[str, Any], link: GameLink, ids: Mapping[str, str], season: int
) -> tuple[LivePlay, ...]:
    """Every play of an NFL v2 game details response as ESPN-shaped plays, in game order.
    `ids` maps GSIS player IDs to ESPN's."""
    records = sorted(
        (
            r
            for r in (game.get("driveChart") or {}).get("plays") or []
            if r.get("playId") is not None
        ),
        key=lambda r: (r.get("playSequenceNumber") or 0, r["playId"]),
    )
    football = [r for r in records if r.get("playType") not in TRIES and not r.get("playDeleted")]
    following = {
        id(r): next(
            (
                n
                for n in football[i + 1 :]
                if n.get("playType") not in ("TIMEOUT", "END_QUARTER", "END_GAME", "GAME_START")
                and n.get("prePlayByPlay")
            ),
            None,
        )
        for i, r in enumerate(football)
    }
    # Each touchdown's try is the try that follows it before the next snap from scrimmage or
    # kickoff; a flag or a timeout can come between them.
    tries: dict[int, Mapping[str, Any]] = {}
    last_touchdown = None
    for record in records:
        if record.get("scoringPlayType") == "TOUCHDOWN" and record.get("playType") not in TRIES:
            last_touchdown = record
        elif record.get("playType") in TRIES and last_touchdown is not None:
            tries[id(last_touchdown)] = record
            last_touchdown = None
        elif record.get("playType") not in ("TIMEOUT", "END_QUARTER", "UNSPECIFIED", "PENALTY"):
            last_touchdown = None
    # The score after every record, tries included, in game order.
    nfl_home = (game.get("homeTeam") or {}).get("id")
    running = {link.home: 0, link.away: 0}
    after: dict[int, dict[str, int]] = {}
    for record in records:
        kind = record.get("scoringPlayType")
        team = record.get("scoringTeamId")
        if kind in SCORE_VALUES and team:
            running[link.home if team == nfl_home else link.away] += SCORE_VALUES[kind]
        after[id(record)] = dict(running)
    summary = game.get("summary") or {}
    nfl_home = (game.get("homeTeam") or {}).get("id")
    players = _game_players(records, ids)
    plays: list[LivePlay] = []
    for record in records:
        if record.get("playType") in TRIES:
            continue
        text = _CLOCK_PREFIX.sub("", record.get("playDescription") or "").strip()
        if not text or record.get("playType") == "GAME_START":
            continue  # blank placeholders and the opening record aren't plays
        tried = tries.get(id(record))
        try_text = _CLOCK_PREFIX.sub("", (tried or {}).get("playDescription") or "").strip()
        stats = {s.get("statType") for s in record.get("stats") or []}
        label = _label(record, text, stats)
        participants, jerseys = _participants(
            [(record, STAT_ROLES)] + ([(tried, TRY_ROLES)] if tried else []),
            ids,
            bool(stats & INTERCEPTIONS),
        )
        if re.search(r"\bno play\b", text, re.I) and not any(
            p.role != "penalized" for p in participants
        ):
            participants = tuple(_wiped_out(record, players)) + participants
        # ESPN's score on a touchdown already includes its try; on any play it never trails a
        # try that came before it.
        score = after[id(tried)] if tried else after[id(record)]
        start = _point(link, record)
        nxt = following.get(id(record))
        end = _point(link, nxt) if nxt is not None else _summary_point(link, summary, nfl_home)
        scoring = record.get("scoringPlayType")
        if scoring in ("TOUCHDOWN", "FIELD_GOAL", "SAFETY") and start.team_id is not None:
            # A score ends in an end zone, not where the next play starts: the opponent's for the
            # offense's points, its own for a safety or the defense's touchdown.
            scorer = record.get("scoringTeamId")
            for_offense = (scorer == nfl_home) == (start.team_id == link.home)
            frame = 100 if scoring != "SAFETY" and for_offense else 0
            end = FieldPoint(
                yards_to_endzone=100 - frame,
                team_id=start.team_id,
                yard_line=frame if start.team_id == link.home else 100 - frame,
            )
        effects: set[str] = {_kind(label, text)}
        turnover = bool(stats & INTERCEPTIONS or stats & LOST)
        if turnover:
            effects.add("turnover")
        penalty = bool(93 in stats or re.search(r"\bpenalty\b", text, re.I))
        if penalty:
            effects.add("penalty")
        point_after = None
        if tried:
            good = tried.get("scoringPlayType") in ("PAT", "PAT2")
            kind = "Two Point" if tried.get("playType") == "PAT2" else "Extra Point"
            point_after = {"text": f"{kind} {'Good' if good else 'Missed'}"}
            effects.add("two_point" if tried.get("playType") == "PAT2" else "pat")
        yac = next(
            (s.get("yards") for s in record.get("stats") or [] if s.get("statType") == 113), None
        )
        full_text = f"{text} {try_text}".strip() if try_text else text
        plays.append(
            LivePlay(
                event_id=link.event_id,
                provider_id=play_id(link, record),
                sequence=str(
                    int(round(float(record.get("playSequenceNumber") or record["playId"]) * 100))
                ),
                provider_type_id=None,
                provider_type_text=label,
                kind=_kind(label, text),
                text=full_text,
                period=record.get("quarter"),
                clock=_clock(_seconds(record.get("clockTime"))),
                home_score=str(score[link.home]),
                away_score=str(score[link.away]),
                scoring_play=bool(record.get("playScored")),
                score_value=str(SCORE_VALUES.get(record.get("scoringPlayType") or "", 0)),
                cancelled=bool(record.get("playDeleted"))
                or bool(re.search(r"\bno play\b", text, re.I)),
                modified_at=None,
                wallclock=record.get("playStartTime"),
                participants=participants,
                start=start,
                end=end,
                can_connect_endpoints=False,
                effects=tuple(sorted(effects)),
                point_after=point_after,
                stat_yardage=str(record["yardsGained"])
                if isinstance(record.get("yardsGained"), int)
                else None,
                source_flags={"isTurnover": turnover, "isPenalty": penalty},
                yards_after_catch=yac if isinstance(yac, int) else None,
                source="nfl",
                snap_at=record.get("playStartTime"),
                whistle_at=record.get("playEndTime"),
                clock_end=clock_end(record),
                jerseys=jerseys or None,
                nfl={"play": dict(record), **({"try": dict(tried)} if tried else {})},
            )
        )
    return tuple(plays)


def attached_try(play: LivePlay) -> LivePlay | None:
    """The NFL try folded into this touchdown, with its own provider facts."""
    raw = (play.nfl or {}).get("try")
    if not isinstance(raw, Mapping):
        return None
    return play.model_copy(
        update={
            "period": raw.get("quarter"),
            "clock": _clock(_seconds(raw.get("clockTime"))),
            "clock_end": None,  # tries do not run the game clock
            "text": _CLOCK_PREFIX.sub("", raw.get("playDescription") or "").strip(),
            "snap_at": raw.get("playStartTime"),
            "whistle_at": raw.get("playEndTime"),
            "cancelled": play.cancelled or bool(raw.get("playDeleted")),
        }
    )


def _summary_point(link: GameLink, summary: Mapping[str, Any], nfl_home: str | None) -> FieldPoint:
    """The game's state now, for the last play: after it, until the next play arrives."""
    if not summary or summary.get("phase") not in ("INGAME", "HALFTIME"):
        return FieldPoint()
    home = summary.get("homeTeam") or {}
    team = (
        link.home
        if home.get("hasPossession")
        else link.away
        if (summary.get("awayTeam") or {}).get("hasPossession")
        else None
    )
    record = {
        "prePlayByPlay": None,
        "yardLine": summary.get("yardLine"),
        "down": summary.get("down"),
        "yardsRemaining": summary.get("distance"),
    }
    point = _point(link, record)
    to_endzone = None
    if point.yard_line is not None and team is not None:
        to_endzone = 100 - point.yard_line if team == link.home else point.yard_line
    return point.model_copy(update={"team_id": team, "yards_to_endzone": to_endzone})

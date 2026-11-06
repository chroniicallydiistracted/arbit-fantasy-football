"""The stadium board's state at each play (automation slice 5, item 10 of the live play plan).

A board in the full-field view shows the game as it stood at the play on screen. For each play
`GameBoard.boards` gives the state at the snap (`before`) and once the play is over (`after`),
with the results shown in large type in between, such as "TOUCHDOWN". A touchdown's try gets a
board of its own, as it gets a script of its own. This is the one implementation of those facts:
the review renderer draws it now and the browser will in slice 7.

Everything comes from the stored plays, in ESPN's order:
- **Scores.** ESPN gives the score after each play, and a touchdown's already includes its try.
  The score before a play is the one after the play before it. A touchdown shows its own six,
  and its try ends at ESPN's score. A play that scores nothing never lowers a score: a flag on
  the try is recorded with the score before the kick.
- **Timeouts.** They aren't stored per play, but the plays record them: "Timeout #2 by SEA at
  1:46." and, after a lost challenge, "Dallas challenged ... (Timeout #1.)". ESPN numbers them
  within each half, so its number is how many that team has used. Each half starts with 3, and
  overtime with 2, the NFL's regular-season rules.
- **Down, distance, spot and possession** come from the play's facts at the snap and from ESPN's
  end of the play after it.
- **The clock** is ESPN's clock at the snap, kept through the play: when the play ended isn't
  known, so the board doesn't run a clock it would have to invent.

Unknown stays unknown. A challenge whose team can't be named leaves both teams' timeouts
unknown until the half ends, and a scoring play without a score shows an unknown score.
"""

import re
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Literal

from arbit_data.live.contracts import FieldPoint, LiveModel, LivePlay
from arbit_data.live.play_facts import GameTeams, PlayFacts

Situation = Literal["down", "kickoff", "extra_point", "two_point"]
ResultKind = Literal[
    "touchdown",
    "field_goal",
    "extra_point",
    "two_point",
    "no_good",
    "blocked",
    "safety",
    "interception",
    "fumble",
    "downs",
    "penalty",
]
# How each result reads, in the owner's colors (OWN-039): scores are good (green), turnovers and
# misses bad (red), and flags yellow. One place, so every renderer shows the same.
Tone = Literal["good", "bad", "flag"]
TONE: dict[str, Tone] = {
    "touchdown": "good",
    "field_goal": "good",
    "extra_point": "good",
    "two_point": "good",
    "safety": "good",
    "no_good": "bad",
    "blocked": "bad",
    "interception": "bad",
    "fumble": "bad",
    "downs": "bad",
    "penalty": "flag",
}
# The words each result shows. A penalty shows its own name, as ESPN gives it.
RESULT_TEXT: dict[str, str] = {
    "touchdown": "TOUCHDOWN",
    "field_goal": "FIELD GOAL GOOD",
    "extra_point": "EXTRA POINT GOOD",
    "two_point": "TWO-POINT GOOD",
    "no_good": "NO GOOD",
    "blocked": "BLOCKED",
    "safety": "SAFETY",
    "interception": "INTERCEPTED",
    "fumble": "FUMBLE",
    "downs": "TURNOVER ON DOWNS",
}
TIMEOUTS_PER_HALF = 3
TIMEOUTS_IN_OVERTIME = 2
_SCRIMMAGE = ("pass", "spike", "sack", "run", "scramble", "kneel")
_CALLED = re.compile(r"\bTimeout #(\d) by ([A-Z]{2,3})\b")
_CHALLENGE = re.compile(
    r"(?:^|[.)]\s*)([A-Z][A-Za-z.' -]*?) challenged\b[^#]*?\(Timeout #(\d)\.?\)"
)


class BoardSide(LiveModel):
    team_id: str
    code: str
    score: int | None
    timeouts: int | None  # left in the half


class BoardSpot(LiveModel):
    team_id: str | None  # whose half the ball is in; None at midfield
    yard: int


class BoardState(LiveModel):
    period: int | None
    clock: str | None
    away: BoardSide
    home: BoardSide
    possession: str | None = None
    situation: Situation | None = None
    down: int | None = None
    distance: int | None = None
    goal_to_go: bool = False
    spot: BoardSpot | None = None


class BoardResult(LiveModel):
    kind: ResultKind
    text: str
    # The team it is for: the scorer, the team that took the ball, or the team flagged.
    team_id: str | None
    tone: Tone
    jersey: str | None = None  # a penalty's player's number, when ESPN names him and it's known
    detail: str | None = None  # a penalty's "DECLINED" or "OFFSETTING"


class PlayBoard(LiveModel):
    version: Literal[1] = 1
    event_id: str
    provider_id: str
    part: Literal["play", "try"] = "play"
    before: BoardState
    after: BoardState
    results: tuple[BoardResult, ...] = ()


def _score(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return (
        int(number) if number.is_finite() and number == int(number) and 0 <= number < 1000 else None
    )


def _half(period: int) -> int:
    return 1 if period <= 2 else 2 if period <= 4 else period  # each overtime period on its own


def _same_player(text_name: str, full_name: str) -> bool:
    """Whether the play text's "J.Jackson" or "Ja.Williams" could be this full name."""
    match = re.fullmatch(r"([A-Z][a-z]*)\.\s?(.+)", text_name.strip())
    if match is None:
        return False
    prefix, last = match.groups()
    full = re.sub(r",? (?:Jr\.|Sr\.|II|III|IV|V)$", "", full_name.strip())
    first, _, rest = full.partition(" ")
    return first.startswith(prefix) and (rest == last or rest.endswith(" " + last))


def _result(kind: ResultKind, team: str | None) -> BoardResult:
    return BoardResult(kind=kind, text=RESULT_TEXT[kind], team_id=team, tone=TONE[kind])


class GameBoard:
    """One game's board, fed every stored play in ESPN's order (timeouts and all)."""

    def __init__(
        self,
        teams: GameTeams,
        home_code: str,
        away_code: str,
        names: Mapping[str, Iterable[str]] | None = None,
        roster: Mapping[str, Iterable[tuple[str | None, str, str]]] | None = None,
    ):
        """`names` are the names a team's text may use. `roster` is each team's players for the
        game's week, by ESPN team ID: (ESPN player ID or None, full name, jersey number)."""
        self.teams = teams
        self.roster = {team: list(players) for team, players in (roster or {}).items()}
        self.codes = {teams.home: home_code, teams.away: away_code}
        # The names a play's text may call a team by, such as "Dallas" or "Los Angeles Chargers".
        # A name both teams share, such as "Los Angeles", names neither.
        claims: dict[str, set[str]] = {}
        for team, known in (names or {}).items():
            for name in known:
                claims.setdefault(name.casefold(), set()).add(team)
        self.names = {
            name: next(iter(owners)) for name, owners in claims.items() if len(owners) == 1
        }
        self.scores: dict[str, int | None] = {teams.home: 0, teams.away: 0}
        self.half = 1
        self.used: dict[str, int] = {teams.home: 0, teams.away: 0}
        self.timeouts_known = True

    # --- the game as it stands -------------------------------------------------------------------

    def _left(self, team: str) -> int | None:
        if not self.timeouts_known:
            return None
        allowed = TIMEOUTS_PER_HALF if self.half <= 2 else TIMEOUTS_IN_OVERTIME
        used = self.used[team]
        return allowed - used if used <= allowed else None

    def _side(self, team: str, scores: Mapping[str, int | None]) -> BoardSide:
        return BoardSide(
            team_id=team, code=self.codes[team], score=scores[team], timeouts=self._left(team)
        )

    def _state(
        self,
        play: LivePlay,
        scores: Mapping[str, int | None],
        clock: str | None = None,
        rest: Mapping[str, object] | None = None,
    ) -> BoardState:
        return BoardState(
            period=play.period,
            clock=clock or play.clock,
            away=self._side(self.teams.away, scores),
            home=self._side(self.teams.home, scores),
            **dict(rest or {}),  # type: ignore[arg-type]
        )

    def _enter(self, period: int | None) -> None:
        """A new half resets the timeouts, and with them anything unknown about them."""
        if period is not None and _half(period) != self.half:
            self.half = _half(period)
            self.used = dict.fromkeys(self.used, 0)
            self.timeouts_known = True

    def _charge(self, text: str) -> None:
        """Timeouts this play's text records: called ones, and those lost with a challenge."""
        for number, code in _CALLED.findall(text):
            team = self.teams.codes.get(code)
            if team in self.used:
                self.used[team] = max(self.used[team], int(number))
            else:
                self.timeouts_known = False
        for name, number in _CHALLENGE.findall(text):
            team = self.names.get(name.strip().casefold())
            if team in self.used:
                self.used[team] = max(self.used[team], int(number))
            else:
                self.timeouts_known = False

    # --- where the ball is ---------------------------------------------------------------------

    def _spot_from_offense(self, yards: int | None, offense: str | None) -> BoardSpot | None:
        """A spot in the offense's frame, yards from its own goal line."""
        if yards is None or offense is None or not 1 <= yards <= 99:
            return None
        if yards == 50:
            return BoardSpot(team_id=None, yard=50)
        return (
            BoardSpot(team_id=offense, yard=yards)
            if yards < 50
            else BoardSpot(team_id=self.teams.other(offense), yard=100 - yards)
        )

    def _end(self, point: FieldPoint) -> dict[str, object]:
        """ESPN's end of the play: the next down, its distance, the spot and who has the ball."""
        team = point.team_id if point.team_id in self.codes else None
        if team is None or point.down not in (1, 2, 3, 4) or point.yard_line is None:
            return {}
        own = point.yard_line if team == self.teams.home else 100 - point.yard_line
        if not 1 <= own <= 99 or point.distance is None or point.distance < 1:
            return {}
        return {
            "possession": team,
            "situation": "down",
            "down": point.down,
            "distance": point.distance,
            "goal_to_go": point.distance >= 100 - own,
            "spot": self._spot_from_offense(own, team),
        }

    def _start(self, facts: PlayFacts) -> dict[str, object]:
        offense = facts.offense if facts.offense in self.codes else None
        start: dict[str, object] = {"possession": offense}
        if facts.shape == "kickoff":
            start["situation"] = "kickoff"
        elif facts.shape in ("extra_point", "two_point"):
            start["situation"] = facts.shape
            return start
        elif facts.down in (1, 2, 3, 4) and facts.distance is not None and facts.distance >= 1:
            start |= {"situation": "down", "down": facts.down, "distance": facts.distance}
            if facts.start is not None:
                start["goal_to_go"] = facts.distance >= 100 - facts.start
        start["spot"] = self._spot_from_offense(facts.start, offense)
        return start

    # --- results ---------------------------------------------------------------------------------

    def _results(self, play: LivePlay, facts: PlayFacts, scorer: str | None) -> list[BoardResult]:
        offense, defense = facts.offense, facts.defense
        results: list[BoardResult] = []
        if facts.shape == "interception":
            results.append(_result("interception", defense))
        elif facts.fumble is not None and facts.fumble.lost:
            results.append(_result("fumble", facts.fumble.recovered_by or defense))
        if facts.touchdown:
            results.append(_result("touchdown", scorer or (defense if results else offense)))
        if facts.safety:
            results.append(_result("safety", defense))
        if facts.shape == "field_goal" and facts.kick is not None:
            if facts.kick.result == "good":
                results.append(_result("field_goal", offense))
            elif facts.kick.result == "no_good":
                results.append(_result("no_good", offense))
            elif facts.kick.result == "blocked":
                results.append(_result("blocked", defense))
        if (
            not results
            and facts.down == 4
            and facts.shape in _SCRIMMAGE
            and play.end.team_id == defense
            and play.end.down == 1
        ):
            results.append(_result("downs", defense))
        return results

    def _penalties(self, play: LivePlay, facts: PlayFacts) -> list[BoardResult]:
        """A card for each flag: the foul, the team and the player's number (OWN-039)."""
        penalized = {person.espn_id for person in play.participants if person.role == "penalized"}
        named = [penalty for penalty in facts.penalties if penalty.player]
        # The NFL's own record of the game names each fouling player with his number that night
        # ("PENALTY on SEA-53-Q.Nelson"), declined fouls included (OWN-041).
        text = str(
            ((play.nfl or {}).get("play") or {}).get("playDescriptionWithJerseyNumbers") or ""
        )
        numbered = {
            name.strip(): number
            for number, name in re.findall(
                r"(?:PENALTY|Penalty) on [A-Z]{2,4}-(\d{1,2})-([A-Z][a-z]*\.[A-Za-z' .-]+?),", text
            )
        }
        cards = []
        for penalty in facts.penalties:
            cards.append(
                BoardResult(
                    kind="penalty",
                    text=(penalty.type or "Penalty").upper(),
                    team_id=penalty.team if penalty.team in self.codes else None,
                    tone="flag",
                    jersey=numbered.get(penalty.player or "")
                    or self._number(penalty.team, penalty.player, penalized, len(named) == 1),
                    detail={"declined": "DECLINED", "offsetting": "OFFSETTING"}.get(penalty.status),
                )
            )
        return cards

    def _number(
        self, team: str | None, name: str | None, penalized: set[str], only: bool
    ) -> str | None:
        """The flagged player's number on his team that week: by the ESPN ID ESPN names him by,
        else by the name the text gives him, such as "Ja.Williams" for Jaylon. Unknown when
        neither finds exactly one player."""
        if not name or team not in self.roster:
            return None
        players = self.roster[team]
        by_id = [p for p in players if p[0] is not None and p[0] in penalized]
        by_name = [p for p in players if _same_player(name, p[1])]
        if len(by_id) == 1 and (only or by_id[0] in by_name):
            return by_id[0][2]
        return by_name[0][2] if len(by_name) == 1 else None

    def _try_results(self, facts: PlayFacts, scorer: str | None) -> list[BoardResult]:
        tried = facts.point_after
        if tried is None or tried.good is None:
            return []
        if tried.good:
            return [_result(tried.kind, scorer)]
        if tried.miss == "blocked":
            return [_result("blocked", self.teams.other(scorer))]
        return [_result("no_good", scorer)]

    # --- one play --------------------------------------------------------------------------------

    def boards(
        self, play: LivePlay, facts: PlayFacts, clock_end: str | None = None
    ) -> tuple[PlayBoard, ...]:
        """The board for this play, then its try's when it scored a touchdown with one attached.
        The game then moves past the play: its score, and any timeout it records. `clock_end` is
        the clock when the play ended, where a source gives it: the board runs to it."""
        self._enter(play.period)
        clock_end = clock_end or play.clock_end  # the NFL record's clock at the whistle
        before_scores = dict(self.scores)
        espn = {self.teams.home: _score(play.home_score), self.teams.away: _score(play.away_score)}
        known = all(value is not None for value in espn.values())
        scored = facts.touchdown or facts.safety or bool(play.scoring_play)
        if facts.shape == "field_goal" and facts.kick is not None and facts.kick.result == "good":
            scored = True
        if known and not scored:
            # A play that scores nothing never lowers a score. ESPN puts a try's points on its
            # touchdown, so a flag on the try is recorded with the score before the kick.
            final: dict[str, int | None] = {
                team: value
                if before_scores[team] is None
                else max(value or 0, before_scores[team] or 0)
                for team, value in espn.items()
            }
        elif known:
            final = espn
        elif scored:
            final = dict.fromkeys(espn)
        else:
            final = before_scores

        # A touchdown shows its own six; the try that follows ends at ESPN's score.
        scorer = None
        if facts.touchdown and known:
            rose = [
                team
                for team in espn
                if before_scores[team] is not None
                and (espn[team] or 0) - (before_scores[team] or 0) >= 6
            ]
            scorer = rose[0] if len(rose) == 1 else None
        elif facts.touchdown:
            scorer = facts.defense if facts.turnover else facts.offense
        play_scores = dict(final)
        if facts.touchdown and scorer is not None and before_scores[scorer] is not None and known:
            play_scores = {**before_scores, scorer: (before_scores[scorer] or 0) + 6}

        before = self._state(play, before_scores, rest=self._start(facts))
        tried = facts.touchdown and facts.point_after is not None
        if facts.touchdown:
            after_rest: dict[str, object] = {"possession": scorer}
            if tried and facts.point_after is not None:
                after_rest["situation"] = facts.point_after.kind
        else:
            after_rest = self._end(play.end)
        self._charge(play.text)  # a lost challenge costs its timeout once the play is over
        after = self._state(play, play_scores, clock_end, after_rest)
        made = [
            PlayBoard(
                event_id=play.event_id,
                provider_id=play.provider_id,
                before=before,
                after=after,
                results=tuple(self._results(play, facts, scorer) + self._penalties(play, facts)),
            )
        ]
        if tried:
            made.append(
                PlayBoard(
                    event_id=play.event_id,
                    provider_id=play.provider_id,
                    part="try",
                    before=after,
                    after=self._state(play, final, clock_end, {"possession": scorer}),
                    results=tuple(self._try_results(facts, scorer)),
                )
            )
        self.scores = dict(final)
        return tuple(made)

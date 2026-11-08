"""Ordered football actions and available landmarks before a motion plan is estimated."""

from datetime import datetime
from typing import Literal

from arbit_data.live.contracts import FieldPoint, LiveModel, LivePlay
from arbit_data.live.play_facts import FumbleFacts, PenaltyFacts, PlayFacts, PointAfter, Shape

Confidence = Literal["observed", "derived", "estimated", "unknown"]
ActionKind = Literal[
    "snap",
    "kick",
    "exchange",
    "release",
    "arrival",
    "possession",
    "advance",
    "contact",
    "loose",
    "recovery",
    "out_of_bounds",
    "score",
    "dead",
]


class Evidence[T](LiveModel):
    value: T | None = None
    confidence: Confidence = "unknown"
    field: str | None = None


class ActionPerson(LiveModel):
    key: str
    espn_id: str | None
    source_id: str | None = None
    team_id: str | None = None
    name: str | None = None
    jersey: str | None = None
    roles: tuple[str, ...]


class ActionStep(LiveModel):
    kind: ActionKind
    actor: str | None = None
    actors: tuple[str, ...] = ()
    target: str | None = None
    team_id: str | None = None
    spot: Evidence[int] = Evidence()
    seconds: Evidence[float] = Evidence()
    confidence: Confidence
    field: str


class ActionSequence(LiveModel):
    event_id: str
    play_id: str
    source: Literal["nfl", "espn"]
    shape: Shape
    offense: str | None
    defense: str | None
    people: tuple[ActionPerson, ...]
    steps: tuple[ActionStep, ...]
    duration: Evidence[float]
    air_yards: Evidence[int]
    start: FieldPoint
    next_state: FieldPoint
    clock: str | None
    clock_end: str | None
    review: Literal["upheld", "reversed"] | None
    penalties: tuple[PenaltyFacts, ...]
    point_after: PointAfter | None
    cancelled: bool
    limitations: tuple[str, ...]


def elapsed_seconds(play: LivePlay) -> float | None:
    if not play.snap_at or not play.whistle_at:
        return None
    try:
        start = datetime.fromisoformat(play.snap_at.replace("Z", "+00:00"))
        end = datetime.fromisoformat(play.whistle_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if start.utcoffset() is None or end.utcoffset() is None:
        return None
    seconds = (end - start).total_seconds()
    return seconds if 0 < seconds < 60 else None


def _spot(value: int | None, field: str, confidence: Confidence = "derived") -> Evidence[int]:
    return (
        Evidence(value=value, confidence=confidence, field=field)
        if value is not None
        else Evidence()
    )


def _action_end(facts: PlayFacts) -> Evidence[int]:
    if facts.action_end_source == "description":
        return _spot(facts.action_end, "description.action_end")
    if facts.touchdown and facts.shape in ("pass", "run", "scramble", "interception"):
        return _spot(0 if facts.shape == "interception" else 100, "touchdown_goal_line")
    if (
        facts.shape in ("pass", "run", "scramble", "sack", "kneel")
        and facts.start is not None
        and facts.yards is not None
        and not facts.turnover
        and not any(p.status == "accepted" for p in facts.penalties)
        and -10 <= facts.start + facts.yards <= 110
    ):
        return _spot(facts.start + facts.yards, "start_plus_gain")
    return Evidence()


def _people(play: LivePlay, facts: PlayFacts) -> tuple[ActionPerson, ...]:
    people: dict[str, ActionPerson] = {}
    for person in play.motion_evidence.people if play.motion_evidence else ():
        key = f"espn:{person.espn_id}" if person.espn_id else f"gsis:{person.source_id}"
        if key in people:
            previous = people[key]
            people[key] = previous.model_copy(
                update={
                    "roles": tuple(dict.fromkeys((*previous.roles, *person.roles))),
                    "team_id": previous.team_id if previous.team_id == person.team_id else None,
                    "source_id": None,
                }
            )
            continue
        people[key] = ActionPerson(
            key=key,
            espn_id=person.espn_id,
            source_id=person.source_id,
            team_id=person.team_id,
            name=person.name,
            jersey=person.jersey,
            roles=person.roles,
        )
    for participant in facts.players:
        key = f"espn:{participant.espn_id}"
        existing = people.get(key)
        if existing is None:
            people[key] = ActionPerson(
                key=key, espn_id=participant.espn_id, roles=(participant.role,)
            )
        elif participant.role not in existing.roles:
            people[key] = existing.model_copy(update={"roles": (*existing.roles, participant.role)})
    return tuple(people.values())


class _Steps:
    def __init__(self, people: tuple[ActionPerson, ...]):
        self.people = people
        self.steps: list[ActionStep] = []

    def person(self, *roles: str, team: str | None = None) -> str | None:
        for role in roles:
            matches = [
                p.key
                for p in self.people
                if role in p.roles and (team is None or p.team_id in (None, team))
            ]
            if matches:
                return matches[0] if len(matches) == 1 else None
        return None

    def add(
        self,
        kind: ActionKind,
        *,
        actor: str | None = None,
        actors: tuple[str, ...] = (),
        target: str | None = None,
        team: str | None = None,
        spot: Evidence[int] | None = None,
        field: str = "description",
        confidence: Confidence = "observed",
        seconds: Evidence[float] | None = None,
    ) -> None:
        self.steps.append(
            ActionStep(
                kind=kind,
                actor=actor,
                actors=actors,
                target=target,
                team_id=team,
                spot=spot or Evidence(),
                field=field,
                confidence=confidence,
                seconds=seconds or Evidence(),
            )
        )

    def contact(self, team: str | None, spot: Evidence[int], fumble: FumbleFacts | None) -> None:
        credited = tuple(
            p.key
            for p in self.people
            if {"tackler", "assistedBy", "sackedBy"} & set(p.roles)
            and (team is None or p.team_id in (None, team))
        )
        forcer = self.person("forcedBy", team=team) if fumble else None
        primary = forcer or self.person("tackler", "sackedBy", team=team)
        actors = tuple(dict.fromkeys((*((forcer,) if forcer else ()), *credited)))
        if primary is None and len(actors) == 1:
            primary = actors[0]
        if actors or (fumble and fumble.forced):
            self.add(
                "contact",
                actor=primary,
                actors=actors,
                team=team,
                spot=spot,
                field="credited_contact",
            )

    def loose(self, fumble: FumbleFacts, team: str | None, carrier: str | None) -> None:
        self.add(
            "loose",
            actor=self.person("fumbler", team=team) or carrier,
            team=team,
            spot=_spot(fumble.loose, "description.fumble_spot"),
        )
        if fumble.recovered_by is not None or fumble.spot is not None:
            self.add(
                "recovery",
                actor=self.person("recoverer", team=fumble.recovered_by),
                team=fumble.recovered_by,
                spot=_spot(fumble.spot, "description.recovery_spot"),
            )

    def scrimmage(self, facts: PlayFacts, fumble: FumbleFacts | None) -> None:
        offense, defense = facts.offense, facts.defense
        start = _spot(facts.start, "start." + (facts.spot_source or "spot"))
        end = _action_end(facts)
        passer = self.person("passer", team=offense)
        rusher = self.person("rusher", team=offense)
        carrier = rusher or passer
        offense_carried = facts.shape in ("run", "scramble", "sack", "kneel")
        self.add(
            "snap", actor=passer, team=offense, spot=start, confidence="derived", field="play_kind"
        )
        if facts.passing:
            passing = facts.passing
            target = self.person("intendedReceiver", "receiver", team=offense)
            self.add("release", actor=passer, target=target, team=offense)
            catch = _spot(
                passing.catch_spot,
                "description.interception_spot"
                if passing.result == "intercepted"
                else "gain_minus_yac",
            )
            self.add("arrival", spot=catch, confidence="derived", field="pass_result")
            if passing.result in ("incomplete", "spiked"):
                return
            picked = passing.result == "intercepted"
            team, opponent = (defense, offense) if picked else (offense, defense)
            carrier = (
                self.person("returner", "passDefender", team=team)
                if picked
                else self.person("receiver", "intendedReceiver", team=team)
            )
            self.add("possession", actor=carrier, team=team, spot=catch, field="pass_result")
            if end.value is not None and (end.value != catch.value or passing.yards_after_catch):
                self.add(
                    "advance",
                    actor=carrier,
                    team=team,
                    spot=end,
                    confidence="derived",
                    field="action_end",
                )
            self.contact(opponent, end, fumble)
            if fumble:
                self.loose(fumble, team, carrier)
        elif offense_carried:
            if facts.shape in ("run", "scramble"):
                self.add("advance", actor=carrier, team=offense, spot=end)
            self.contact(defense, end, fumble)
            if fumble:
                self.loose(fumble, offense, carrier)

    def special_teams(self, facts: PlayFacts, fumble: FumbleFacts | None) -> None:
        kick = facts.kick
        assert kick is not None
        offense, defense = facts.offense, facts.defense
        kicker = self.person("kicker", "punter", team=offense)
        if facts.shape != "kickoff":
            self.add(
                "snap",
                team=offense,
                spot=_spot(facts.start, "start.spot"),
                confidence="derived",
                field="play_kind",
            )
        self.add(
            "kick",
            actor=kicker,
            team=offense,
            spot=_spot(facts.start, "start.spot") if facts.shape == "kickoff" else None,
        )
        if facts.shape in ("field_goal", "extra_point"):
            return
        landing = _spot(kick.landing, "description.kick_landing")
        self.add("arrival", spot=landing, confidence="derived", field="kick_result")
        returner = self.person("returner", team=defense)
        returned = kick.result == "returned" or kick.return_yards is not None
        if returned or kick.result == "fair_catch":
            self.add("possession", actor=returner, team=defense, spot=landing, field="kick_result")
        if returned:
            end = _spot(kick.return_spot, "description.return_spot")
            if end.value is None and kick.landing is not None and kick.return_yards is not None:
                end = _spot(kick.landing - kick.return_yards, "kick_landing_minus_return_yards")
            self.add("advance", actor=returner, team=defense, spot=end, field="kick_return")
            self.contact(offense, end, fumble)
        if fumble:
            self.loose(fumble, defense if returned else None, returner if returned else None)


def sequence(play: LivePlay, facts: PlayFacts) -> ActionSequence:
    """Keep known action order and participants independent from generated timing and official next state."""
    people = _people(play, facts)
    timeline = _Steps(people)
    elapsed = elapsed_seconds(play)
    duration: Evidence[float] = (
        Evidence(value=elapsed, confidence="derived", field="playEndTime-playStartTime")
        if elapsed is not None
        else Evidence()
    )
    limitations = list(facts.missing)
    if facts.reason:
        limitations.append(facts.reason)
    if not play.cancelled and facts.reason not in ("no_play", "not_a_play", "aborted"):
        base = facts.before if facts.shape == "fumble" and facts.before is not None else facts
        if base.kick:
            timeline.special_teams(base, facts.fumble)
        elif base.passing or base.shape in ("run", "scramble", "sack", "kneel"):
            timeline.scrimmage(base, facts.fumble)
        if timeline.steps:
            possession = next(
                (
                    s
                    for s in reversed(timeline.steps)
                    if s.kind in ("possession", "recovery", "advance")
                ),
                None,
            )
            if facts.out_of_bounds:
                timeline.add("out_of_bounds", spot=_action_end(facts))
            if facts.touchdown or facts.safety or (facts.kick and facts.kick.result == "good"):
                timeline.add(
                    "score",
                    actor=timeline.person("scorer"),
                    team=possession.team_id if possession and facts.touchdown else None,
                    field="scoring_result",
                )
            timeline.add("dead", confidence="derived", field="play_result", seconds=duration)
    motion = play.motion_evidence
    air = (
        _spot(motion.air_yards, f"stats.{motion.air_stat_type}.yards", "observed")
        if motion and motion.air_stat_type
        else _spot(facts.passing.air_yards if facts.passing else None, "pass_spot_minus_start")
    )
    return ActionSequence(
        event_id=play.event_id,
        play_id=play.provider_id,
        source=play.source or "espn",
        shape=facts.shape,
        offense=facts.offense,
        defense=facts.defense,
        people=people,
        steps=tuple(timeline.steps),
        duration=duration,
        air_yards=air,
        start=play.start,
        next_state=play.end,
        clock=play.clock,
        clock_end=play.clock_end,
        review=facts.review,
        penalties=facts.penalties,
        point_after=facts.point_after,
        cancelled=play.cancelled,
        limitations=tuple(dict.fromkeys(limitations)),
    )

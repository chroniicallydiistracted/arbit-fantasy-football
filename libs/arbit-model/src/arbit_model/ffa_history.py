"""FFA league ownership and availability at any moment of the 2026 season, for research.

2026 is FFA's inaugural season (OWN-076): its league history starts with the 2026 draft. Earlier
NFL seasons are studied with the league's scoring rules, but no FFA rosters exist for them.

**Ownership** is rebuilt by replaying the draft (the league document's picks) and every executed
add and drop (free-agent, waiver and roster moves) in time order. ESPN returns current ownership
even for historical periods, so current rosters are never used as history. The replay is checked
against ESPN's own roster for every finished scoring period: the weekly lineups Arbit captures,
reconciled to the official matchup totals. A period whose replay doesn't match its capture is not
trusted.

**Effective time** of a move:
- a waiver claim takes effect when it is processed;
- free-agent adds and roster drops take effect when they are made (ESPN gives no separate
  processing time for them).

**Availability** of a player on no roster at time T, with the league's waiver hold (24 hours,
`rule_version.waiver_hours`):
- `WAIVERS`: dropped less than the hold before T, so only a waiver claim can get him;
- `WAIVERS_OR_FREE_AGENT`: dropped between one and two holds before T. Claims process on
  scheduled days, so he may still be on waivers. Treated as not immediately claimable;
- `FREE_AGENT`: otherwise. A free agent can be added until his own game locks (INDIVIDUAL_GAME).

**Classes:**
- `VERIFIED`: matches a captured period roster or an archived snapshot at that moment;
- `RECONSTRUCTED`: replayed between verified states;
- `UNKNOWN`: a replay inconsistency, or no verified state to anchor it.

Pure functions: no database or network access here.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

EXECUTED = "EXECUTED"
MOVE_TYPES = frozenset({"FREEAGENT", "WAIVER", "ROSTER"})
FREE_AGENT = "FREE_AGENT"
WAIVERS = "WAIVERS"
UNCERTAIN = "WAIVERS_OR_FREE_AGENT"


@dataclass(frozen=True)
class Move:
    when: datetime
    period: int
    kind: str  # ADD or DROP
    player: str
    from_team: str | None
    to_team: str | None
    transaction: str
    transaction_type: str


def moves(transactions: Iterable[Mapping[str, Any]]) -> list[Move]:
    """Executed adds and drops in effective-time order (a drop before an add at the same time).

    Proposals, declines, cancellations and failed waiver claims change no roster and are left
    out; lineup-slot changes don't change ownership. Raises on an executed move without a time."""
    out = []
    for t in transactions:
        if t["status"] != EXECUTED or t["type"] not in MOVE_TYPES:
            continue
        when = t.get("processed_at") or t.get("proposed_at")
        if when is None:
            raise ValueError(f"executed transaction {t['espn_id']} has no time")
        for item in t["items"]:
            if item["type"] not in ("ADD", "DROP"):
                continue
            out.append(
                Move(
                    when=when,
                    period=int(t["scoring_period"]),
                    kind=item["type"],
                    player=str(item["player_id"]),
                    from_team=item.get("from_team_id"),
                    to_team=item.get("to_team_id"),
                    transaction=str(t["espn_id"]),
                    transaction_type=str(t["type"]),
                )
            )
    return sorted(out, key=lambda m: (m.when, 0 if m.kind == "DROP" else 1, m.transaction))


@dataclass
class Replay:
    owners: dict[str, str]  # player -> team
    problems: list[str]
    applied: int


def replay(
    draft: Iterable[tuple[str, str]],
    all_moves: Sequence[Move],
    *,
    until: datetime | None = None,
    through_period: int | None = None,
) -> Replay:
    """Owners after the draft and every move effective by `until` (inclusive) or assigned to a
    scoring period up to `through_period`. A drop of a player the team doesn't hold, or an add of
    a player someone holds, is recorded as a problem: the log disagrees with itself."""
    owners = {player: team for player, team in draft}
    problems: list[str] = []
    applied = 0
    for move in all_moves:
        if until is not None and move.when > until:
            continue
        if through_period is not None and move.period > through_period:
            continue
        applied += 1
        if move.kind == "ADD":
            if move.player in owners:
                problems.append(f"{move.transaction}: add of a held player")
            if move.to_team is None:
                problems.append(f"{move.transaction}: add without a team")
                continue
            owners[move.player] = move.to_team
        else:
            if owners.get(move.player) != move.from_team:
                problems.append(f"{move.transaction}: drop of a player the team didn't hold")
            owners.pop(move.player, None)
    return Replay(owners, problems, applied)


def verify_periods(
    draft: Sequence[tuple[str, str]],
    all_moves: Sequence[Move],
    captured: Mapping[int, set[tuple[str, str]]],
) -> dict[int, dict[str, Any]]:
    """Per captured period: the replay through that period against ESPN's roster for it."""
    out = {}
    for period, roster in sorted(captured.items()):
        rebuilt = replay(draft, all_moves, through_period=period)
        state = set(rebuilt.owners.items())
        out[period] = {
            "captured": len(roster),
            "reconstructed": len(state),
            "matched": len(roster & state),
            "missingFromReplay": len(roster - state),
            "extraInReplay": len(state - roster),
            "replayProblems": len(rebuilt.problems),
            "verified": roster == state and not rebuilt.problems,
        }
    return out


def availability(
    universe: Iterable[str],
    owners: Mapping[str, str],
    all_moves: Sequence[Move],
    when: datetime,
    hold: timedelta,
) -> dict[str, str]:
    """Each player's state at `when`: `OWNED:<team>`, `WAIVERS`, `WAIVERS_OR_FREE_AGENT` or
    `FREE_AGENT` (see the module notes). `owners` must be the replay at `when`."""
    last_drop: dict[str, datetime] = {}
    for move in all_moves:
        if move.kind == "DROP" and move.when <= when:
            last_drop[move.player] = move.when
    out = {}
    for player in universe:
        if player in owners:
            out[player] = f"OWNED:{owners[player]}"
            continue
        dropped = last_drop.get(player)
        if dropped is not None and when - dropped < hold:
            out[player] = WAIVERS
        elif dropped is not None and when - dropped < 2 * hold:
            out[player] = UNCERTAIN
        else:
            out[player] = FREE_AGENT
    return out


def snapshot_agreement(
    replayed: Mapping[str, str], snapshot: Mapping[str, str], players: Iterable[str]
) -> dict[str, int]:
    """How a replay at a snapshot's time agrees with the snapshot's owners for some players
    (`snapshot` maps owned players to teams; a player absent from it is unowned there)."""
    agree = disagree = 0
    for player in players:
        if replayed.get(player) == snapshot.get(player):
            agree += 1
        else:
            disagree += 1
    return {"agree": agree, "disagree": disagree}

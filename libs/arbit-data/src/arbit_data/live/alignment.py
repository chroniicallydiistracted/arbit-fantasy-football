"""Where each drawn player lines up, and his first move after the snap, by his position (OWN-036).

Positions are each team's 2026 depth chart slots (nflverse, sourced from ESPN), matched by ESPN ID:
1,003 of the 1,009 players ESPN names in the captured plays have one. A 3-4 defense's outside
linebackers rush off the edge, so its WLB and SLB become WOLB and SOLB here; a 4-3's stay off the
ball. The roster's depth chart position fills in for a player missing from the depth charts.

The spot is the team's base alignment, not that play's real one, which no live source has
([research](../../../../../docs/research/play-alignment-sources-2026-11-04.md)). Context from the
play moves it where the play says: a defensive back who makes the play lines up on its side, and
over the drawn receiver he covers. Frame as in ENG-034: x toward the defense, z from the near
sideline. The offense's left is the near side, so the defense's left (LDE, LCB) is the far side.
The tight end, and so the strong side, is on the offense's right unless the play puts him left.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

Group = Literal["OL", "TE", "WR", "RB", "FB", "QB", "DL", "EDGE", "LB", "CB", "NB", "S", "ST"]

GROUPS: dict[str, Group] = {
    **dict.fromkeys(("LT", "LG", "C", "RG", "RT", "T", "G", "OL"), "OL"),
    "TE": "TE",
    "WR": "WR",
    **dict.fromkeys(("RB", "HB"), "RB"),
    "FB": "FB",
    "QB": "QB",
    **dict.fromkeys(("LDE", "RDE", "DE", "LDT", "RDT", "DT", "NT", "DL"), "DL"),
    **dict.fromkeys(("WOLB", "SOLB"), "EDGE"),
    **dict.fromkeys(("WLB", "SLB", "MLB", "LILB", "RILB", "ILB", "OLB", "LB"), "LB"),
    **dict.fromkeys(("LCB", "RCB", "CB"), "CB"),
    **dict.fromkeys(("NB", "DB"), "NB"),
    **dict.fromkeys(("FS", "SS", "S"), "S"),
    **dict.fromkeys(("PK", "K", "P", "LS", "H", "KR", "PR"), "ST"),
}
DEFENSE: frozenset[Group] = frozenset({"DL", "EDGE", "LB", "CB", "NB", "S"})
# Kick coverage: the fast players are the gunners, wide on the line; everyone else is inside.
GUNNERS: frozenset[Group] = frozenset({"CB", "NB", "S", "WR"})

# Yards past the line (toward the defense) and across from the ball. +across is the offense's
# right. "side" means the play decides the sign for a position without one.
_FIXED: dict[str, tuple[float, float]] = {
    "LT": (-0.7, -2.8),
    "LG": (-0.6, -1.4),
    "C": (-0.5, 0.0),
    "RG": (-0.6, 1.4),
    "RT": (-0.7, 2.8),
    "FB": (-4.5, 0.0),
    "LDE": (1.0, 3.9),
    "RDE": (1.0, -3.9),
    "LDT": (1.0, 1.0),
    "RDT": (1.0, -1.0),
    "NT": (1.0, 0.0),
    "LILB": (4.5, 1.8),
    "RILB": (4.5, -1.8),
    "MLB": (4.5, 0.0),
    "LCB": (6.0, 14.0),
    "RCB": (6.0, -14.0),
}
_SIDED: dict[str, tuple[float, float]] = {  # across is a size; the play picks the side
    "T": (-0.7, 2.8),
    "G": (-0.6, 1.4),
    "OL": (-0.6, 1.4),
    "DE": (1.0, 3.9),
    "DT": (1.0, 1.0),
    "DL": (1.0, 1.0),
    "ILB": (4.5, 1.8),
    "OLB": (4.5, 4.0),
    "LB": (4.5, 1.8),
    "CB": (6.0, 14.0),
    "NB": (5.0, 8.0),
    "DB": (5.0, 8.0),
    "S": (11.0, 3.0),
    "WR": (-0.5, 14.0),
}


@dataclass(frozen=True)
class Context:
    """What the play says about where things are. `side` is where the play goes: -1 the offense's
    left, +1 its right, 0 the middle or not said."""

    los: float
    ball_z: float
    shotgun: bool
    kind: Literal["pass", "run", "kick", "other"]
    side: int = 0
    strong: int = 1


def group(code: str | None) -> Group | None:
    return GROUPS.get(code or "")


def pick(codes: tuple[str, ...], side: str) -> str | None:
    """His position on this side of the ball: a two-way player such as a corner who also plays
    receiver has both. None when he has none there, such as a safety on the punt team."""
    for code in codes:
        kind = group(code)
        if kind is not None and kind != "ST" and (kind in DEFENSE) == (side == "defense"):
            return code
    return None


def spot(
    code: str, ctx: Context, toward: float | None = None, chance: float = 0.5
) -> tuple[float, float] | None:
    """Where a player at this position stands at the snap, or None for a kick specialist, whose
    spot the kick unit sets. `toward` is the across-the-field spot of the play he makes, which
    puts a defensive back or a player without a set side on that side. `chance` (0 to 1) picks
    among equal choices and comes from the play's seeded draws."""
    kind = group(code)
    if kind is None or kind == "ST":
        return None
    play_side = ctx.side
    if toward is not None and abs(toward - ctx.ball_z) > 1.0:
        play_side = 1 if toward > ctx.ball_z else -1
    either = play_side or (1 if chance >= 0.5 else -1)
    if code == "QB":
        return ctx.los - (5.0 if ctx.shotgun else 1.0), ctx.ball_z
    if kind == "RB":
        if ctx.shotgun:
            return ctx.los - 5.0, ctx.ball_z + 1.5 * either
        return ctx.los - 7.0, ctx.ball_z
    if code == "TE":
        return ctx.los - 0.7, ctx.ball_z + 4.2 * ctx.strong
    if code in ("WOLB", "SOLB"):
        sign = -ctx.strong if code == "WOLB" else ctx.strong
        return ctx.los + 1.0, ctx.ball_z + 5.5 * sign
    if code in ("WLB", "SLB"):
        sign = -ctx.strong if code == "WLB" else ctx.strong
        return ctx.los + 4.5, ctx.ball_z + 3.8 * sign
    if code == "SS":
        return ctx.los + 8.0, ctx.ball_z + 4.0 * (play_side or ctx.strong)
    if code == "FS":
        return ctx.los + 13.0, ctx.ball_z + 2.0 * (play_side or -ctx.strong)
    if kind in ("CB", "NB") and code in ("LCB", "RCB") and play_side:
        # The corner who makes the play was the one on its side.
        return ctx.los + 6.0, ctx.ball_z + 14.0 * play_side
    if code in _FIXED:
        dx, dz = _FIXED[code]
        return ctx.los + dx, ctx.ball_z + dz
    if code in _SIDED:
        dx, dz = _SIDED[code]
        return ctx.los + dx, ctx.ball_z + dz * either
    return None


Read = tuple[str, float, float, float, str | None]  # pose, seconds, x, z, facing


def read(code: str, ctx: Context, at: tuple[float, float], defense: bool) -> Read | None:
    """His first move after the snap for this kind of play, before he goes to the ball: a
    lineman rushes the passer or takes on a block, a linebacker or defensive back drops into
    coverage, a receiver releases into his route. None: he reads the play where he stands."""
    kind = group(code)
    x, z = at
    if kind is None or kind == "ST":
        return None
    passing = ctx.kind == "pass"
    if defense:
        if kind in ("DL", "EDGE"):
            if passing:  # the rush: up the field and in toward where the quarterback sets
                return "RUN", 0.0, ctx.los - 2.5, z + (ctx.ball_z - z) * 0.4, "left"
            if ctx.kind == "run":  # takes on the block at the line and sheds it
                return "drive", 0.3, x - 0.3, z, "left"
            return None
        if kind in ("LB", "CB", "NB", "S") and passing:
            depth = {"LB": 4.0, "CB": 4.5, "NB": 4.0, "S": 3.0}[kind]
            return "DROP", depth / 4.4, x + depth, z, "left"  # backpedal into coverage
        return None
    if kind in ("OL", "TE") and passing:
        return "DROP", 0.45, x - 1.2, z, "right"  # pass set
    if kind in ("OL", "TE") and ctx.kind == "run":
        return "drive", 0.45, x + 0.6, z, "right"  # drive block
    if kind in ("WR",) and passing:
        return "RUN", 0.0, ctx.los + 8.0, z, "right"  # releases into his route
    return None


def coverage_spot(
    code: str | None, los: float, ball_z: float, line: float, chance: float
) -> tuple[float, float]:
    """Where a kick coverage player lines up on `line`: gunners wide, everyone else inside."""
    kind = group(code)
    side = 1 if chance >= 0.5 else -1
    if kind in GUNNERS:
        return line, ball_z + side * (10.0 + 6.0 * abs(chance - 0.5) * 2)
    return line, ball_z + side * (1.5 + 5.0 * abs(chance - 0.5) * 2)


# Loading positions ---------------------------------------------------------------------------


_DEPTH_RENAMES = {("Base 3-4 D", "WLB"): "WOLB", ("Base 3-4 D", "SLB"): "SOLB"}
_ROSTER = {"K": "PK", "OLB": "OLB", "ILB": "ILB", "DB": "DB", "LB": "LB", "S": "S"}


def from_depth_charts(
    rows: Iterable[Mapping[str, Any]], before: str | None = None
) -> dict[str, tuple[str, ...]]:
    """ESPN ID to position codes from nflverse depth chart rows (`dt`, `team`, `espn_id`,
    `pos_grp`, `pos_abb`, `pos_rank`), best first: offense and defense slots by rank, then
    special teams. Each team's latest snapshot taken before `before` (an ISO time) is used."""
    latest: dict[str, str] = {}
    kept = [r for r in rows if r.get("espn_id") and (before is None or str(r["dt"]) < before)]
    for row in kept:
        team = str(row["team"])
        latest[team] = max(latest.get(team, ""), str(row["dt"]))
    slots: dict[str, list[tuple[int, int, str]]] = {}
    for row in kept:
        if str(row["dt"]) != latest[str(row["team"])]:
            continue
        code = _DEPTH_RENAMES.get((str(row["pos_grp"]), str(row["pos_abb"])), str(row["pos_abb"]))
        special = 1 if row["pos_grp"] == "Special Teams" else 0
        slots.setdefault(str(row["espn_id"]), []).append(
            (special, int(row.get("pos_rank") or 99), code)
        )
    return {
        key: tuple(dict.fromkeys(code for *_, code in sorted(found)))
        for key, found in slots.items()
    }


def from_rosters(rows: Iterable[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    """ESPN ID to position code from nflverse roster rows, by `depth_chart_position`."""
    found: dict[str, tuple[str, ...]] = {}
    for row in rows:
        espn_id, code = row.get("espn_id"), row.get("depth_chart_position")
        if espn_id and code:
            found[str(espn_id)] = (_ROSTER.get(str(code), str(code)),)
    return found

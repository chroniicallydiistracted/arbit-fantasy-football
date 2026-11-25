"""Synthetic FFA-like seasons with a known defensive signal (owner final directive AUD-06).

config/dvp/simulation-v1.json declares the data-generating process. The generator returns data in
the real observation and schedule schemas, so Arbit's own estimators run on it unchanged, plus the
truth: each studied unit's trait, the true k and the oracle conditional mean. The oracle is a
research reference, never an eligible input.

points = mu + a(side, season) + d(studied unit, season, week) + e_nontd + e_td, with
k_true = var(e) / var(d) per game. For QB to K the studied unit is the defense and the scoring side
the offense; for D/ST the studied unit is the offense and the scoring side the D/ST.

Pure functions; randomness only from the generator passed in.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

MEANS = {"QB": 18.0, "RB": 22.0, "WR": 30.0, "TE": 9.0, "K": 8.0, "DST": 6.0}
NOISE = {"QB": 7.0, "RB": 8.0, "WR": 10.0, "TE": 6.0, "K": 4.0, "DST": 6.0}
SIDE = {"QB": 3.0, "RB": 3.0, "WR": 4.0, "TE": 2.0, "K": 1.5, "DST": 1.5}
TD_SHARE = 0.4  # share of the noise variance in touchdowns (no defensive signal there)
INVALID = "invalid_refused_line"


@dataclass(frozen=True)
class Scenario:
    """One data-generating process (simulation-v1.json `scenarios`)."""

    id: str
    k_true: float = math.inf
    persistence: float = 0.5
    abrupt_week: int | None = None
    drift: float | None = None
    exposure_loss: int = 0
    mcar: float = 0.0
    mnar: float = 0.0
    game_shock: float = 0.0
    week_shock: float = 0.0
    heavy_tails: bool = False
    tiers: bool = False
    channel: str = "points"  # points | volume | efficiency
    positions: tuple[str, ...] = ("WR", "DST")
    teams: int = 32
    weeks: int = 17
    seasons: tuple[int, ...] = tuple(range(2016, 2026))
    extra: dict[str, Any] = field(default_factory=dict)

    def trait_sd(self, position: str) -> float:
        return 0.0 if math.isinf(self.k_true) else NOISE[position] / math.sqrt(self.k_true)


SCENARIOS = {
    "SIM-01": Scenario("SIM-01"),
    "SIM-02": Scenario("SIM-02", k_true=60),
    "SIM-03": Scenario("SIM-03", k_true=20),
    "SIM-04": Scenario("SIM-04", k_true=8),
    "SIM-05": Scenario("SIM-05", k_true=8, abrupt_week=9),
    "SIM-06": Scenario("SIM-06", k_true=8, drift=0.85),
    "SIM-07": Scenario("SIM-07", k_true=20, exposure_loss=6),
    "SIM-08": Scenario("SIM-08", k_true=20, mcar=0.15),
    "SIM-09": Scenario("SIM-09", k_true=20, mnar=0.5),
    "SIM-10": Scenario("SIM-10", k_true=20, game_shock=0.4, week_shock=0.3),
    "SIM-11": Scenario("SIM-11", k_true=20, heavy_tails=True),
    "SIM-12": Scenario("SIM-12", k_true=20, tiers=True),
    "SIM-13a": Scenario("SIM-13a", k_true=8, persistence=0.0),
    "SIM-13b": Scenario("SIM-13b", k_true=8, persistence=0.9),
    "SIM-14a": Scenario("SIM-14a", k_true=8, channel="volume"),
    "SIM-14b": Scenario("SIM-14b", k_true=8, channel="efficiency"),
    "SIM-16": Scenario("SIM-16", positions=("QB", "RB", "WR", "TE", "K", "DST")),
}


@dataclass
class Synthetic:
    observations: pl.DataFrame  # the real observation schema (valid and invalid cells)
    schedule: pl.DataFrame  # game_id, season, week, kickoff, home, away
    volumes: pl.DataFrame  # game_id, offense, position, volume (the opportunity hook's table)
    oracle: pl.DataFrame  # game_id, offense, position, oracle (true conditional mean)
    truth: dict[str, Any]


def _ar1(rng: np.random.Generator, seasons: int, units: int, sd: float, rho: float) -> np.ndarray:
    """Season-by-unit values following an AR(1) across seasons with stationary sd."""
    out = np.zeros((seasons, units))
    if sd == 0:
        return out
    out[0] = rng.normal(0, sd, units)
    for s in range(1, seasons):
        out[s] = rho * out[s - 1] + math.sqrt(1 - rho**2) * rng.normal(0, sd, units)
    return out


def _noise(rng: np.random.Generator, size: int, sd: float, heavy: bool) -> np.ndarray:
    if not heavy:
        return rng.normal(0, sd, size)
    return rng.standard_t(3, size) * sd / math.sqrt(3.0)  # t(3) has variance 3


def _pairings(
    rng: np.random.Generator, teams: int, tiers: np.ndarray | None
) -> list[tuple[int, int]]:
    if tiers is not None and rng.random() < 0.6:
        games = []
        for tier in np.unique(tiers):
            members = rng.permutation(np.flatnonzero(tiers == tier))
            games += [
                (int(members[2 * i]), int(members[2 * i + 1])) for i in range(len(members) // 2)
            ]
        return games
    order = rng.permutation(teams)
    return [(int(order[2 * i]), int(order[2 * i + 1])) for i in range(teams // 2)]


def generate(sc: Scenario, rng: np.random.Generator) -> Synthetic:
    """One league history under the scenario. See the module notes and simulation-v1.json."""
    teams = [f"T{i:02d}" for i in range(sc.teams)]
    n_seasons = len(sc.seasons)
    side = {p: _ar1(rng, n_seasons, sc.teams, SIDE[p], sc.persistence) for p in sc.positions}
    trait = {
        p: _ar1(rng, n_seasons, sc.teams, sc.trait_sd(p), sc.persistence) for p in sc.positions
    }
    second = {
        p: _ar1(rng, n_seasons, sc.teams, sc.trait_sd(p), sc.persistence) for p in sc.positions
    }
    rows: list[dict[str, Any]] = []
    games: list[dict[str, Any]] = []
    vol: list[dict[str, Any]] = []
    orc: list[dict[str, Any]] = []
    for si, season in enumerate(sc.seasons):
        strength = np.mean([side[p][si] for p in sc.positions], axis=0)
        tiers = (
            np.digitize(strength, np.quantile(strength, [0.25, 0.5, 0.75])) if sc.tiers else None
        )
        lost: dict[tuple[str, int], set[int]] = {}
        if sc.exposure_loss:
            for p in sc.positions:
                for t in range(sc.teams):
                    count = int(rng.integers(0, sc.exposure_loss + 1))
                    lost[(p, t)] = set(rng.choice(sc.weeks, count, replace=False).tolist())
        week_trait = {p: trait[p][si].copy() for p in sc.positions}
        thursday = datetime(season, 9, 11, tzinfo=UTC)
        for week in range(1, sc.weeks + 1):
            for p in sc.positions:
                if sc.drift is not None and week > 1:
                    week_trait[p] = sc.drift * week_trait[p] + math.sqrt(
                        1 - sc.drift**2
                    ) * rng.normal(0, sc.trait_sd(p), sc.teams)
                if sc.abrupt_week is not None and week == sc.abrupt_week:
                    week_trait[p] = second[p][si].copy()
            week_shock = rng.normal()
            for g, (h, a) in enumerate(_pairings(rng, sc.teams, tiers)):
                base = thursday + timedelta(days=7 * (week - 1))
                kickoff = base if g == 0 else base + timedelta(days=3, hours=17)
                game_id = f"{season}_{week:02d}_{teams[a]}_{teams[h]}"
                available = datetime(
                    kickoff.year, kickoff.month, kickoff.day, 12, tzinfo=UTC
                ) + timedelta(days=1)
                games.append(
                    {
                        "game_id": game_id,
                        "season": season,
                        "week": week,
                        "kickoff": kickoff,
                        "home": teams[h],
                        "away": teams[a],
                    }
                )
                game_shock = rng.normal()
                for off, de in ((h, a), (a, h)):
                    for p in sc.positions:
                        dst = p == "DST"
                        scoring, studied = (de, off) if dst else (off, de)
                        sd = NOISE[p]
                        mu, a_side, d = MEANS[p], side[p][si][scoring], week_trait[p][studied]
                        v_mean = mu / 1.5
                        rate = mu / v_mean
                        shared = sd * (sc.game_shock * game_shock + sc.week_shock * week_shock)
                        if sc.channel == "volume":
                            e_v = rng.normal(0, 0.25 * v_mean)
                            volume = max(1.0, v_mean + d / rate + e_v)
                            rest = math.sqrt(max(sd**2 - (0.25 * mu) ** 2, 1.0))
                            e_td = float(
                                _noise(rng, 1, rest * math.sqrt(TD_SHARE), sc.heavy_tails)[0]
                            )
                            e_nt = float(
                                _noise(rng, 1, rest * math.sqrt(1 - TD_SHARE), sc.heavy_tails)[0]
                            )
                            points = volume * rate + a_side + e_nt + e_td + shared
                        elif sc.channel == "efficiency":
                            volume = max(1.0, v_mean + rng.normal(0, 0.25 * v_mean))
                            rest = math.sqrt(max(sd**2 - (0.25 * mu) ** 2, 1.0))
                            e_td = float(
                                _noise(rng, 1, rest * math.sqrt(TD_SHARE), sc.heavy_tails)[0]
                            )
                            e_nt = float(
                                _noise(rng, 1, rest * math.sqrt(1 - TD_SHARE), sc.heavy_tails)[0]
                            )
                            points = volume * (rate + d / v_mean) + a_side + e_nt + e_td + shared
                        else:
                            volume = max(1.0, v_mean + rng.normal(0, 0.25 * v_mean))
                            e_td = float(
                                _noise(rng, 1, sd * math.sqrt(TD_SHARE), sc.heavy_tails)[0]
                            )
                            e_nt = float(
                                _noise(rng, 1, sd * math.sqrt(1 - TD_SHARE), sc.heavy_tails)[0]
                            )
                            points = mu + a_side + d + e_nt + e_td + shared
                        status = "valid"
                        if sc.mcar and rng.random() < sc.mcar:
                            status = INVALID
                        if sc.mnar and (e_nt + e_td) > sd and rng.random() < sc.mnar:
                            status = INVALID
                        if week - 1 in lost.get((p, studied), set()):
                            status = INVALID
                        rows.append(
                            {
                                "game_id": game_id,
                                "season": season,
                                "week": week,
                                "kickoff": kickoff,
                                "available_at": available,
                                "position": p,
                                "offense": teams[off],
                                "defense": teams[de],
                                "unit": teams[studied],
                                "points": float(points),
                                "nontd": float(points - e_td),
                                "status": status,
                                "source_type": "FFA_ACTUAL_FINAL",
                                "observed_or_generated": "observed",
                            }
                        )
                        vol.append(
                            {
                                "game_id": game_id,
                                "offense": teams[off],
                                "position": p,
                                "volume": float(volume),
                            }
                        )
                        orc.append(
                            {
                                "game_id": game_id,
                                "offense": teams[off],
                                "position": p,
                                "oracle": float(mu + a_side + d),
                            }
                        )
    truth = {
        "kTrue": sc.k_true,
        "traitSd": {p: sc.trait_sd(p) for p in sc.positions},
        "noiseSd": {p: NOISE[p] for p in sc.positions},
        "traitVarianceDrawn": {
            p: float(np.var(trait[p][1:8])) for p in sc.positions
        },  # development seasons' drawn traits
        "persistence": sc.persistence,
    }
    return Synthetic(
        observations=pl.DataFrame(rows),
        schedule=pl.DataFrame(games),
        volumes=pl.DataFrame(vol),
        oracle=pl.DataFrame(orc),
        truth=truth,
    )


def known_difference(signal_sd: float, noise_sd: float, c: float) -> float:
    """The exact population RMSE of forecast A = 0 minus forecast B = c * s for y = s + e
    (experiment U): sqrt(var s + var e) - sqrt((1 - c)^2 var s + var e). Positive when B is
    better; walkforward.metrics reports B minus A, the negative of this."""
    a = math.sqrt(signal_sd**2 + noise_sd**2)
    b = math.sqrt((1 - c) ** 2 * signal_sd**2 + noise_sd**2)
    return a - b

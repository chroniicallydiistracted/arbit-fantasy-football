# Task: Weather intelligence for sit/start and the Model (ADR-008)

Status: planned 2026-11-22 under owner decision OWN-069. Not started; no weather data is read yet.

- **Requirement IDs:** MD-002, MD-004 (point-in-time, backtests), LN-002 and LN-003 (matchups and reasons in sit/start), DATA-008 (supervised sources).
- **Decisions:** [ADR-008](../../architecture/decisions/008-weather-intelligence.md), [ADR-007](../../architecture/decisions/007-model-availability.md) with A1–A4, OWN-068 (contributions in explanations).
- **Research:** [weather sources](../../research/weather-sources-2026-11-22.md), SRC-34 to SRC-38.
- **Order:** W1 runs beside M3 slice 3. W5's effect study feeds slice 4. W6 lands with M4 sit/start (OWN-068).

## Slices

| Slice | Outcome | Gate |
| --- | --- | --- |
| **W1 Venues and the forecast record** | Committed venue table: every 2026 stadium plus international and neutral sites, with coordinates, elevation, roof type (dome, fixed, retractable, open), surface and field orientation, each with a source. Join from nflverse `stadium_id` and ESPN venue. Point-in-time forecast record contract and storage: Parquet plus manifests, like the availability captures | Every 2026 game maps to one venue. Orientation is checked against imagery for at least the open-air venues. A test changes a record after its fetch time and requires an identical feature |
| **W2 Open-Meteo capture lane** | Worker lane on ADR-008's lead-time schedule for every upcoming non-dome game. Multi-model forecast plus ensemble; freshness entry; raw captures; catch-up for missed leads (the forecast can't be re-read once a lead passes, so it is recorded as missing) | Week 12 captured at every lead from day 7 to kickoff. Call count recorded against the 10,000-a-day limit |
| **W3 NWS and NBM** | NWS hourly gridpoint forecast and alerts, with the owner's User-Agent contact from `.env.local`; NBM station text bulletins or GRIB point values from NOMADS, archive from AWS | Real captures for one slate. Alert handling shown on an observed alert. Agreement report against Open-Meteo |
| **W4 RRFS and ECMWF/AIFS** | RRFS point values inside 84 hours, and ECMWF IFS and AIFS from day 10, read by index byte ranges or point APIs. One GRIB dependency | Real captures; disagreement measure between models per game |
| **W5 History and effects** | Observed weather per past game from GHCNh (nearest station by venue) and Meteostat, checked against nflverse `temp`/`wind`. Point-in-time forecasts for 2024–2026 from Open-Meteo Previous Runs and the NBM archive. Effect study: wind, gusts, precipitation, snow and temperature against passing volume and efficiency, field goals by distance, and each position's FFA points | Effects reported with intervals by position. Observation-only seasons labeled. No observed value used as a pregame feature |
| **W6 Into projections and sit/start** | Weather feature group in the simulator (slice 4). Retractable roofs as a mixture. Contribution shown in sit/start with forecast age and model disagreement. Attribution shown where weather appears | Ablation from 2024 on reported, Baseline A with and without weather. Explanation reviewed on real games |

## Interfaces

- **`arbit_data.weather`:**
  - venue table reader;
  - forecast record contract;
  - one reader per source, each returning records with model, run time, fetch time, lead and valid hour;
  - a point-in-time reader `forecast_as_of(game, decision_time)` that applies ADR-007.
- **Worker:** one `weather` lane that schedules by game and lead; each source has its own freshness name.
- **Model:** a feature group `weather` with the uncertainty from ensemble spread and disagreement between models; outputs per-game expected conditions and their contribution.

## Exclusions and risks

- **Exclusions:** no paid tiers, no commercial use, and no provider's fantasy data.
- **Missed leads stay missing (A4):** a forecast lead missed while the PC was asleep can only be filled from archives, which hold fewer models. The capture lane is one more reason for the remote 24/7 worker (OWN-070).
- **Retractable-roof decisions** aren't published pre-game in any chosen source. Their probability comes from history and is labeled.
- **Owner input needed:** the NWS User-Agent contact.

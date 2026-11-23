# ADR-008: Weather intelligence for games outside a closed roof

Status: Accepted · 2026-11-22 · owner direction OWN-069. Narrows [ADR-006](006-model-architecture.md)'s nflverse-only inputs for weather, as OWN-063 did for availability. Follows [ADR-007](007-model-availability.md)'s timing rules. Research: [weather sources](../../research/weather-sources-2026-11-22.md).

## Context

The owner lists weather among the reasons a player projects higher or lower in a sit/start call (OWN-068). nflverse records `temp` and `wind` only after a game (R-063), so no forecast exists in the Model's data. The owner decided (OWN-069) that a weather forecast is a factor wherever the game isn't under a closed roof. They chose free providers for a multi-source system that updates as kickoff approaches and leans little on weather indoors.

They also found that observed and forecast weather must not be mixed. A lineup decision sees only the forecast, and training a feature on what happened would leak.

## Decision

1. **Sources and roles.**

| Role | Source | Use |
| --- | --- | --- |
| Integration layer | Open-Meteo forecast and ensemble APIs | Every lead time. Several models in one call. Hourly temperature, wind and gusts, precipitation and snow, humidity and pressure. Ensemble spread |
| Game-day high resolution | NOAA RRFS (operational 2026-11-03); HRRR as a cross-check while it runs | The last 48 hours, especially wind and precipitation near the stadium |
| Official guidance | NWS API (hourly gridpoint forecast, alerts) and the National Blend of Models | Every lead time inside about seven days. Severe-weather alerts |
| Independent medium range | ECMWF IFS and AIFS open data | Three to ten days. Disagreement between models |
| What happened | NOAA GHCNh hourly stations, Meteostat; nflverse `temp` and `wind` as a cross-check | Outcomes and effect estimation only. Never a pregame feature for the game it describes |
| Point-in-time history | Open-Meteo Previous Runs (from Jan 2024) and Single Runs; NBM archive on AWS | Forecast features for backtests |

   Open-Meteo is used under its non-commercial terms. Open-Meteo and ECMWF data carry CC BY 4.0 attribution wherever the app shows them. Nothing depends on NAM, which was retired on 2026-11-03.

2. **Each forecast is a point-in-time record.** A record holds the source, model, run (issue) time, when Arbit fetched it, lead time, valid hour, venue and the values. Records are append-only.
   - Under ADR-007 a forecast counts from when Arbit fetched it.
   - For archived forecasts read later (A1), it counts from the run's publication: the run time plus the source's documented delay.
   - A feature at a decision time uses only records known before it.
3. **Captures follow the kickoff.** The worker reads each upcoming game's venue on a lead-time schedule: daily from seven days out, then about 72, 48, 24, 12, 6, 3 and 1 hours before kickoff. Each source is read within its own horizon: ECMWF and AIFS from day 7, NBM and NWS inside about seven days, RRFS inside 84 hours. A game moved in the schedule moves its captures. The owner's call budget is far above the need: a regular-season week has at most 16 games, and fewer outdoors.
4. **Roofs set how much weather counts.**
   - Dome and fixed-roof games carry indoor conditions, so weather contributes nothing.
   - Open-air games use the forecast.
   - Retractable roofs before the decision are a mixture: the forecast's effect is weighted by the probability that the roof is open, estimated from that venue's history in similar conditions. Once nflverse records the roof state after the game, the outcome is labeled with it.
5. **Effects are measured, then applied.**
   - **Estimation:** how wind, gusts, precipitation, snow and temperature change passing, kicking and each position's FFA output, estimated from observed weather across past seasons. That is legitimate, because it describes the conditions, not a forecast.
   - **At a decision time:** the Model applies those effects to the forecast distribution, using ensemble and cross-model spread as uncertainty.
   - **Backtests:** the weather feature group is backtested only where point-in-time forecasts exist (2024 onward). Earlier seasons are labeled observation-only.
   - **Explanations:** sit/start shows weather as a measured contribution (OWN-068), with the forecast's age and disagreement.
6. **Venues are data with provenance.** A committed venue table gives each stadium's coordinates, elevation, roof type, surface and field orientation, each with its source. International and neutral sites are included.
7. **Supervised like every source.** Each weather source gets a worker lane entry with a cadence and stale limit, a freshness row, private raw captures and a catch-up path (ENG-052).
   - The NWS User-Agent contact comes from an ignored local setting chosen by the owner, never from source.
   - No other provider's fantasy data enters through weather sources.

## Alternatives

- **nflverse weather only.** Recorded after games, so it can't inform a lineup decision. Rejected by the owner.
- **One provider.** Simpler, but it can't measure forecast disagreement, and it ties game-day wind to one model. Rejected for the owner's multi-source design.
- **Historical Forecast API as training history.** It stitches the latest forecast for each hour, which is close to what happened. Using it as a pregame feature would leak. Allowed only as labeled analysis.
- **GRIB-wide downloads.** Unnecessary at around 30 venues. Point extraction uses index byte ranges or point APIs.

## Consequences

- Weather becomes a measured contribution for outdoor games, with uncertainty that shrinks toward kickoff.
- The worker adds lanes and storage, and GRIB reading adds a dependency (pre-authorized for development).
- Backtests of weather features cover 2024 onward. Effect estimates use all seasons with observations.
- Venue data must be built and kept current, including international games.

## Validation and adoption

- **Adopted by the owner (OWN-069)** for the direction and the source stack.
- **Per-source acceptance:** each source is accepted only after its slice's real-data capture and freshness check. The plan is [weather intelligence](../../superpowers/plans/2026-11-22-weather-intelligence.md).
- **Related:** Q-016, R-063, OWN-061, OWN-063, OWN-066, OWN-068; MD-002, MD-004, LN-002, LN-003.

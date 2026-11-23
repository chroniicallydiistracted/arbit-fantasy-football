# Weather sources for game-day forecasts, 2026-11-22

The owner chose a multi-source weather stack for games played outside a closed roof (OWN-069): Open-Meteo, NOAA RRFS, NWS and the National Blend of Models, ECMWF and AIFS, and NOAA historical observations or Meteostat. This note checks each source's access, terms and history against primary pages. It also records what matters for honest backtests.

Each fact carries one of the evidence grades in [SOURCE_OF_TRUTH](../governance/SOURCE_OF_TRUTH.md):
- **Observed:** Arbit read it itself, with a time.
- **Documented:** a provider page or notice says it.
- **Unknown:** not established.

## Findings

### NOAA RRFS and the retirement of older models (SRC-34)

- **Documented:**
  - NWS Service Change Notice 26-48 (updated 2026-10-15) puts RRFS and REFS into operations on 2026-11-03, replacing NAM, HREF, SREF and HiresW.
  - SCN 26-89 lists the downstream removals of NAM, SREF and the HiresW members from the 12 UTC run that day.
  - Earlier dates, 2026-08-31 and 2026-10-06, were superseded.
  - RRFS runs hourly at about 3 km over the contiguous US, out to 84 hours.
- **Correction to the owner's note:** HRRR is **not** retired by this change. NOAA's RRFS page says it "will remain in operations", and an NWS webinar (2026-06-25) placed its retirement with a later RRFS upgrade, after RRFS matches it.
- **Observed 2026-11-23 about 00:00 UTC:**
  - `nomads.ncep.noaa.gov/pub/data/nccf/com/nam/prod/` returned 404.
  - `…/rrfs/prod/` and `…/hrrr/prod/` returned 200. The responses had empty bodies, so the directory contents were not read.
- **Consequence:** game-day high-resolution guidance comes from RRFS, with HRRR as a cross-check while it lasts. Nothing may depend on NAM.

### Open-Meteo (SRC-35)

- **Terms (documented):**
  - The free API is for non-commercial use only: fewer than 10,000 calls a day, 5,000 an hour and 600 a minute.
  - The data is CC BY 4.0, so attribution is required.
  - There is no service guarantee.
  - Arbit is a private family app, so it qualifies. A commercial use would need a paid plan.
- **Archives for honest backtests (documented):**
  - **Previous Runs API:** each variable at fixed lead times of 1 to 7 days, from January 2024.
  - **Single Runs API:** whole runs as issued. ECMWF IFS HRES is kept from March 2024, and other models from 2026-04-02.
  - **Historical Forecast API:** stitches runs into one continuous series, the latest available forecast for each hour. That is close to what happened, not what was forecast days before, so it is **not** a point-in-time source for lineup-time features.
  - **Historical Weather API:** reanalysis, not observations.

### NWS API and the National Blend of Models (SRC-36)

- **NWS API (`api.weather.gov`), documented:**
  - It needs no key, but it rejects requests without a descriptive User-Agent that includes contact information.
  - `/points/{lat},{lon}` gives a grid, then `/gridpoints/{office}/{x},{y}/forecast/hourly` gives the hourly forecast. Alerts come from `/alerts`.
  - The rate limit is not published.
- **NBM, documented:**
  - Hourly cycles, in GRIB2 and in station text bulletins.
  - The archive is on AWS (`noaa-nbm-grib2-pds`, no account needed), and current runs are on NOMADS for one to two days.
  - It is NOAA open data with no use restrictions.
  - **Consequence:** NBM is the only official guidance with an archive that Arbit can read point in time for past seasons.

### ECMWF and AIFS (SRC-37)

- **Documented:**
  - ECMWF open data is CC-BY-4.0 with attribution.
  - Real-time AIFS output is free, mirrored on AWS (`ecmwf-forecasts`, no account), and read with ECMWF's `ecmwf-opendata` package.
  - The historical archive (MARS) needs registration.
  - Resolution statements differ between pages: older ones say 0.25° or 0.5°, and newer ones say full resolution as the catalogue opens.
- **Role:** three- to ten-day leads, and an independent check for disagreement between models.

### Historical observations (SRC-38)

- **GHCNh (documented):** NOAA's hourly station network, which replaces ISD. NCEI is ending online ISD service. It is on AWS (`noaa-ghcnh`).
- **Meteostat (documented):** its pages conflict, citing CC BY 4.0 on one and CC BY-NC 4.0 on another. Either fits Arbit's private use. Data it takes straight from NOAA or DWD follows those providers' terms.
- **nflverse `temp` and `wind`:** filled only after games (R-063). They are a cross-check, not the record.

## What matters for the Model

1. **Forecasts and observations are different things.**
   - Training a weather effect on what happened is fine for learning how conditions change play.
   - A backtest feature must be the forecast available at the lineup decision time (ADR-007).
   - Point-in-time forecasts exist from January 2024 (Open-Meteo Previous Runs), from 2026-04-02 for most single runs, and across the NBM archive on AWS.
   - Earlier seasons have observations only. Their backtests can't claim a forecast-based feature, and the report must say so.
2. **Forecasts change as kickoff approaches.** Each capture is kept with:
   - the model run (issue) time;
   - when Arbit fetched it;
   - its lead time and the hour it describes.

   A later capture never overwrites an earlier one.
3. **Roofs.**
   - Dome and fixed-roof games carry indoor conditions, so weather adds nothing.
   - Retractable roofs are decided close to kickoff, and nflverse records `roof` as `open` or `closed` only afterwards. Before the decision the roof is uncertain, and its forecast still applies with that uncertainty attached.
4. **Venue coordinates.** nflverse gives `stadium_id`, `roof` and `surface` but no coordinates, and Arbit has no venue table yet. Each stadium needs coordinates, elevation and the field's compass orientation, which turns a wind direction into crosswind or along-field. Each value needs its source.
5. **NWS User-Agent contact.** The NWS requires contact details in each request's header. Which contact goes there is the owner's choice. It is kept in an ignored local setting and never committed.

## Sources

- NWS [SCN 26-48 updated (2026-10-15)](https://www.weather.gov/media/notification/pdf_2026/scn26-48_updated_RRFS_and_REFS_Implementation_aac.pdf), [SCN 26-89 downstream changes](https://www.weather.gov/media/notification/pdf_2026/scn26-89_RRFS_Downstream.pdf), [RRFS webinar Q&A (2026-06-25)](https://www.weather.gov/media/wrn/calendar/RRFS_REF-Webinar&RegistrationFormQANotes.pdf), [NOAA GSL RRFS page](https://gsl.noaa.gov/rrfs/), [NOAA news release](https://www.noaa.gov/news-release/noaa-weather-modeling-hits-key-milestone-with-rapid-refresh-forecast-system-debut), [Open-Meteo tracking issue #1849](https://github.com/open-meteo/open-meteo/issues/1849)
- Open-Meteo [terms](https://open-meteo.com/en/terms), [pricing](https://open-meteo.com/en/pricing), [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api), [Single Runs API](https://open-meteo.com/en/docs/single-runs-api), [Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api)
- NWS [API documentation](https://www.weather.gov/documentation/services-web-api); NBM on [AWS Open Data](https://registry.opendata.aws/noaa-nbm), [MDL download page](https://vlab.noaa.gov/web/mdl/nbm-download), [NOMADS description](https://nomads.ncep.noaa.gov/txt_descriptions/BLEND_txt.html)
- ECMWF [open data](https://ecmwf.int/en/forecasts/datasets/open-data), [AIFS data](https://ecmwf.int/en/forecasts/dataset/aifs-machine-learning-data)
- NCEI [GHCNh](https://ncei.noaa.gov/products/global-historical-climatology-network-hourly), [GHCNh on AWS](https://registry.opendata.aws/noaa-ghcnh/); Meteostat [licence](https://dev.meteostat.net/license), [server repository](https://github.com/meteostat/meteostat-server)

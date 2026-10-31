"""Safe operator output, deliberately excluding names, source bodies and stat values."""

from collections import Counter

from arbit_data.espn.contracts import EspnAcquisition


def acquisition_summary(acquisition: EspnAcquisition) -> dict[str, object]:
    league = acquisition.league
    return {
        "provider": "espn",
        "leagueId": str(league.id),
        "season": league.season_id,
        "scoringPeriod": league.scoring_period_id,
        "teams": len(league.teams),
        "ownedPlayers": sum(len(team.roster.entries) for team in league.teams),
        "availablePlayers": len(acquisition.available),
        "availableByStatus": dict(Counter(player.status for player in acquisition.available)),
        "scoringItems": len(league.settings.scoring_settings.scoring_items),
        "draftPicks": len(league.draft_detail.picks),
        "matchups": len(league.schedule),
        "rulesNormalized": False,
        "canonicalIdentitiesResolved": False,
        "published": False,
        "captureStartedAt": acquisition.capture_started_at.isoformat(),
        "captureFinishedAt": acquisition.capture_finished_at.isoformat(),
        "sources": [
            {
                "url": receipt.url,
                "fantasyFilter": receipt.fantasy_filter,
                "observedAt": receipt.observed_at.isoformat(),
                "sha256": receipt.sha256,
                "bytes": receipt.byte_count,
            }
            for receipt in acquisition.receipts
        ],
    }

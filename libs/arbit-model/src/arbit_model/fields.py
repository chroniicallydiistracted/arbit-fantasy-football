"""Every imported nflverse field gets one recorded use in the Model (ADR-006, OWN-061).

Rules are matched in order and the first match wins. Families with fields of different kinds
list those fields by name, so a field nflverse adds later matches nothing until someone classifies
it. The committed catalog (`nflverse_fields.json`) is generated from these rules over the imported
manifests. `unclassified` reports every imported field the catalog lacks; the field catalog check
fails on any.
"""

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import resources
from typing import Any, Literal

Use = Literal[
    "pre_game", "history", "earlier_seasons", "as_imported", "outcome", "identity", "excluded"
]

FORMAT = "arbit-nflverse-field-catalog-v1"

USES: dict[Use, str] = {
    "pre_game": "Known before kickoff of the game it describes. An input for that game at the "
    "decision times the availability policy allows",
    "history": "Describes a completed game, play or dated event. An input only for later games, "
    "once published",
    "earlier_seasons": "Published after the season it describes. An input only for later seasons",
    "as_imported": "A current value without its own date. It applies from the Arbit import that "
    "held it (an observed vintage) and never to a game before that import (ADR-007 A2)",
    "outcome": "Recorded only after the game and never an input. Kept for labels, reconciliation "
    "or explanation",
    "identity": "Keys, names, identifiers, display and provenance attributes. Used for joins and "
    "labels, never as a statistical input",
    "excluded": "Kept from the Model by policy, never for timing (ADR-007 A2); the rule gives the "
    "decision. A gated rule is readable only for the study its decision names",
}

# `misc` holds unrelated tables whose columns share names, so each table is its own family.
SPLIT_FAMILIES = frozenset({"misc"})


@dataclass(frozen=True)
class Rule:
    id: str
    use: Use
    reason: str
    families: frozenset[str] | None = None  # None: every family
    fields: frozenset[str] = frozenset()
    pattern: str | None = None  # full match
    every_field: bool = False  # the whole family, for families excluded wholesale
    decision: str | None = None

    def matches(self, family: str, field: str) -> bool:
        if self.families is not None and family not in self.families:
            return False
        if self.every_field or field in self.fields:
            return True
        return self.pattern is not None and re.fullmatch(self.pattern, field) is not None


def _names(text: str) -> frozenset[str]:
    return frozenset(text.split())


def _families(text: str) -> frozenset[str]:
    return frozenset(text.split())


PLAYER_IDS = _names(
    "gsis_id espn_id sportradar_id yahoo_id rotowire_id pff_id pfr_id fantasy_data_id sleeper_id "
    "esb_id gsis_it_id smart_id"
)
ROSTER_IDENTITY = PLAYER_IDS | _names(
    "season team week game_type jersey_number full_name first_name last_name football_name "
    "headshot_url"
)
ROSTER_FACTS = _names(
    "position depth_chart_position status status_description_abbr birth_date height weight "
    "college years_exp entry_year rookie_year draft_club draft_number ngs_position"
)
PLAYER_DIRECTORY_IDENTITY = _names(
    "gsis_id display_name common_first_name first_name last_name short_name football_name suffix "
    "esb_id nfl_id pfr_id pff_id otc_id espn_id smart_id headshot jersey_number nfl_player_id "
    "esbid gsis_it_id pff_position position_group position ngs_position_group ngs_position"
)
PLAYER_DIRECTORY_FACTS = _names(
    "birth_date height weight college_name college_conference rookie_season draft_year "
    "draft_round draft_pick draft_team"
)
PLAYER_DIRECTORY_SNAPSHOT = _names(
    "status ngs_status ngs_status_short_description last_season latest_team "
    "years_of_experience pff_status"
)
WEEKLY_STATISTICS = _names(
    "games completions attempts passing_yards passing_tds passing_interceptions sacks_suffered "
    "sack_yards_lost sack_fumbles sack_fumbles_lost passing_air_yards passing_yards_after_catch "
    "passing_first_downs passing_epa passing_cpoe passing_2pt_conversions pacr passing_10 "
    "passing_16 passing_20 passing_40 carries rushing_yards rushing_tds rushing_fumbles "
    "rushing_fumbles_lost rushing_first_downs rushing_epa rushing_2pt_conversions rushing_10 "
    "rushing_12 rushing_20 rushing_40 receptions targets receiving_yards receiving_tds "
    "receiving_fumbles receiving_fumbles_lost receiving_air_yards receiving_yards_after_catch "
    "receiving_first_downs receiving_epa receiving_2pt_conversions receiving_10 receiving_16 "
    "receiving_20 receiving_40 racr target_share air_yards_share wopr special_teams_tds "
    "def_tackles_solo def_tackles_with_assist def_tackle_assists def_tackles_for_loss "
    "def_tackles_for_loss_yards def_fumbles_forced def_sacks def_sack_yards def_qb_hits "
    "def_interceptions def_interception_yards def_pass_defended def_tds def_fumbles def_safeties "
    "def_punt_blocks def_pat_blocks def_fg_blocks def_2pt_atts def_2pt_made misc_yards "
    "fumble_recovery_own fumble_recovery_yards_own fumble_recovery_opp fumble_recovery_yards_opp "
    "fumble_recovery_tds penalties penalty_yards timeouts fumbles_forced_by_opp "
    "fumbles_not_forced fumbles_out_of_bounds fumbles_total fumbles_lost_total punt_returns "
    "punt_return_yards kickoff_returns kickoff_return_yards fg_made fg_att fg_missed fg_blocked "
    "fg_long fg_pct fg_made_0_19 fg_made_20_29 fg_made_30_39 fg_made_40_49 fg_made_50_59 "
    "fg_made_60_ fg_missed_0_19 fg_missed_20_29 fg_missed_30_39 fg_missed_40_49 fg_missed_50_59 "
    "fg_missed_60_ fg_made_list fg_missed_list fg_blocked_list fg_made_distance "
    "fg_missed_distance fg_blocked_distance pat_made pat_att pat_missed pat_blocked pat_pct "
    "gwfg_made gwfg_att gwfg_missed gwfg_blocked gwfg_distance_list gwfg_distance pt_att "
    "pt_blocked pt_long pt_yards pt_inside_20 pt_out_of_bounds pt_downed pt_touchback "
    "pt_fair_caught pt_returned pt_return_yards pt_return_tds pt_net_yards"
)
PBP_IDENTITY = _names(
    "play_id game_id old_game_id nfl_api_id home_team away_team posteam defteam passer rusher "
    "receiver passer_id rusher_id receiver_id name id jersey_number fantasy fantasy_id "
    "drive_play_id_started drive_play_id_ended stadium stadium_id game_stadium"
)
PBP_FITTED = (
    r"ep|epa|wp|def_wp|home_wp|away_wp|wpa|home_wp_post|away_wp_post|cp|cpoe|xpass|pass_oe"
    r"|qb_epa|success|no_score_prob|opp_fg_prob|opp_safety_prob|opp_td_prob|fg_prob"
    r"|safety_prob|td_prob|extra_point_prob|two_point_conversion_prob|xyac_[a-z_]+"
    r"|(air|yac|comp_air|comp_yac)_(epa|wpa)|total_(home|away)_([a-z_]+_)?(epa|wpa)"
)
PBP_EVENTS = _names(
    "posteam_type side_of_field yardline_100 quarter_seconds_remaining half_seconds_remaining "
    "game_seconds_remaining game_half quarter_end drive sp qtr down goal_to_go time yrdln "
    "ydstogo ydsnet play_type yards_gained shotgun no_huddle qb_dropback qb_kneel qb_spike "
    "qb_scramble pass_length pass_location air_yards yards_after_catch run_location run_gap "
    "field_goal_result kick_distance extra_point_result two_point_conv_result "
    "home_timeouts_remaining away_timeouts_remaining timeout timeout_team td_team "
    "posteam_timeouts_remaining defteam_timeouts_remaining total_home_score total_away_score "
    "posteam_score defteam_score score_differential posteam_score_post defteam_score_post "
    "score_differential_post punt_blocked first_down_rush first_down_pass first_down_penalty "
    "third_down_converted third_down_failed fourth_down_converted fourth_down_failed "
    "incomplete_pass touchback interception punt_inside_twenty punt_in_endzone "
    "punt_out_of_bounds punt_downed punt_fair_catch kickoff_inside_twenty kickoff_in_endzone "
    "kickoff_out_of_bounds kickoff_downed kickoff_fair_catch fumble_forced fumble_not_forced "
    "fumble_out_of_bounds solo_tackle safety penalty tackled_for_loss fumble_lost "
    "own_kickoff_recovery own_kickoff_recovery_td qb_hit rush_attempt pass_attempt sack "
    "touchdown pass_touchdown rush_touchdown return_touchdown extra_point_attempt "
    "two_point_attempt field_goal_attempt kickoff_attempt punt_attempt fumble complete_pass "
    "assist_tackle lateral_reception lateral_rush lateral_return lateral_recovery passing_yards "
    "receiving_yards rushing_yards lateral_receiving_yards lateral_rushing_yards "
    "forced_fumble_player_1_team forced_fumble_player_2_team solo_tackle_1_team "
    "solo_tackle_2_team assist_tackle_1_team assist_tackle_2_team assist_tackle_3_team "
    "assist_tackle_4_team tackle_with_assist tackle_with_assist_1_team tackle_with_assist_2_team "
    "fumbled_1_team fumbled_2_team fumble_recovery_1_team fumble_recovery_1_yards "
    "fumble_recovery_2_team fumble_recovery_2_yards return_team return_yards penalty_team "
    "penalty_yards replay_or_challenge replay_or_challenge_result penalty_type "
    "defensive_two_point_attempt defensive_two_point_conv defensive_extra_point_attempt "
    "defensive_extra_point_conv series series_success series_result order_sequence "
    "time_of_day play_clock play_deleted play_type_nfl special_teams_play st_play_type "
    "end_clock_time end_yard_line fixed_drive fixed_drive_result drive_real_start_time "
    "drive_play_count drive_time_of_possession drive_first_downs drive_inside20 "
    "drive_ended_with_score drive_quarter_start drive_quarter_end drive_yards_penalized "
    "drive_start_transition drive_end_transition drive_game_clock_start drive_game_clock_end "
    "drive_start_yard_line drive_end_yard_line aborted_play pass rush first_down special play "
    "out_of_bounds home_opening_kickoff"
)
NGS_IDENTITY = _names(
    "season season_type week player_display_name player_position team_abbr player_gsis_id "
    "player_first_name player_last_name player_jersey_number player_short_name"
)
NGS_MEASURES = _names(
    "avg_cushion avg_separation avg_intended_air_yards percent_share_of_intended_air_yards "
    "receptions targets catch_percentage yards rec_touchdowns avg_yac avg_expected_yac "
    "avg_yac_above_expectation avg_time_to_throw avg_completed_air_yards "
    "avg_air_yards_differential aggressiveness max_completed_air_distance "
    "avg_air_yards_to_sticks attempts pass_yards pass_touchdowns interceptions passer_rating "
    "completions completion_percentage expected_completion_percentage "
    "completion_percentage_above_expectation avg_air_distance max_air_distance efficiency "
    "percent_attempts_gte_eight_defenders avg_time_to_los rush_attempts rush_yards "
    "expected_rush_yards rush_yards_over_expected avg_rush_yards "
    "rush_yards_over_expected_per_att rush_pct_over_expected rush_touchdowns"
)
PFR_IDENTITY = _names(
    "season player pfr_id tm team pos game_id pfr_game_id pfr_player_name pfr_player_id "
    "opponent week game_type"
)
PFR_MEASURES = _names(
    "g gs int tgt cmp cmp_percent yds yds_cmp yds_tgt td rat dadot air yac bltz hrry qbkd sk "
    "prss comb m_tkl m_tkl_percent loaded bats pass_attempts throwaways spikes drops drop_pct "
    "bad_throws bad_throw_pct pocket_time times_blitzed times_hurried times_hit times_pressured "
    "pressure_pct batted_balls on_tgt_throws on_tgt_pct rpo_plays rpo_yards rpo_pass_att "
    "rpo_pass_yards rpo_rush_att rpo_rush_yards pa_pass_att pa_pass_yards intended_air_yards "
    "intended_air_yards_per_pass_attempt completed_air_yards completed_air_yards_per_completion "
    "completed_air_yards_per_pass_attempt pass_yards_after_catch "
    "pass_yards_after_catch_per_completion scrambles scramble_yards_per_attempt rec x1d ybc "
    "ybc_r yac_r adot brk_tkl rec_br drop drop_percent att ybc_att yac_att att_br def_ints "
    "def_targets def_completions_allowed def_completion_pct def_yards_allowed "
    "def_yards_allowed_per_cmp def_yards_allowed_per_tgt def_receiving_td_allowed "
    "def_passer_rating_allowed def_adot def_air_yards_completed def_yards_after_catch "
    "def_times_blitzed def_times_hurried def_times_hitqb def_sacks def_pressures "
    "def_tackles_combined def_missed_tackles def_missed_tackle_pct passing_drops "
    "passing_drop_pct receiving_drop receiving_drop_pct passing_bad_throws "
    "passing_bad_throw_pct times_sacked times_pressured_pct rushing_broken_tackles "
    "receiving_broken_tackles receiving_int receiving_rat carries rushing_yards_before_contact "
    "rushing_yards_before_contact_avg rushing_yards_after_contact "
    "rushing_yards_after_contact_avg"
)
FTN_MEASURES = _names(
    "starting_hash qb_location n_offense_backfield n_defense_box is_no_huddle is_motion "
    "is_play_action is_screen_pass is_rpo is_trick_play is_qb_out_of_pocket "
    "is_interception_worthy is_throw_away read_thrown is_catchable_ball is_contested_ball "
    "is_created_reception is_drop is_qb_sneak n_blitzers n_pass_rushers is_qb_fault_sack"
)
PARTICIPATION_MEASURES = _names(
    "offense_formation offense_personnel defenders_in_box defense_personnel "
    "number_of_pass_rushers players_on_play offense_players defense_players n_offense n_defense "
    "ngs_air_yards time_to_throw was_pressure route defense_man_zone_type defense_coverage_type "
    "offense_positions defense_positions"
)
DRAFT_CAREER = _names(
    "hof to allpro probowls seasons_started w_av car_av dr_av games pass_completions "
    "pass_attempts pass_yards pass_tds pass_ints rush_atts rush_yards rush_tds receptions "
    "rec_yards rec_tds def_solo_tackles def_ints def_sacks"
)
CONTRACT_TERMS = _names(
    "position team year_signed years value apy guaranteed apy_cap_pct inflated_value "
    "inflated_apy inflated_guaranteed height weight draft_year draft_round draft_overall "
    "draft_team date_of_birth season_history contract_history"
)
QBR_IDENTITY = _names(
    "season season_type game_week team_abb player_id name_short name_first name_last "
    "name_display headshot_href team game_id week_text opp_id opp_abb opp_team opp_name week_num"
)
QBR_MEASURES = _names(
    "rank qbr_total pts_added qb_plays epa_total pass run exp_sack penalty qbr_raw sack qualified"
)

FFA_OWN_061 = "OWN-061"

RULES: tuple[Rule, ...] = (
    # Policy rules that hold in every family.
    Rule(
        "generic-fantasy-points",
        "excluded",
        "nflverse's generic fantasy points use upstream scoring, not FFA's rules",
        pattern=r"fantasy_points(_[a-z]+)?",
        decision=FFA_OWN_061,
    ),
    Rule(
        "betting-lines",
        "excluded",
        "A betting market's forecast of the game. It enters only if the Q-014 study and the "
        "slice 4 ablation show better FFA-point accuracy and calibration; readable only for that "
        "study",
        families=_families("schedules pbp"),
        fields=_names(
            "spread_line total_line away_moneyline home_moneyline away_spread_odds "
            "home_spread_odds under_odds over_odds vegas_wp vegas_home_wp vegas_wpa "
            "vegas_home_wpa"
        ),
        decision="OWN-067",
    ),
    Rule(
        "weather-after-game",
        "history",
        "Observed weather, filled in only after the game (empty for every 2026 game): history for "
        "later games and the weather effect study, never a pre-game input for the game it "
        "describes. Forecasts come from the weather system (ADR-008)",
        families=_families("schedules pbp"),
        fields=_names("temp wind weather"),
        decision="R-063",
    ),
    # Families excluded wholesale.
    Rule(
        "ffopportunity",
        "excluded",
        "ffopportunity's expected fantasy points: another provider's fantasy model and points",
        families=_families("ff_opportunity"),
        every_field=True,
        decision=FFA_OWN_061,
    ),
    Rule(
        "dynastyprocess-values",
        "excluded",
        "DynastyProcess and FantasyPros values, rankings and projections",
        families=_families("dynastyprocess"),
        every_field=True,
        decision=FFA_OWN_061,
    ),
    Rule(
        "espn-draft-projections",
        "excluded",
        "ESPN's draft probabilities and analyst ranks: another provider's projections",
        families=_families("misc/espn_draft_player_probs misc/espn_draft_position_probs"),
        every_field=True,
        decision=FFA_OWN_061,
    ),
    Rule(
        "release-tests",
        "excluded",
        "Assets nflverse publishes to test its release pipeline",
        families=_families("test"),
        every_field=True,
    ),
    Rule(
        "legacy-player-stats",
        "excluded",
        "Legacy release (through 2024) superseded by stats_player and stats_team, which carry "
        "the same statistics for every season; kept only for reconciliation",
        families=_families("player_stats"),
        every_field=True,
    ),
    # The DynastyProcess ID directory is an identity source only.
    Rule(
        "id-directory-keys",
        "identity",
        "Cross-provider identifiers used only to join players",
        families=_families("ff_playerids"),
        pattern=r"[a-z_]+_id|name|merge_name|position|team|db_season",
    ),
    Rule(
        "id-directory-facts",
        "excluded",
        "The DynastyProcess directory is used only for identifiers; player facts come from "
        "nflverse's own player tables",
        families=_families("ff_playerids"),
        fields=_names(
            "birthdate age draft_year draft_round draft_pick draft_ovr twitter_username height "
            "weight college"
        ),
        decision=FFA_OWN_061,
    ),
    # Schedules.
    Rule(
        "schedule-keys",
        "identity",
        "Game, team, venue and provider keys and names",
        families=_families("schedules"),
        fields=_names(
            "game_id old_game_id gsis nfl_detail_id pfr pff espn ftn away_team home_team "
            "stadium_id stadium away_qb_name home_qb_name"
        ),
    ),
    Rule(
        "schedule-context",
        "pre_game",
        "Game context set before kickoff: date and time, rest, venue, roof, surface, division "
        "and head coaches",
        families=_families("schedules"),
        fields=_names(
            "season game_type week gameday weekday gametime location away_rest home_rest "
            "div_game roof surface away_coach home_coach"
        ),
    ),
    Rule(
        "expected-quarterbacks",
        "pre_game",
        "Expected starting quarterbacks, published about a week ahead. Past games show the "
        "actual starter, so a backtest may use them only after inactives",
        families=_families("schedules"),
        fields=_names("away_qb_id home_qb_id"),
    ),
    Rule(
        "referee",
        "pre_game",
        "Referee assigned in game week: a candidate input that must show out-of-sample benefit",
        families=_families("schedules"),
        fields=_names("referee"),
    ),
    Rule(
        "final-score",
        "history",
        "Final score: team scoring history and the D/ST points-allowed target",
        families=_families("schedules pbp"),
        fields=_names("away_score home_score result total overtime"),
    ),
    # Play-by-play.
    Rule(
        "pbp-keys",
        "identity",
        "Play, game, team and player keys, names and jersey numbers",
        families=_families("pbp"),
        fields=PBP_IDENTITY,
        pattern=r"[a-z0-9_]+_(player_id|player_name|jersey_number)",
    ),
    Rule(
        "pbp-game-context",
        "pre_game",
        "Game context repeated on each play; the same facts as schedules",
        families=_families("pbp"),
        fields=_names(
            "season season_type week game_date start_time location roof surface div_game "
            "home_coach away_coach"
        ),
    ),
    Rule(
        "pbp-free-text",
        "excluded",
        "Free-text play description. Its facts are in structured fields, and parsing the text "
        "would add an unverified second source",
        families=_families("pbp"),
        fields=_names("desc"),
    ),
    Rule(
        "nflfastr-model-outputs",
        "history",
        "nflfastR model outputs per play (expected points, win probability, completion "
        "probability, expected YAC, expected dropback). The availability policy records which "
        "seasons the producing model was fitted on",
        families=_families("pbp"),
        pattern=PBP_FITTED,
    ),
    Rule(
        "pbp-events",
        "history",
        "Play-level situation, opportunity and result: down, distance, field position, air "
        "yards, scoring, turnovers, penalties, drives and clock",
        families=_families("pbp"),
        fields=PBP_EVENTS,
    ),
    # Weekly statistics.
    Rule(
        "weekly-stat-keys",
        "identity",
        "Keys, names and labels. The position label is nflverse's current one, not a dated role",
        families=_families("stats_player stats_team"),
        fields=_names(
            "player_id player_name player_display_name headshot_url game_id team recent_team "
            "opponent_team season season_type week position position_group"
        ),
    ),
    Rule(
        "weekly-statistics",
        "history",
        "Per-game and season statistics: history for later games and the source of the FFA "
        "training target",
        families=_families("stats_player stats_team"),
        fields=WEEKLY_STATISTICS,
    ),
    Rule(
        "ngs-keys",
        "identity",
        "Player, team and period keys and names",
        families=_families("nextgen_stats"),
        fields=NGS_IDENTITY,
    ),
    Rule(
        "ngs-measures",
        "history",
        "Next Gen Stats tracking measures (from 2016): separation, cushion, time to throw, "
        "aggressiveness, expected completion and YAC, rushing yards over expected",
        families=_families("nextgen_stats"),
        fields=NGS_MEASURES,
    ),
    Rule(
        "pfr-keys",
        "identity",
        "Player, team, game and period keys and names",
        families=_families("pfr_advstats"),
        fields=PFR_IDENTITY,
    ),
    Rule(
        "pfr-age",
        "pre_game",
        "Age in that season",
        families=_families("pfr_advstats"),
        fields=_names("age"),
    ),
    Rule(
        "pfr-measures",
        "history",
        "Pro Football Reference charting (from 2018): pressures, blitzes, drops, bad throws, "
        "broken tackles, yards before and after contact, coverage allowed",
        families=_families("pfr_advstats"),
        fields=PFR_MEASURES,
    ),
    Rule(
        "snap-keys",
        "identity",
        "Player, team, game and period keys; the game-level position label",
        families=_families("snap_counts"),
        fields=_names(
            "game_id pfr_game_id season game_type week player pfr_player_id position team opponent"
        ),
    ),
    Rule(
        "snap-counts",
        "history",
        "Offense, defense and special-teams snaps: role history and the participation labels",
        families=_families("snap_counts"),
        fields=_names("offense_snaps offense_pct defense_snaps defense_pct st_snaps st_pct"),
    ),
    Rule(
        "ftn-keys",
        "identity",
        "FTN and nflverse game and play keys, and when FTN's data was pulled",
        families=_families("ftn_charting"),
        fields=_names(
            "ftn_game_id nflverse_game_id ftn_play_id nflverse_play_id season week date_pulled"
        ),
    ),
    Rule(
        "ftn-charting",
        "history",
        "FTN charting (from 2022), published with a lag: play action, RPO, screens, motion, "
        "box count, blitzers, catchable and contested balls, drops, interception-worthy throws",
        families=_families("ftn_charting"),
        fields=FTN_MEASURES,
    ),
    Rule(
        "participation-keys",
        "identity",
        "Game, play and team keys; player names and jersey numbers on the field",
        families=_families("pbp_participation"),
        fields=_names(
            "nflverse_game_id old_game_id play_id possession_team offense_names defense_names "
            "offense_numbers defense_numbers"
        ),
    ),
    Rule(
        "participation",
        "earlier_seasons",
        "Published after the postseason from 2023 (earlier from a retired NGS source): routes, "
        "coverage, personnel, players on the field and pressure. Informs only later seasons",
        families=_families("pbp_participation"),
        fields=PARTICIPATION_MEASURES,
    ),
    # Availability and roles.
    Rule(
        "injury-keys",
        "identity",
        "Player, team and period keys and names; when the report was modified",
        families=_families("injuries"),
        fields=_names(
            "season game_type season_type team week gsis_id full_name first_name last_name "
            "position date_modified"
        ),
    ),
    Rule(
        "injury-reports",
        "pre_game",
        "Game-status and practice reports: the main evidence of whether a player plays",
        families=_families("injuries"),
        fields=_names(
            "report_primary_injury report_secondary_injury report_status "
            "practice_primary_injury practice_secondary_injury practice_status"
        ),
    ),
    Rule(
        "roster-keys",
        "identity",
        "Player, team and period keys, names, jersey numbers and other providers' player IDs",
        families=_families("weekly_rosters rosters"),
        fields=ROSTER_IDENTITY,
    ),
    Rule(
        "roster-facts",
        "pre_game",
        "Dated roster status, position, depth position, age, size, experience and draft slot. "
        "Weekly status `INA` is set at inactives",
        families=_families("weekly_rosters rosters"),
        fields=ROSTER_FACTS,
    ),
    Rule(
        "depth-chart-keys",
        "identity",
        "Player, team and period keys and names; the observation timestamp",
        families=_families("depth_charts"),
        fields=_names(
            "season club_code week game_type last_name first_name football_name full_name "
            "player_name gsis_id elias_id espn_id jersey_number team dt"
        ),
    ),
    Rule(
        "depth-charts",
        "pre_game",
        "Depth chart position and rank (timestamped from 2025)",
        families=_families("depth_charts"),
        fields=_names(
            "depth_team formation position depth_position pos_grp_id pos_grp pos_id pos_name "
            "pos_abb pos_slot pos_rank"
        ),
    ),
    Rule(
        "trade-keys",
        "identity",
        "Trade and player keys and names",
        families=_families("trades"),
        fields=_names("trade_id pfr_id pfr_name"),
    ),
    Rule(
        "trades",
        "history",
        "Dated trades: a player's team and role change after the trade date",
        families=_families("trades"),
        fields=_names(
            "season trade_date gave received pick_season pick_round pick_number conditional"
        ),
    ),
    # Static facts and priors.
    Rule(
        "player-directory-keys",
        "identity",
        "Player keys, names, images and current position labels; weekly rosters give the "
        "dated position",
        families=_families("players players_components"),
        fields=PLAYER_DIRECTORY_IDENTITY,
    ),
    Rule(
        "player-directory-facts",
        "pre_game",
        "Facts fixed before a player's first game: birth date, size, college and draft slot",
        families=_families("players players_components"),
        fields=PLAYER_DIRECTORY_FACTS,
    ),
    Rule(
        "current-snapshot",
        "as_imported",
        "Current values without dates. They apply from the import that held them, never to "
        "earlier games; weekly rosters and injury reports carry the dated equivalents",
        families=_families("players players_components contracts"),
        fields=PLAYER_DIRECTORY_SNAPSHOT | _names("is_active"),
    ),
    Rule(
        "combine-keys",
        "identity",
        "Player keys, names and school",
        families=_families("combine"),
        fields=_names("player_name pfr_id cfb_id school"),
    ),
    Rule(
        "combine",
        "pre_game",
        "Combine measurements and draft slot, known before a player's first NFL game",
        families=_families("combine"),
        fields=_names(
            "season draft_year draft_team draft_round draft_ovr pos ht wt forty bench vertical "
            "broad_jump cone shuttle"
        ),
    ),
    Rule(
        "draft-keys",
        "identity",
        "Player keys, names and college",
        families=_families("draft_picks"),
        fields=_names("gsis_id pfr_player_id cfb_player_id pfr_player_name college"),
    ),
    Rule(
        "draft-capital",
        "pre_game",
        "Draft year, round, pick, team, position and age at the draft",
        families=_families("draft_picks"),
        fields=_names("season round pick team position category side age"),
    ),
    Rule(
        "draft-career-totals",
        "as_imported",
        "Career totals and honours as of the file date. They apply from the import that held "
        "them, never to earlier games; weekly statistics carry the same totals by game",
        families=_families("draft_picks"),
        fields=DRAFT_CAREER,
    ),
    Rule(
        "contract-keys",
        "identity",
        "Player keys, names, college and Over The Cap links",
        families=_families("contracts"),
        fields=_names("player otc_id gsis_id player_page player_url college"),
    ),
    Rule(
        "contract-terms",
        "pre_game",
        "Contract terms dated by signing year, and player facts: investment signals role",
        families=_families("contracts"),
        fields=CONTRACT_TERMS,
    ),
    Rule(
        "official-keys",
        "identity",
        "Game, period and official keys, names and numbers",
        families=_families("officials"),
        fields=_names("game_id game_key official_name jersey_number season season_type week"),
    ),
    Rule(
        "officiating-crews",
        "pre_game",
        "Officiating crew assignments: a candidate input (penalty rates) that must show "
        "out-of-sample benefit",
        families=_families("officials"),
        fields=_names("official_id position"),
    ),
    Rule(
        "qbr-keys",
        "identity",
        "Player, team, opponent, game and period keys, names and images",
        families=_families("espn_data"),
        fields=QBR_IDENTITY,
    ),
    Rule(
        "qbr",
        "history",
        "ESPN's QBR components, computed from play-by-play. A performance rating, not fantasy "
        "data; a candidate that must show benefit over nflverse's own EPA",
        families=_families("espn_data"),
        fields=QBR_MEASURES,
    ),
    Rule(
        "team-keys",
        "identity",
        "Team keys, names, colors and logos",
        families=_families("teams"),
        pattern=r"team_(abbr|name|id|nick|color[0-9]*|logo_[a-z]+|wordmark|conference_logo"
        r"|league_logo)",
    ),
    Rule(
        "team-alignment",
        "pre_game",
        "Conference and division",
        families=_families("teams"),
        fields=_names("team_conf team_division"),
    ),
    Rule(
        "lateral-keys",
        "identity",
        "Game, play, team and player keys and names",
        families=_families("misc/multiple_lateral_yards"),
        fields=_names("game_id play_id team_abbr player_name gsis_player_id"),
    ),
    Rule(
        "lateral-yards",
        "history",
        "Yardage credits on multi-lateral plays that play-by-play cannot attribute",
        families=_families("misc/multiple_lateral_yards"),
        fields=_names("stat_id type yards"),
    ),
    Rule(
        "pbp-id-patches",
        "identity",
        "Corrected player IDs for 2022 and 2023 play-by-play",
        families=_families("misc/pbp_patch_ids_{season}"),
        every_field=True,
    ),
    Rule(
        "pfr-roster-keys",
        "identity",
        "Pro Football Reference roster keys, names, jersey numbers and college",
        families=_families("misc/pfr_rosters"),
        fields=_names("season pfr nfl pfr_player_id no player college_univ"),
    ),
    Rule(
        "pfr-roster-facts",
        "pre_game",
        "Age, position, size, experience, draft slot and salary in that season",
        families=_families("misc/pfr_rosters"),
        fields=_names("age pos wt ht birth_date yrs drafted_tm_rnd_yr salary"),
    ),
    Rule(
        "pfr-roster-season",
        "history",
        "Season games, starts and approximate value",
        families=_families("misc/pfr_rosters"),
        fields=_names("g gs av"),
    ),
)


def catalog_family(family: str, logical_key: str) -> str:
    """The family a field is catalogued under; tables in `misc` stand alone."""
    if family not in SPLIT_FAMILIES:
        return family
    return family + "/" + table_pattern(logical_key)


def table_pattern(logical_key: str) -> str:
    """A table name with its season replaced, so per-season files share one pattern."""
    stem = logical_key.rsplit("/", 1)[-1]
    return re.sub(r"(?<![0-9])(19|20)[0-9]{2}(?![0-9])", "{season}", stem)


def classify(family: str, field: str) -> Rule | None:
    for rule in RULES:
        if rule.matches(family, field):
            return rule
    return None


@dataclass(frozen=True)
class Observation:
    """One imported table's columns, from its manifest."""

    family: str
    logical_key: str
    columns: tuple[tuple[str, str], ...]  # (name, type)
    seasons: tuple[int, ...] = ()
    row_count: int = 0
    missing: Mapping[str, int] | None = None


def _first_seasons(
    observations: Iterable[Observation], multi_season: Mapping[tuple[str, str], int]
) -> dict[tuple[str, str], int]:
    first: dict[tuple[str, str], int] = {}
    for obs in observations:
        family = catalog_family(obs.family, obs.logical_key)
        # Some per-season manifests record no season coverage; their file name carries it.
        named = re.findall(r"(?<![0-9])((?:19|20)[0-9]{2})(?![0-9])", obs.logical_key)
        seasons = obs.seasons or tuple(int(year) for year in named)
        for name, _ in obs.columns:
            season: int | None
            if len(seasons) == 1:
                nulls = (obs.missing or {}).get(name)
                filled = nulls is None or nulls < obs.row_count
                season = seasons[0] if obs.row_count and filled else None
            else:
                season = multi_season.get((obs.logical_key, name))
            if season is not None:
                key = (family, name)
                first[key] = min(season, first.get(key, season))
    return first


def build_catalog(
    observations: Iterable[Observation],
    *,
    multi_season_first: Mapping[tuple[str, str], int] | None = None,
) -> dict[str, Any]:
    """The catalog for these tables. Raises if any field matches no rule."""
    observations = list(observations)
    fields: dict[str, dict[str, dict[str, Any]]] = {}
    unmatched: set[tuple[str, str]] = set()
    for obs in observations:
        family = catalog_family(obs.family, obs.logical_key)
        for name, kind in obs.columns:
            rule = classify(family, name)
            if rule is None:
                unmatched.add((family, name))
                continue
            entry = fields.setdefault(family, {}).setdefault(
                name, {"use": rule.use, "rule": rule.id, "type": kind, "tables": []}
            )
            pattern = table_pattern(obs.logical_key)
            if pattern not in entry["tables"]:
                entry["tables"].append(pattern)
    if unmatched:
        listed = ", ".join(f"{family}.{name}" for family, name in sorted(unmatched))
        raise ValueError(f"UNCLASSIFIED_FIELDS: {listed}")
    first = _first_seasons(observations, multi_season_first or {})
    used = {entry["rule"] for entries in fields.values() for entry in entries.values()}
    by_use: dict[str, int] = dict.fromkeys(USES, 0)
    for family_name, entries in fields.items():
        for name, entry in entries.items():
            entry["tables"].sort()
            entry["firstSeason"] = first.get((family_name, name))
            by_use[entry["use"]] += 1
    return {
        "format": FORMAT,
        "policy": "ADR-006 and OWN-061: every imported nflverse field has one recorded use",
        "uses": dict(USES),
        "rules": {
            rule.id: {
                "use": rule.use,
                "reason": rule.reason,
                **({"decision": rule.decision} if rule.decision else {}),
            }
            for rule in RULES
            if rule.id in used
        },
        "summary": {
            "families": len(fields),
            "fields": sum(len(entries) for entries in fields.values()),
            "byUse": by_use,
        },
        "fields": {
            family: {name: fields[family][name] for name in sorted(fields[family])}
            for family in sorted(fields)
        },
    }


def unclassified(
    catalog: Mapping[str, Any], observations: Iterable[Observation]
) -> list[tuple[str, str]]:
    """Imported fields the catalog has no entry for, as (family, field)."""
    known = catalog["fields"]
    missing = {
        (family, name)
        for obs in observations
        for family in (catalog_family(obs.family, obs.logical_key),)
        for name, _ in obs.columns
        if name not in known.get(family, {})
    }
    return sorted(missing)


def load_catalog() -> dict[str, Any]:
    """The committed catalog."""
    text = resources.files("arbit_model").joinpath("nflverse_fields.json").read_text()
    catalog: dict[str, Any] = json.loads(text)
    if catalog.get("format") != FORMAT:
        raise ValueError("UNKNOWN_FIELD_CATALOG_FORMAT")
    return catalog


def render(catalog: Mapping[str, Any]) -> str:
    """Stable text for the committed file: one line per field, so diffs show each change."""
    head = {key: value for key, value in catalog.items() if key != "fields"}
    lines = [json.dumps(head, indent=1, sort_keys=True)[:-2] + ',\n "fields": {']
    families = list(catalog["fields"].items())
    for index, (family, entries) in enumerate(families):
        lines.append(f"  {json.dumps(family)}: {{")
        items = list(entries.items())
        for position, (name, entry) in enumerate(items):
            comma = "," if position < len(items) - 1 else ""
            body = json.dumps(entry, sort_keys=True)
            lines.append(f"   {json.dumps(name)}: {body}{comma}")
        lines.append("  }" + ("," if index < len(families) - 1 else ""))
    lines.append(" }\n}\n")
    return "\n".join(lines)

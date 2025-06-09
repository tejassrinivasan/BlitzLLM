# constants.py

# Endpoint labels for live/upcoming endpoints
ENDPOINT_LABELS = {
    "mlb": {
        "https://api.sportsdata.io/v3/mlb/scores/json/PlayersByActive": "Blitz Active Players",
        "https://api.sportsdata.io/v3/mlb/scores/json/PlayersByFreeAgents": "Blitz Free Agents",
        "https://api.sportsdata.io/v3/mlb/scores/json/teams": "Blitz Teams",
        "https://api.sportsdata.io/v3/mlb/scores/json/ScoresBasicFinal/{date}": "Blitz Scores Basic",
        "https://api.sportsdata.io/v3/mlb/odds/json/BettingMarketsByGameID/{gameID}": "Blitz Betting Markets",
        "https://api.sportsdata.io/v3/mlb/projections/json/BakerPlayerGameProjections/{date}": "Blitz AI Player Projections",
        "https://baker-api.sportsdata.io/baker/v2/mlb/projections/players/full-season/{season_name}/avg": "Blitz AI Season Projections",
        "https://baker-api.sportsdata.io/baker/v2/mlb/trends/{date}/{team}": "Blitz AI Team Trends",
        "https://baker-api.sportsdata.io/baker/v2/mlb/trends/{date}/players/{playerid}": "Blitz AI Player Trends",
    },
    "nfl": {},
}

# List of all live/upcoming endpoints
UPCOMING_ENDPOINTS = {
    "mlb": [
        "https://api.sportsdata.io/v3/mlb/scores/json/PlayersByActive",
        "https://api.sportsdata.io/v3/mlb/scores/json/PlayersByFreeAgents",
        "https://api.sportsdata.io/v3/mlb/scores/json/teams",
        "https://api.sportsdata.io/v3/mlb/scores/json/ScoresBasicFinal/{date}",
        "https://api.sportsdata.io/v3/mlb/odds/json/BettingMarketsByGameID/{gameID}",
        "https://api.sportsdata.io/v3/mlb/projections/json/BakerPlayerGameProjections/{date}",
        "https://baker-api.sportsdata.io/baker/v2/mlb/projections/players/full-season/{season_name}/avg",
        "https://baker-api.sportsdata.io/baker/v2/mlb/trends/{date}/{team}",
        "https://baker-api.sportsdata.io/baker/v2/mlb/trends/{date}/players/{playerid}",
    ],
    "nfl": [],
}

# Table descriptions for SQL query generation (used in determine_sql_query)
TABLE_DESCRIPTIONS = {
    "mlb": """
Tables/Columns:
TABLE: battingstatsgame
COLUMNS: stat_id, player_team_id, player_id, season_type (1 for regular season, 3 for postseason), season, name, player_team_abbreviation, position, position_category, started, batting_order, injury_status, injury_body_part, injury_start_date, injury_notes, game_id, opponent_team_id, opponent_team_abbreviation, day_of_week, date_time, home_or_away (HOME/AWAY), fantasy_points, at_bats, runs, hits, singles, doubles, triples, homeruns, rbis, batting_average, outs, strikeouts, walks, times_hit_by_pitch, sacrifices, sacrifice_flies, grounded_into_double_plays, stolen_bases, times_caught_stealing, pitches_seen, on_base_percentage, slugging_percentage, on_base_plus_slugging, errors, grand_slams, plate_appearances, total_bases, flyouts, groundouts, lineouts, popouts, intentional_walks, reached_on_error, balls_in_play, batting_average_on_balls_in_play, weighted_on_base_percentage, double_plays, isolated_power, total_batters_left_on_base, pinch_hit_batting_order, pinch_hit_appearance_sequence, player_team_runs, opponent_team_runs, is_win (boolean)

TABLE: pitchingstatsgame
COLUMNS: stat_id, player_team_id, player_id, season_type (1 for regular season, 3 for postseason), season, name, player_team_abbreviation, position, position_category, started, injury_status, injury_body_part, injury_start_date, injury_notes, game_id, opponent_team_id, opponent_team_abbreviation, day_of_week, date_time, home_or_away (HOME/AWAY), fantasy_points, errors, pitching_wins, pitching_losses, pitching_saves, innings_pitched_decimal, total_outs_pitched, innings_pitched_full, innings_pitched_outs, earned_run_average, pitching_hits, pitching_runs, pitching_earned_runs, pitching_walks, pitching_strikeouts, pitching_home_runs, pitches_thrown, pitches_thrown_strikes, walks_hits_per_innings_pitched, pitching_batting_average_against, pitching_singles_allowed, pitching_doubles_allowed, pitching_triples_allowed, pitching_grand_slams_allowed, pitching_hit_by_pitch_allowed, pitching_sacrifices_allowed, pitching_sacrifice_flies_allowed, pitching_grounded_into_double_plays_allowed, pitching_complete_games, pitching_shutouts, pitching_no_hitters, pitching_perfect_games, pitching_plate_appearances_allowed, pitching_total_bases_allowed, pitching_flyouts_allowed, pitching_groundouts_allowed, pitching_lineouts_allowed, pitching_popouts_allowed, pitching_intentional_walks_allowed, pitching_reached_on_error_allowed, pitching_catchers_interference_allowed, pitching_balls_in_play_allowed, pitching_on_base_percentage, pitching_slugging_percentage, pitching_on_base_plus_slugging, pitching_strikeouts_per_nine_innings, pitching_walks_per_nine_innings, pitching_batting_average_on_balls_in_play, pitching_weighted_on_base_percentage, pitching_double_plays_allowed, fielding_independent_pitching, pitching_quality_starts, pitching_inning_started, pitching_holds, pitching_blown_saves, player_team_runs, opponent_team_runs, is_win (boolean)

TABLE: teamstatsgame
COLUMNS: stat_id, team_id, season_type (1 for regular season, 3 for postseason), season, team_name, team_abbreviation, game_id, opponent_team_id, opponent_team_abbreviation, day_of_week, date_time, home_or_away (HOME/AWAY), fantasy_points, at_bats, runs, hits, singles, doubles, triples, homeruns, rbis, batting_average, outs, strikeouts, walks, times_hit_by_pitch, sacrifices, sacrifice_flies, grounded_into_double_plays, stolen_bases, times_caught_stealing, pitches_seen, on_base_percentage, slugging_percentage, on_base_plus_slugging, errors, wins, losses, saves, innings_pitched_decimal, total_outs_pitched, innings_pitched_full, innings_pitched_outs, earned_run_average, pitching_hits, pitching_runs, pitching_earned_runs, pitching_walks, pitching_strikeouts, pitching_home_runs, pitches_thrown, pitches_thrown_strikes, walks_hits_per_innings_pitched, pitching_batting_average_against, grand_slams, plate_appearances, total_bases, flyouts, groundouts, lineouts, popouts, intentional_walks, reached_on_error, balls_in_play, batting_average_on_balls_in_play, weighted_on_base_percentage, pitching_singles_allowed, pitching_doubles_allowed, pitching_triples_allowed, pitching_grand_slams_allowed, pitching_hit_by_pitch_allowed, pitching_sacrifices_allowed, pitching_sacrifice_flies_allowed, pitching_grounded_into_double_plays_allowed, pitching_complete_games, pitching_shutouts, pitching_no_hitters, pitching_perfect_games, pitching_plate_appearances, pitching_total_bases, pitching_flyouts, pitching_groundouts, pitching_lineouts, pitching_popouts, pitching_intentional_walks, pitching_reached_on_error, pitching_catchers_interference, pitching_balls_in_play, pitching_on_base_percentage, pitching_slugging_percentage, pitching_on_base_plus_slugging, pitching_strikeouts_per_nine_innings, pitching_walks_per_nine_innings, pitching_batting_average_on_balls_in_play, pitching_weighted_on_base_percentage, double_plays, pitching_double_plays_allowed, isolated_power, fielding_independent_pitching, pitching_quality_starts, total_batters_left_on_base, pitching_holds, pitching_blown_saves, is_win (boolean)

TABLE: battingstatsseason
COLUMNS: stat_id, player_team_id, player_id, season_type (1 for regular season, 3 for postseason), season, name, player_team_abbreviation, position, position_category, started, games, fantasy_points, at_bats, runs, hits, singles, doubles, triples, homeruns, rbis, batting_average, outs, strikeouts, walks, times_hit_by_pitch, sacrifices, sacrifice_flies, grounded_into_double_plays, stolen_bases, times_caught_stealing, num_pitches_seen, on_base_percentage, slugging_percentage, on_base_plus_slugging, errors, grand_slams, plate_appearances, total_bases, flyouts, groundouts, lineouts, popouts, intentional_walks, reached_on_error, balls_in_play, batting_average_on_balls_in_play, weighted_on_base_percentage, double_plays, isolated_power, total_batters_left_on_base

TABLE: pitchingstatsseason
COLUMNS: stat_id, player_team_id, player_id, season_type (1 for regular season, 3 for postseason), season, name, player_team_abbreviation, position, position_category, started, games, fantasy_points, pitching_wins, pitching_losses, pitching_saves, innings_pitched_decimal, total_outs_pitched, innings_pitched_full, innings_pitched_outs, earned_run_average, pitching_hits, pitching_runs, pitching_earned_runs, pitching_walks, pitching_strikeouts, pitching_home_runs, pitches_thrown, pitches_thrown_strikes, walks_hits_per_innings_pitched, pitching_batting_average_against, pitching_complete_games, pitching_shut_outs, pitching_hit_by_pitch_allowed, pitching_sacrifices_allowed, pitching_sacrifice_flies_allowed, pitching_grounded_into_double_plays_allowed, pitching_no_hitters, pitching_perfect_games, pitching_plate_appearances, pitching_total_bases, pitching_fly_outs, pitching_ground_outs, pitching_line_outs, pitching_pop_outs, pitching_intentional_walks, pitching_reached_on_error, pitching_catchers_interference, pitching_balls_in_play, pitching_on_base_percentage, pitching_slugging_percentage, pitching_on_base_plus_slugging, pitching_strikeouts_per_nine_innings, pitching_walks_per_nine_innings, pitching_batting_average_on_balls_in_play, pitching_weighted_on_base_percentage, pitching_double_plays_allowed, fielding_independent_pitching, pitching_quality_starts, pitching_inning_started, pitching_holds, pitching_blown_saves

TABLE: teamstatsseason
COLUMNS: stat_id, team_id, season_type (1 for regular season, 3 for postseason), season, team_name, team_abbreviation, games, fantasy_points, at_bats, runs, hits, singles, doubles, triples, homeruns, rbis, batting_average, outs, strikeouts, walks, times_hit_by_pitch, sacrifices, sacrifice_flies, grounded_into_double_plays, stolen_bases, times_caught_stealing, pitches_seen, on_base_percentage, slugging_percentage, on_base_plus_slugging, errors, wins, losses, saves, innings_pitched_decimal, total_outs_pitched, innings_pitched_full, innings_pitched_outs, earned_run_average, pitching_hits, pitching_runs, pitching_earned_runs, pitching_walks, pitching_strikeouts, pitching_home_runs, pitches_thrown, pitches_thrown_strikes, walks_hits_per_innings_pitched, pitching_batting_average_against, grand_slams, plate_appearances, total_bases, flyouts, groundouts, lineouts, popouts, intentional_walks, reached_on_error, balls_in_play, batting_average_on_balls_in_play, weighted_on_base_percentage, pitching_singles_allowed, pitching_doubles_allowed, pitching_triples_allowed, pitching_grand_slams_allowed, pitching_hit_by_pitch_allowed, pitching_sacrifices_allowed, pitching_sacrifice_flies_allowed, pitching_grounded_into_double_plays_allowed, pitching_complete_games, pitching_shutouts, pitching_no_hitters, pitching_perfect_games, pitching_plate_appearances, pitching_total_bases, pitching_flyouts, pitching_groundouts, pitching_lineouts, pitching_popouts, pitching_intentional_walks, pitching_reached_on_error, pitching_catchers_interference, pitching_balls_in_play, pitching_on_base_percentage, pitching_slugging_percentage, pitching_on_base_plus_slugging, pitching_strikeouts_per_nine_innings, pitching_walks_per_nine_innings, pitching_batting_average_on_balls_in_play, pitching_weighted_on_base_percentage, double_plays, pitching_double_plays_allowed, batting_order_confirmed, isolated_power, fielding_independent_pitching, pitching_quality_starts, pitching_inning_started, total_batters_left_on_base, pitching_holds, pitching_blown_saves

TABLE: playersmetadata
COLUMNS: player_id, player_team_id, player_team_abbreviation, jersey, position_category, position, first_name, last_name, bat_hand, throw_hand, height, weight, birth_date, birth_city, birth_state, birth_country, high_school, college, pro_debut, salary, experience

TABLE: teamsmetadata
COLUMNS: team_id, team_abbreviation, active, city, name, stadium_id, league, division, primary_color, secondary_color, tertiary_color, quaternary_color, wikipedia_logo_url, wikipedia_wordmark_url, head_coach, hitting_coach, pitching_coach

TABLE: games
COLUMNS: game_id, season, season_type (1 for regular season, 3 for postseason), status, day, date_time, away_team_abbreviation, home_team_abbreviation, away_team_id, home_team_id, stadium_id, channel, final_inning, final_inning_half, away_team_runs, home_team_runs, away_team_hits, home_team_hits, away_team_errors, home_team_errors, winning_pitcher_id, losing_pitcher_id, saving_pitcher_id, attendance, away_team_starting_pitcher_id, home_team_starting_pitcher_id, forecast_temp_low, forecast_temp_high, forecast_description, forecast_wind_chill, forecast_wind_speed, forecast_wind_direction, away_team_starting_pitcher_name, home_team_starting_pitcher_name, winning_pitcher_name, losing_pitcher_name, saving_pitcher_name, game_end_date_time, neutral_venue, series_home_team_wins (only non-null for postseason), series_away_team_wins (only non-null for postseason), series_game_number (only non-null for postseason), series_max_length (only non-null for postseason), home_team_opener, away_team_opener, total_runs, home_team_moneyline, away_team_moneyline, home_team_spread, away_team_spread, home_team_spread_odds, away_team_spread_odds, over_under, over_odds, under_odds

TABLE: innings
COLUMNS: inning_id, game_id, inning_number, away_team_abbreviation, home_team_abbreviation, away_team_id, home_team_id, away_team_runs, home_team_runs, season

TABLE: bettingdata
COLUMNS: betting_market_id, betting_outcome_id, open_or_closing_line, sportsbook_id (22 - Consensus, 7 - DraftKings, 8 - FanDuel, 30 - PrizePicks, 41 - Underdog, 24 - BetMGM, 19 - Caesars, 40 - Fanatics, 102 - Pinnacle, 103 - Bovada, 100 - PointsBet, 39 - Circa, 37 - ESPNBet, 43 - ProphetX, 42 - Sleeper, 101 - Tipico), sportsbook_name, betting_market_type_id, betting_market_type, betting_bet_type_id, betting_bet_type, betting_period_type_id, betting_period_type, team_id, team_abbreviation, player_id, player_name, betting_outcome_type_id, betting_outcome_type, payout_american, payout_decimal, value, participant, is_alternate, betting_outcome_created, betting_outcome_updated, betting_outcome_unlisted, units, result

Betting Market Combinations We Have Calculated Units and Results For inside the bettingdata table (If the user doesn't specify a sportsbook, use Consensus always for the lines and odds):
| betting_market_type_id| betting_market_type| betting_bet_type_id | betting_bet_type              | betting_period_type_id| betting_period_type | betting_outcome_type_id| betting_outcome_type |
|-----------------------|--------------------|---------------------|-------------------------------|-----------------------|---------------------|------------------------|----------------------|
| 2                     | Player Prop        | 79                  | Singles                       | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 82                  | Hits Allowed                  | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 45                  | Total Home Runs               | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 45                  | Total Home Runs               | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 181                 | Total Walks                   | 1                     | Full-Game           | 4                      | Under                |
| 1                     | Game Line          | 1                   | Moneyline                     | 1                     | Full-Game           | 1                      | Home                 |
| 1                     | Game Line          | 3                   | Total Runs                    | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 81                  | Total Bases                   | 1                     | Full-Game           | 3                      | Over                 |
| 1                     | Game Line          | 2                   | Spread                        | 1                     | Full-Game           | 1                      | Home                 |
| 2                     | Player Prop        | 180                 | Total Hits, Runs, & RBIs      | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 47                  | Total Hits                    | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 3                   | Total Runs                    | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 66                  | Total Earned Runs Allowed     | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 83                  | Stolen Bases                  | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 85                  | Total Outs Recorded           | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 180                 | Total Hits, Runs, & RBIs      | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 120                 | Total Batting Strikeouts      | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 46                  | Total RBIs                    | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 79                  | Singles                       | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 3                   | Total Runs                    | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 82                  | Hits Allowed                  | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 84                  | Triples                       | 1                     | Full-Game           | 4                      | Under                |
| 1                     | Game Line          | 3                   | Total Runs                    | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 81                  | Total Bases                   | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 120                 | Total Batting Strikeouts      | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 66                  | Total Earned Runs Allowed     | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 181                 | Total Walks                   | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 84                  | Triples                       | 1                     | Full-Game           | 3                      | Over                 |
| 1                     | Game Line          | 1                   | Moneyline                     | 1                     | Full-Game           | 2                      | Away                 |
| 2                     | Player Prop        | 46                  | Total RBIs                    | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 51                  | Total Pitching Strikeouts     | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 133                 | Walks Allowed                 | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 47                  | Total Hits                    | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 133                 | Walks Allowed                 | 1                     | Full-Game           | 4                      | Under                |
| 1                     | Game Line          | 2                   | Spread                        | 1                     | Full-Game           | 2                      | Away                 |
| 2                     | Player Prop        | 85                  | Total Outs Recorded           | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 83                  | Stolen Bases                  | 1                     | Full-Game           | 4                      | Under                |
| 2                     | Player Prop        | 80                  | Doubles                       | 1                     | Full-Game           | 3                      | Over                 |
| 2                     | Player Prop        | 51                  | Total Pitching Strikeouts     | 1                     | Full-Game           | 4                      | Under                |

TABLE: schedules
COLUMNS: game_id, season, season_type (1 for regular season, 3 for postseason), status, day_of_week, date_time, away_team_abbreviation, home_team_abbreviation, away_team_id, home_team_id, stadium_id, game_end_date_time, date_time_utc

TABLE: standings
COLUMNS: season, season_type (1 for regular season, 3 for postseason), team_id, team_abbreviation, city, name, league, division, wins, losses, percentage, division_wins, division_losses, games_behind, last_ten_games_wins, last_ten_games_losses, streak, league_rank, division_rank, wildcard_rank, wildcard_games_behind, home_wins, home_losses, away_wins, away_losses, day_wins, day_losses, night_wins, night_losses, runs_scored, runs_against

TABLE: stadiums
COLUMNS: stadium_id, active, name, city, state, country, capacity, surface, left_field, mid_left_field, left_center_field, mid_left_center_field, center_field, mid_right_center_field, right_center_field, mid_right_field, right_field, geo_latitude, geo_longitude, altitude, home_plate_direction, type
        
Team abbreviations:
NYY, BOS, TOR, BAL, TB, CHW, CLE, DET, MIN, KC, HOU, LAA, ATH, SEA, TEX, NYM, ATL, PHI, MIA, WSH, CHC, MIL, STL, PIT, CIN, LAD, SF, SD, ARI, COL
""",
    "nfl": "",
}

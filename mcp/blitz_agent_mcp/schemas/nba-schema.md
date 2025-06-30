# 🏀 NBA Database Schema Documentation

---
## 🗺️ Overview

This document outlines the structure of the NBA database, including table descriptions, primary keys, common join paths, and interpretation rules for querying player, team, and game data.

---
## 📂 Key Tables

### `players`
- **Description**: Player metadata including name, position, team, and status
- **Primary Key**: `player_id`

### `teams`
- **Description**: Team metadata including name, abbreviation, market
- **Primary Key**: `team_id`

### `games`
- **Description**: Core game data including date, home/away teams, scores, and type
- **Primary Key**: `game_id`

### `schedules`
- **Description**: Official league schedules for each season
- **Primary Key**: `game_id`

### `playerstatsgame`
- **Description**: Player box score statistics per game
- **Primary Key**: (`player_id`, `game_id`)

### `playerstatsperiod`
- **Description**: Player stats by period (quarter, half, OT) per game
- **Primary Key**: (`player_id`, `game_id`, `period_number`)

### `playerstatsseason`
- **Description**: Aggregated player statistics over a season
- **Primary Key**: (`player_id`, `season_id`)

### `playerstatsseries`
- **Description**: Player stats over playoff series
- **Primary Key**: (`player_id`, `series_id`)

### `teamstatsgame`
- **Description**: Team box score statistics per game
- **Primary Key**: (`team_id`, `game_id`)

### `teamstatsperiod`
- **Description**: Team stats by period (quarter, half, OT) per game
- **Primary Key**: (`team_id`, `game_id`, `period_number`)

### `teamstatsseason`
- **Description**: Aggregated team statistics over a season
- **Primary Key**: (`team_id`, `season_id`)

### `teamstatsseries`
- **Description**: Team stats over playoff series
- **Primary Key**: (`team_id`, `series_id`)

### `injuries`
- **Description**: Injury logs for players
- **Primary Key**: (`player_id`, `game_id`)

### `standings`
- **Description**: Win/loss records and standings per team per season
- **Primary Key**: (`season_id`, `team_id`)

### `coaches`
- **Description**: Coaching assignments per game
- **Primary Key**: (`team_id`, `game_id`, `coach_id`)

### `officials`
- **Description**: Referee assignments per game
- **Primary Key**: (`official_id`, `game_id`)

### `venues`
- **Description**: Arena information
- **Primary Key**: `venue_id`

### `broadcasts`
- **Description**: Broadcast info by game and network
- **Primary Key**: (`game_id`, `network`)

### `playbyplay`
- **Description**: Sequential in-game events
- **Primary Key**: (`game_id`, `event_number`)

### `leagueleaders`
- **Description**: Current stat leaders for active season
- **Primary Key**: (`season_id`, `stat_category`, `player_id`)

### `rankings`
- **Description**: Weekly team rankings (e.g., power rankings)
- **Primary Key**: (`week_id`, `team_id`)

### `seasons`
- **Description**: Metadata on each NBA season (start/end dates, type)
- **Primary Key**: `season_id`

---
## 🧠 Query Interpretation Rules

1. **All Must Satisfy by Default**:  
   Queries like *“Do the top 3 scorers score 20+?”* are interpreted as **all three** players must reach the threshold unless the user explicitly says "any".

2. **AND Is the Default Logic**:  
   When multiple conditions are given (e.g., “player scores 30 and team wins”), assume **AND logic**, not conditional probabilities or independent stats.

3. **Don't Split Conditional Logic**:  
   If a query includes a condition (e.g., "when Player A scores 20+, what’s Team B’s win rate?"), evaluate within the **same game context** — do not break into separate subqueries and combine.

4. **Regular Season by Default**:  
   Unless stated, assume queries refer to **regular season games only**.

5. **Use Full Name Matching Without Special Characters**:  
   Normalize special characters (e.g., “Luka Dončić” → “Luka Doncic”) to match database-stored values.

6. **Default to Per-Game Averages**:  
   If a stat is requested without a timeframe, return the **per-game average**, not total.

7. **Most Recent Season or Game**:  
   If no season or date is given, use the **latest full season** or most recent available game logs.

8. **Ignore Case and Formatting in Names**:  
   Player/team identifiers are case-insensitive (e.g., “BOS”, “bos”, “Bos” all match Boston).

9. **More is Better**:  
   When in doubt, **select more information** (player names, team, opponent, date, location) than the query directly requests — for better clarity and analysis.

10. **Use `playbyplay` only for event-level breakdowns**:  
   Don’t use `playbyplay` unless the user explicitly asks for sequential actions (e.g., first bucket, clutch shot).

11. **Cumulative stat questions**:
   Assume each individual meets the threshold, e.g., "Frequency three starters go over 20 points" means all three did, not a combined 20.

12. **Player / Team Performance**: Assume user means only in games where that player or team is playing
   For example, for: what percent of the time do the warriors win and Curry scores 30+?, ee implicitly assume the user wants to filter out games where Curry did not play. 


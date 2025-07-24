# 🏀 NBA Database Schema Documentation
This document provides comprehensive information about the historical NBA database schema, including table descriptions, primary keys, query interpretation rules, and what types of questions can or cannot be answered using the data. The database contains data until yesterday but nothing live/in the future.

---
## 📊 Important Stats (for Sanity)

A quick reference to help ground expectations and guide query interpretation.

1. **Data Coverage:**  
   Includes NBA games from **2013 through 2025**.

2. **Games per Team per Year:**  
   Each team plays **82 regular season games per season**. However, since each game involves two teams, there are **~1230 unique games per regular season**.

3. **Total Game Count (2013–2025):**  
   Roughly **14,700+ unique games** across all seasons.

4. **Teams:**  
   30 NBA teams across both divisions.

5. **Players per Team per Game:**  
   Each team has 5 players who starts a game, with a team typically substituting up to an additional 10 players in the game, leading to **5–15 total player appearances** per team per game

6. **Stat Granularity:**  
   - **Game-level stats:** One row per game  
   - **Team-level stats:** One row per team per game (2 per game)  
   - **Player-level stats:** One row per player per game (batting/pitching)  
   - **Period-level stats:** One row per player/team per quarter

7. **Season Length Consideration:**  
   Strike-shortened or COVID seasons (e.g., 2020) may have fewer games.

8. **Playoffs:**  
   Postseason games are included and flagged via `season_type = PST`. These are a small fraction (~2%) of total games.

9. **Time Zones:**  
   Game start times are normalized to **Eastern Time** unless otherwise specified.

Use this section to validate scale and interpret frequency-based queries with realistic denominators.

---
## 🧠 Query Interpretation Rules

1. **All Must Satisfy by Default**:  
   Queries like *“Do the top 3 scorers score 20+?”* are interpreted as **all three** players must reach the threshold unless the user explicitly says "any".

2. **AND Is the Default Logic**:  
   When multiple conditions are given (e.g., “player scores 30 and team wins”), assume **AND logic**, not conditional probabilities or independent stats.

3. **Duplicate players**:
   If a user asks a question that involves a player with a common name, first find the player inside playersmetadata to make sure there aren't multiple players with the same name. If there are, then assume who they are talking about with other context clues or make sure you say you figure out which one they are talking about before executing the query

3. **Don't Split Conditional Logic**:  
   If a query includes a condition (e.g., "when Player A scores 20+, what’s Team B’s win rate?"), evaluate within the **same game context** — do not break into separate subqueries and combine.

4. **Regular Season and Postseason by Default**:  
   Unless stated, assume queries refer to **regular season and post season games only**.

5. **Use Full Name Matching Without Special Characters**:  
   Normalize special characters (e.g., “Luka Dončić” → “Luka Doncic”) to match database-stored values.

6. **Default to Per-Game Averages**:  
   If a stat is requested without a timeframe, return the **per-game average**, not total.

7. **Most Recent Season or Game**:  
   If no season or date is given, use the **latest season** or most recent available game logs. Any phrasing such as "this year" should also refer to the most recent basketball season, even if its the prior year. 

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

13. **Include Games with Valid Data Only**  
   If a required column (e.g., `assists`, `minutes`) is missing for a given player/game and is essential to answering the question **exclude the game from the result**, but **do not treat it as a failure**. 
   > Useful for maintaining denominator integrity

14. **Default to the Consensus lines if the user asks a question that requires a sportsbook and doesn't specify which one to use for betting lines/odds**


15. **Questions involving multiple players in the same game have an implicit condition that both players played in that game**
    > **Example**:  
    > *"How often does Stephen Curry score 30+ and Draymond Green have 10+ assists?"*  
    >  
    > **Interpretation**:  
    > Only consider games where **both Curry and Draymond** played.  
    > If either player did not appear in the game, exclude it from the calculation.  
    > Then evaluate whether Curry had ≥ 30 points **and** Draymond had ≥ 10 assists in the game

16. **When possible, results should have a summary row that answers the question, then example rows with relevant information below**

> **Example**:  
> The first row is a summary (aggregates), and the rows below are individual examples that met the success condition.

   | row_type | game_id                             | curry_points | dray_assists | total_successes | total_failures | success_percentage | outcome  |
   |----------|--------------------------------------|--------------|--------------|------------------|----------------|---------------------|----------|
   | summary  | NULL                                 | NULL         | NULL         | 125              | 186            | 40.19               | NULL     |
   | example  | 006e8283-2bc4-4db7-80a2-3ebbffe...    | 37           | 8            | NULL             | NULL           | NULL                | success  |
   | example  | 011d3114-b08a-466d-8a19-8dbbe6...     | 31           | 14           | NULL             | NULL           | NULL                | success  |
   | example  | 04ebb0fd-f8af-4871-820d-1f28a7...     | 51           | 12           | NULL             | NULL           | NULL                | success  |
   | example  | 05398bab-fb3a-48be-8500-865504...     | 39           | 10           | NULL             | NULL           | NULL                | success  |
   | ...      | ...                                  | ...          | ...          | ...              | ...            | ...                 | ...      |


---
## 🚫 What You *Cannot* Answer (NBA)

### Data Granularity Limitations:
- **Defender vs shooter matchups** – You cannot isolate how Player A defends Player B on specific possessions
- **Defensive assignments** – No information on who guarded whom during plays
- **Advanced synergy or lineup context** – Can't analyze how specific 5-man lineups perform together per possession

### Technical Limitations:
- **Live game data or real-time stats** – No access to ongoing or just-finished games

### Invalid Analysis Patterns:
- ❌ "How does Jrue Holiday defend Jalen Brunson in clutch moments?" (no defender-vs-offensive player context)
- ✅ "How does Jalen Brunson perform in games decided by fewer than 5 points?" (valid game-level stat filter)
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

### `officials`
- **Description**: Referee assignments per game
- **Primary Key**: (`official_id`)

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



# ⚾ MLB Database Schema Documentation

This document provides comprehensive information about the historical MLB database schema, including table descriptions, primary keys, query interpretation rules, and what types of questions can or cannot be answered using the data. The database contains data until yesterday but nothing live/in the future.

---
## 📊 Important Stats (for Sanity)

A quick reference to help ground expectations and guide query interpretation.

1. **Data Coverage:**  
   Includes MLB games from **2012 through 2025**.

2. **Games per Team per Year:**  
   Each team plays **162 games per season**. However, since each game involves two teams, there are **~2,430 unique games per regular season**.

3. **Total Game Count (2012–2025):**  
   Roughly **31,000+ unique games** across all seasons.

4. **Teams:**  
   30 MLB teams across both leagues.

5. **Players per Team per Game:**  
   Typically 9 starting batters and 1 starting pitcher, with substitutions leading to **15–20 total player appearances** per team per game.

6. **Stat Granularity:**  
   - **Game-level stats:** One row per game  
   - **Team-level stats:** One row per team per game (2 per game)  
   - **Player-level stats:** One row per player per game (batting/pitching)  
   - **Inning-level stats:** One row per team per inning (18 per game)

7. **Season Length Consideration:**  
   Strike-shortened or COVID seasons (e.g., 2020) may have fewer games.

8. **Playoffs:**  
   Postseason games are included and flagged via `season_type = 3`. These are a small fraction (~1–2%) of total games.

9. **Time Zones:**  
   Game start times are normalized to **Eastern Time** unless otherwise specified.

Use this section to validate scale and interpret frequency-based queries with realistic denominators.

---
## 🧠 Query Rules

To ensure consistency and accuracy in answering questions against the MLB database, the following rules apply when interpreting user queries:

1. **Be Precise About Denominators**: MOST IMPORTANT RULE
   Always clarify *what unit of measurement* is being used when calculating percentages—this could be **games**, **teams**, **players**, **innings**, or another appropriate denominator. Whenever a user asks "What percent of the time..." or "How often..." make "total_times" one of the column names!

   > For example, if the user asks:  
   > ❓ *“What percent of the time does the leadoff batter score a run?”*  
   > ✅ The correct denominator is **times** not **games**, since each team’s leadoff hitter is a separate instance per game (2 per game).  

   > ❓ *“What percent of games have at least two home runs?”*  
   > ✅ The correct denominator is **games**, because the event is checked once per full game.

   **✅ Good Practice:**  
   Use denominator names like `total_events`, `total_times`, or `total_games` to reflect what’s being counted.

   **❌ Common Pitfall:**  
   Avoid using a misleading denominator like `total_games` when there are multiple qualifying rows per game (e.g., multiple players per team or checking a condition for both teams of a single game).

   **Key Principle:**  
   > One row = one check = one count in the denominator.  
   > Don’t mix units (e.g., player-level filters with game-level denominators) unless the logic demands it and is explicitly stated.

2. **"All" Interpretation**:  
   If a user asks a question involving multiple players or events (e.g., *“What percent of the time do the first three batters get a run?”*), assume they mean **all of the entities must satisfy the condition**, **not just any**.  
   > ✅ Means: *All three batters scored a run*  
   > ❌ Not: *At least one of the three batters scored a run*

3. **"And" is Always the Default**: EXTREMELY IMPORTANT
   If multiple conditions are presented (e.g., *“How often does a pitcher throw 100+ pitches and the team loses?”*), interpret the question using logical **AND** unless the user explicitly specifies **OR** or conditional probability.  
   > ✅ Means: *Time where a pitcher threw 100+ pitches **and** the their team lost*  
   > ❌ Not: *Given the pitcher threw 100+ pitches, what percent did the team lose*
   > EXPLICITLY MENTION THIS IN YOUR RESPONSE

4. **NEVER Split Conditional Queries Into Multiple Subqueries**:  
   If a query includes a conditional clause (e.g., *“What percent of the time do the first three batters score and there was a run scored in the first inning?”*), do **not** compute each part separately and combine them.  
   > Always evaluate the condition within the **same row/game context**.

5. **Special Characters Handling**:  
   Player and team names may contain special characters (e.g., accents or unicode dashes). In queries, **strip or normalize** special characters because the database stores **escaped or ASCII-normalized** values.  
   > E.g., `"José Ramírez"` → `"Jose Ramirez"`

6. **More is Better**:  
   When querying, **select more contextual information** than the prompt explicitly requests. This includes:
   - Player/team metadata (e.g., name, team, position)
   - Game details (e.g., date, opponent, score)
   - Stat breakdowns beyond the filtered metric  
   > This ensures better visibility for interpretation and downstream usage, especially in result visualization or correlation analysis.

7. **Implicit Averages**  
   If a user asks *“How many hits does a player get?”* or *“What is a team’s run total?”* without specifying a timeframe, **default to the per-game average** over all available data unless the context clearly implies season totals.  
   > ✅ Assume "hits" = average hits per game  
   > Use season total **only** if user says "in the 2023 season" or similar

8. **Default Scope is Regular + Post Season**  
   Unless otherwise specified, assume **regular season** + **post season**.

9. **Include Games with Valid Data Only**  
   If a required column (e.g., `hits`, `pitches_thrown`) is missing for a given player/game, **exclude the game from the result**, but **do not treat it as a failure**.  
   > Useful for maintaining denominator integrity

10. **Default Sort Order**  
   If a user asks “top 10” or “most,” default to **descending order** on the primary stat of interest (e.g., hits, runs)  
   > Sort `DESC` unless otherwise stated

11. **Ignore Case in Identifiers**  
    Names and team abbreviations should be **case-insensitive**.  
    > Treat `"NYY"` and `"nyy"` as equivalent

12. **Fallback to Latest Data**  
    When no date range is given, default to **most recent full season** or **latest available game logs**  
    > For example, default to 2024 if it’s June 2025 and 2025 is incomplete

13. **Default to the Consensus lines if the user asks a question that requires a sportsbook and doesn't specify which one to use for betting lines/odds**

---
## 🚫 What You *Cannot* Answer

### Data Granularity Limitations:
- **Individual pitcher vs batter matchups** - You cannot analyze how Pitcher A performed against Batter B specifically
- **Situational analysis** - No data on runners on base, count situations, outs, inning-specific contexts
- **Play-by-play or pitch-by-pitch data** - No individual at-bat outcomes
- **Within-game sequencing** - Cannot determine when events occurred during the game
- **Clutch performance** - No data on high-leverage situations, runners in scoring position, etc.
- **Batting order vs pitcher** - Cannot correlate specific batting positions with individual pitcher performance

### Technical Limitations:
- Live game data or in-play outcomes
- Statcast-level data (e.g., exit velocity, launch angle)
- **Cross-game correlations that require situational context**

### Invalid Analysis Patterns:
- ❌ "How do relief pitchers perform against speed threats?" (can't isolate which batters faced which pitchers)
- ❌ "Pitcher performance in clutch situations" (no situational data available)
- ❌ "How do pitchers perform against opposite-handed batters?" (can't isolate specific matchups within games)
- ✅ "How do relief pitchers perform in games where the opposing team has many stolen bases?" (valid game-level analysis)

---
## 📂 Key Tables

### `battingstatsgame`
- **Description**: **GAME-LEVEL AGGREGATED** hitting statistics for each batter per game. Contains totals for the entire game, NOT individual at-bats or situational data.
- **Primary Key**: (`player_id`, `game_id`)
- **Important**: This table shows how a batter performed across all their plate appearances in a single game, with no breakdown by inning, situation, or opposing pitcher.

### `battingstatsgameprojections`
- **Description**: AI-generated stat projections for batters per game
- **Primary Key**: (`player_id`, `game_id`)

### `battingstatsseason`
- **Description**: Aggregated hitting stats for each batter over a season
- **Primary Key**: (`player_id`, `season`)

### `battingstatsseasonsplits`
- **Description**: Season-long batting splits by pitcher handedness
- **Primary Key**: (`player_id`, `season`, `split`)

### `pitchingstatsgame`, `pitchingstatsgameprojections`, `pitchingstatsseason`, `pitchingstatsseasonsplits`
- **Description**: Analogous tables to batting, for pitching stats
- **Primary Keys**:
  - `pitchingstatsgame`: (`player_id`, `game_id`)
  - `pitchingstatsgameprojections`: (`player_id`, `game_id`)
  - `pitchingstatsseason`: (`player_id`, `season`)
  - `pitchingstatsseasonsplits`: (`player_id`, `season`, `split`)

### `teamstatsgame`
- **Description**: Aggregated per-game team stats
- **Primary Key**: (`team_id`, `game_id`)

### `teamstatsseason`
- **Description**: Aggregated per-season team stats
- **Primary Key**: (`team_id`, `season`)

### `playersmetadata`
- **Description**: Static player info such as name, handedness, position
- **Primary Key**: `player_id`

### `teamsmetadata`
- **Description**: Static team info such as abbreviation, full name, market
- **Primary Key**: `team_id`

### `games`
- **Description**: Core game metadata (date, teams, final score, etc.)
- **Primary Key**: `game_id`

### `innings`
- **Description**: Runs scored by each team in each inning
- **Primary Key**: (`game_id`, `inning_number`)

### `bettingdata`
- **Description**: Historical betting odds, props, and lines from sportsbooks
- **Primary Key**: (`betting_market_id`, `open_or_closing_line`, `sportsbook_id`, `betting_market_type_id`, `betting_bet_type_id`, `betting_period_type_id`, `betting_outcome_type_id`)

### `schedules`
- **Description**: Official game schedule
- **Primary Key**: (`game_id`)

### `standings`
- **Description**: Team standings for a given season
- **Primary Key**: (`season`, `team_id`)

### `stadiums`
- **Description**: Ballpark metadata (e.g., location, altitude, team home park)
- **Primary Key**: `stadium_id`

---
## 📊 Betting Market Mapping (`bettingdata`)

| MarketTypeID | MarketType   | BetTypeID | BetType                    | PeriodTypeID | Period       | OutcomeTypeID | Outcome     |
|--------------|--------------|-----------|----------------------------|---------------|--------------|----------------|--------------|
| 1            | Game Line    | 1         | Moneyline                  | 1             | Full-Game    | 1              | Home         |
| 1            | Game Line    | 2         | Spread                     | 1             | Full-Game    | 1              | Home         |
| 1            | Game Line    | 2         | Spread                     | 1             | Full-Game    | 2              | Away         |
| 1            | Game Line    | 3         | Total Runs                 | 1             | Full-Game    | 3              | Over         |
| 1            | Game Line    | 3         | Total Runs                 | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 3         | Total Runs                 | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 3         | Total Runs                 | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 45        | Total Home Runs            | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 45        | Total Home Runs            | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 46        | Total RBIs                 | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 46        | Total RBIs                 | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 47        | Total Hits                 | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 47        | Total Hits                 | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 51        | Total Pitching Strikeouts  | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 51        | Total Pitching Strikeouts  | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 66        | Total Earned Runs Allowed  | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 66        | Total Earned Runs Allowed  | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 79        | Singles                    | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 79        | Singles                    | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 80        | Doubles                    | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 81        | Total Bases                | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 81        | Total Bases                | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 82        | Hits Allowed               | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 82        | Hits Allowed               | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 83        | Stolen Bases               | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 83        | Stolen Bases               | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 84        | Triples                    | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 84        | Triples                    | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 85        | Total Outs Recorded        | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 85        | Total Outs Recorded        | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 120       | Total Batting Strikeouts   | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 120       | Total Batting Strikeouts   | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 133       | Walks Allowed              | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 133       | Walks Allowed              | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 180       | Total Hits, Runs, & RBIs   | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 180       | Total Hits, Runs, & RBIs   | 1             | Full-Game    | 4              | Under        |
| 2            | Player Prop  | 181       | Total Walks                | 1             | Full-Game    | 3              | Over         |
| 2            | Player Prop  | 181       | Total Walks                | 1             | Full-Game    | 4              | Under        |

from typing import List, Tuple, Optional, Union, Dict
from datetime import datetime, timedelta, date
from urllib.error import HTTPError
from dotenv import load_dotenv  # type: ignore
import lightgbm as lgb  # type: ignore
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import statsapi  # type: ignore
import contextlib
import subprocess
import pickle
import time
import json
import os
import io

IDS = [
    "id_to_team",
    "team_to_id",
    "team_to_abbreviation",
    "league_dict",
    "division_teams",
    "division_to_id",
    "id_to_division",
]

# to satisfy type checker...
id_to_team: Dict[str, str] = {}
team_to_id: Dict[str, str] = {}
team_to_abbreviation: Dict[str, str] = {}
league_dict: Dict[str, int] = {}
division_teams: Dict[str, List[str]] = {}
division_to_id: Dict[str, int] = {}
id_to_division: Dict[int, str] = {}

cwd = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# feature orders
order1 = [
    "home-win-percentage",
    "away-win-percentage",
    "home-starter-season-era",
    "away-starter-season-era",
    "home-starter-season-win-percentage",
    "away-starter-season-win-percentage",
    "home-top5-hr-avg",
    "away-top5-hr-avg",
    "home-last10-avg-runs",
    "away-last10-avg-runs",
    "home-last10-avg-ops",
    "away-last10-avg-ops",
    "home-starter-season-whip",
    "away-starter-season-whip",
    "home-top5-rbi-avg",
    "away-top5-rbi-avg",
    "home-last10-avg-runs-allowed",
    "away-last10-avg-runs-allowed",
    "home-starter-season-avg",
    "away-starter-season-avg",
    "home-top5-batting-avg",
    "away-top5-batting-avg",
    "home-starter-season-strike-percentage",
    "away-starter-season-strike-percentage",
    "home-last10-avg-hits",
    "away-last10-avg-hits",
    "home-last10-avg-hits-allowed",
    "away-last10-avg-hits-allowed",
    "home-last10-avg-obp",
    "away-last10-avg-obp",
    "home-last10-avg-avg",
    "away-last10-avg-avg",
    "home-last10-avg-rbi",
    "away-last10-avg-rbi",
    "home-starter-season-runs-per9",
    "away-starter-season-runs-per9",
    "home-top5-stolenBases-avg",
    "away-top5-stolenBases-avg",
    "home-top5-totalBases-avg",
    "away-top5-totalBases-avg",
    "home-last10-avg-strikeouts",
    "away-last10-avg-strikeouts",
    "home-starter-career-era",
    "away-starter-career-era",
]
order2 = [
    "home-win-percentage",
    "home-starter-season-era",
    "home-starter-season-win-percentage",
    "home-top5-hr-avg",
    "home-last10-avg-runs",
    "home-last10-avg-ops",
    "home-starter-season-whip",
    "home-top5-rbi-avg",
    "home-last10-avg-runs-allowed",
    "home-starter-season-avg",
    "home-top5-batting-avg",
    "home-starter-season-strike-percentage",
    "home-last10-avg-hits",
    "home-last10-avg-hits-allowed",
    "home-last10-avg-obp",
    "home-last10-avg-avg",
    "home-last10-avg-rbi",
    "home-starter-season-runs-per9",
    "home-top5-stolenBases-avg",
    "home-top5-totalBases-avg",
    "home-last10-avg-strikeouts",
    "home-starter-career-era",
    "away-win-percentage",
    "away-starter-season-era",
    "away-starter-season-win-percentage",
    "away-top5-hr-avg",
    "away-last10-avg-runs",
    "away-last10-avg-ops",
    "away-starter-season-whip",
    "away-top5-rbi-avg",
    "away-last10-avg-runs-allowed",
    "away-starter-season-avg",
    "away-top5-batting-avg",
    "away-starter-season-strike-percentage",
    "away-last10-avg-hits",
    "away-last10-avg-hits-allowed",
    "away-last10-avg-obp",
    "away-last10-avg-avg",
    "away-last10-avg-rbi",
    "away-starter-season-runs-per9",
    "away-top5-stolenBases-avg",
    "away-top5-totalBases-avg",
    "away-last10-avg-strikeouts",
    "away-starter-career-era",
]


class LeagueStats:
    def __init__(self):
        self.retrieve_ids(IDS)

    def retrieve_ids(self, variables: List[str]) -> None:
        """
        method to retrieve ids and translation data from the ids.json file
            -> generates that file if needed

        Args:
            variables: List of strings of identifiers to retrieve
        """
        ids_filepath = os.path.join(cwd, "data/ids.json")
        script_path = os.path.join(cwd, "data/generate_ids.py")
        if not os.path.isfile(ids_filepath):
            subprocess.run(["python3", script_path])
        with open(ids_filepath, "r") as f:
            data = json.load(f)
        for key in variables:
            if key in data:
                globals()[key] = data[key]

    def get_division(self, team: str) -> Optional[Union[Tuple[str, int], None]]:
        """
        method to get the division of the given team

        Args:
            team: string team name (i.e. "New York mets")

        Returns:
            division name (e.g. "NL East"), division API id (e.g 201)
        """
        for division in division_teams:
            if team in division_teams[division]:
                return division, division_to_id[division]
        return None

    def get_division_standings(
        self, division_id: int, request_date: Optional[str] = None
    ) -> Optional[Union[Dict, None]]:
        """
        method to get current division standings of an MLB team

        Args:
            division_id: id of division to get standings from
            date: date to get standings from

        Retuns:
            standings: python dictionary containing division standings data
        """
        if not request_date:
            request_date = date.today().strftime("%m/%d/%Y")
        standings = statsapi.standings_data("103,104", date=request_date).get(
            division_id
        )
        if standings:
            standings = standings.get("teams")
        return standings

    def get_team_standings(
        self, team_name: str, division_standings: Dict
    ) -> Tuple[int, int, int, Optional[Union[int, str]], int]:
        """
        method to get wins, loses, division rank, div games back, and league rank

        Args:
            team_name: string of team's name (i.e. "New York Mets")
            division_standings: return of get_division_standings() method

        Returns:
            wins: integer number of wins for the season
            loses: integer number of loses for the season
            division rank: integer rank within division
            games back: number of games back behind division leader (if 0 then '-')
            league rank: integer rank within league
        """
        for team in division_standings:
            if team["name"] == team_name:
                win, loss, gb = team["w"], team["l"], team["gb"]
                drank, lrank = team["div_rank"], team["league_rank"]
        return win, loss, drank, gb, lrank

    def get_next_game(
        self, team: str
    ) -> Optional[Union[Tuple[str, Dict], Tuple[None, None]]]:
        """
        method to get data about the team's next unstarted game

        Args:
            team: name of team (e.g. "New York Mets")

        Returns:
            gamePk: id of the team's next to-be-played game
            schedule: python dictionary with game details
        """
        id = team_to_id.get(team)
        if not id:
            return None, None
        gamePk = statsapi.next_game(id)
        next = statsapi.schedule(game_id=gamePk)
        return gamePk, next[0]

    def get_days_games(self, team: str, date: str) -> Optional[List[Dict]]:
        """
        method to get data about a team's games on the given day

        Args:
            team: name of team (e.g. "New York Mets")
            date: date to get games for (MM/DD/YYYY)

        Returns:
            gamePks: id of the team's next to-be-played game
            schedule: python dictionary with game details
        """
        id = team_to_id.get(team)
        if not id:
            return None
        games = statsapi.schedule(start_date=date, end_date=date, team=id)
        return games

    def get_last_game(
        self, team: str
    ) -> Optional[Union[Tuple[str, Dict], Tuple[None, None]]]:
        """
        method to get data about the team's last completed game

        Args:
            team: name of team (e.g. "New York Mets")

        Returns:
            gamePk: id of the team's next to-be-played game
            schedule: python dictionary with game details
        """
        id = team_to_id.get(team)
        if not id:
            return None, None
        gamePk = statsapi.last_game(id)
        next = statsapi.schedule(game_id=gamePk)
        return gamePk, next[0]

    def get_player_id(
        self, player_name: str, season: Optional[str] = None
    ) -> Optional[Union[str, None]]:
        """
        method that will get the id of a player given their name

        Args:
            player_name: a player's name in plain english
            season: season to search for player within

        Returns:
            player_id: a player's id for use with the api as a parameter
        """
        player = statsapi.lookup_player(player_name, season=season)
        if not player:
            return None
        return player[0].get("id")

    def get_starting_pitcher_stats(self, gamePk: str) -> Dict:
        """
        method that will get the required stats about a starting pitcher given a game ID

        Args:
            gamePk: game id of the game to retrieve data from

        Returns:
            starters_stats: python dictionary with stats from both pitchers for a game
                -> era, career era, season era, season avg, ...
                   seasons runs/9, season win percentage,
        """
        starters_stats = {}
        game = statsapi.schedule(game_id=gamePk)[0]
        home_starter, away_starter = (
            game["home_probable_pitcher"],
            game["away_probable_pitcher"],
        )
        season = game["game_date"][0:4]
        for pitcher in [("home", home_starter), ("away", away_starter)]:
            if not pitcher[1]:
                continue
            pitcher_id = self.get_player_id(pitcher[1], season=season)
            if not pitcher_id:
                continue
            seasons = statsapi.player_stat_data(
                pitcher_id, group="pitching", type="yearByYear"
            ).get("stats")
            season_stats = {}
            if seasons:
                for year in seasons:
                    if year["season"] == season:
                        season_stats = year["stats"]
            career_stats = statsapi.player_stat_data(
                pitcher_id, group="pitching", type="career"
            )["stats"]
            if not career_stats:
                continue
            career_stats = career_stats[0]["stats"]
            starters_stats[f"{pitcher[0]}-starter-career-era"] = career_stats.get("era")
            # if no season stats, use career stats in place
            if season_stats:
                starters_stats[f"{pitcher[0]}-starter-season-era"] = season_stats.get("era")
                starters_stats[f"{pitcher[0]}-starter-season-avg"] = season_stats.get("avg")
                starters_stats[f"{pitcher[0]}-starter-season-runs-per9"] = season_stats.get(
                    "runsScoredPer9"
                )
                starters_stats[f"{pitcher[0]}-starter-season-whip"] = season_stats.get("whip")
                starters_stats[
                    f"{pitcher[0]}-starter-season-strike-percentage"
                ] = season_stats.get("strikePercentage")
                try:
                    win_pct = float(season_stats["winPercentage"])
                except ValueError:
                    win_pct = None
                starters_stats[f"{pitcher[0]}-starter-season-win-percentage"] = win_pct
            else: # if season_stats is empty use career stats
                starters_stats[f"{pitcher[0]}-starter-season-era"] = career_stats.get("era")
                starters_stats[f"{pitcher[0]}-starter-season-avg"] = career_stats.get("avg")
                starters_stats[f"{pitcher[0]}-starter-season-runs-per9"] = career_stats.get(
                    "runsScoredPer9"
                )
                starters_stats[f"{pitcher[0]}-starter-season-whip"] = career_stats.get("whip")
                starters_stats[
                    f"{pitcher[0]}-starter-season-strike-percentage"
                ] = career_stats.get("strikePercentage")
                try:
                    win_pct = float(career_stats["winPercentage"])
                except ValueError:
                    win_pct = None
                starters_stats[f"{pitcher[0]}-starter-season-win-percentage"] = win_pct
        return starters_stats

    def get_last10_stats(self, gamePk: str) -> Dict:
        """
        method to get/calculate a team's average stats over the past 10 days

        Args:
            gamePk: game id of the game to retrieve data from

        Returns:
            last10_stats: a python dictionary containing a team's 10 day averages
        """
        last10_stats = {}
        game = statsapi.schedule(game_id=gamePk)[0]
        home, away = game["home_id"], game["away_id"]
        date = datetime.strptime(game["game_date"], "%Y-%m-%d")
        start_date = date - timedelta(days=11)
        end_date = date - timedelta(days=1)
        start, end = start_date.strftime("%m/%d/%Y"), end_date.strftime("%m/%d/%Y")
        for team in [("home", home), ("away", away)]:
            last10daygames = statsapi.schedule(
                team=team[1], start_date=start, end_date=end
            )
            # to ensure only uses regular season or playoff games
            last10daygames = [
                game
                for game in last10daygames
                if game.get("game_type") in ["R", "F", "D", "L", "W", "C", "P"]
            ]
            game_ids = []
            for game in last10daygames:
                game_ids.append(game["game_id"])
            (
                runs,
                runs_allowed,
                hits,
                hits_allowed,
                ops,
                pitching_strikouts,
                pitching_obp,
                avg,
                rbi,
            ) = (0, 0, 0, 0, 0.0, 0, 0.0, 0.0, 0)
            for id in game_ids:
                box = statsapi.boxscore_data(id)
                isHome = box["home"]["team"]["id"] == team[1]
                game_stats = (
                    box["home"]["teamStats"] if isHome else box["away"]["teamStats"]
                )
                runs += game_stats["batting"]["runs"]
                hits += game_stats["batting"]["hits"]
                runs_allowed += game_stats["pitching"]["runs"]
                hits_allowed += game_stats["pitching"]["hits"]
                ops += float(game_stats["batting"]["ops"])
                pitching_strikouts += game_stats["pitching"]["strikeOuts"]
                pitching_obp += float(game_stats["pitching"]["obp"])
                avg += float(game_stats["batting"]["avg"])
                rbi += game_stats["batting"]["rbi"]
            last10_stats[f"{team[0]}-last10-avg-runs"] = (
                runs / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-runs-allowed"] = (
                runs_allowed / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-hits"] = (
                hits / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-hits-allowed"] = (
                hits_allowed / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-ops"] = (
                ops / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-strikeouts"] = (
                pitching_strikouts / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-obp"] = (
                pitching_obp / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-avg"] = (
                avg / len(game_ids) if game_ids else None
            )
            last10_stats[f"{team[0]}-last10-avg-rbi"] = (
                rbi / len(game_ids) if game_ids else None
            )
        return last10_stats

    def get_win_percentage(
        self, gamePk: str
    ) -> Optional[Union[Tuple[float, float], None]]:
        """
        method that will retrieve and calculate a team's winning percentage

        Args:
            gamePk: game id of the game to retrieve data from

        Returns:
            home_pct: home team's winning percentage
            away_pct: away team's winning percentage
        """
        game = statsapi.schedule(game_id=gamePk)[0]
        game_date = game["game_date"]
        date_obj = datetime.strptime(game_date, "%Y-%m-%d")
        game_date = datetime.strftime(date_obj, "%m/%d/%Y")
        home, away = game["home_name"], game["away_name"]
        home_div, away_div = self.get_division(home), self.get_division(away)
        if not home_div or not away_div:
            return None
        h_div, a_div = home_div[1], away_div[1]
        home_standings, away_standings = self.get_division_standings(
            h_div, request_date=game_date
        ), self.get_division_standings(a_div, request_date=game_date)
        if not home_standings or not away_standings:
            return None
        h_wins, h_loses, *_ = self.get_team_standings(home, home_standings)
        a_wins, a_loses, *_ = self.get_team_standings(away, away_standings)
        home_pct = (
            round(h_wins / (h_loses + h_wins), 3) if (h_loses + h_wins) > 0 else 0.000
        )
        away_pct = (
            round(h_wins / (a_loses + a_wins), 3) if (a_loses + a_wins) > 0 else 0.000
        )
        return home_pct, away_pct

    def get_team_leaders(self, gamePk: str) -> Dict:
        """
        method that will retrieve team_leaders in specific stats

        Args:
            gamePk: game id of the game to retrieve data from

        Returns:
            leaders: Dictionary of each team's leaders' stats in key areas
        """
        leaders: Dict = {}
        game = statsapi.schedule(game_id=gamePk)[0]
        home_id, away_id = game["home_id"], game["away_id"]
        season = game["game_date"][0:4]
        for team in [("home", home_id), ("away", away_id)]:
            # if first game of the season, use last season's data
            isFirstGame = True if statsapi.last_game(team[1]) is None else False
            season = (int(season) - 1) if isFirstGame else season

            # average homeruns among top 5 players
            hr = statsapi.team_leader_data(team[1], "homeRuns", season=season)
            top5_hr = [int(item[2]) for item in hr[:5]]
            top5_hr_avg = sum(top5_hr) / len(top5_hr)
            leaders[f"{team[0]}-top5-hr-avg"] = top5_hr_avg

            # average RBI among top 5 players
            rbi = statsapi.team_leader_data(team[1], "runsBattedIn", season=season)
            top5_rbi = [int(item[2]) for item in rbi[:5]]
            top5_rbi_avg = sum(top5_rbi) / len(top5_rbi)
            leaders[f"{team[0]}-top5-rbi-avg"] = top5_rbi_avg

            # average batting avg among top 5 players
            avg = statsapi.team_leader_data(team[1], "battingAverage", season=season)
            top5_avg = [float(item[2]) for item in avg[:5]]
            top5_avg_avg = sum(top5_avg) / len(top5_avg)
            leaders[f"{team[0]}-top5-batting-avg"] = top5_avg_avg

            # average stolen bases among top 5 players
            sb = statsapi.team_leader_data(team[1], "stolenBases", season=season)
            top5_sb = [int(item[2]) for item in sb[:5]]
            top5_sb_avg = sum(top5_sb) / len(top5_sb)
            leaders[f"{team[0]}-top5-stolenBases-avg"] = top5_sb_avg

            # average total bases among top 5 players
            bases = statsapi.team_leader_data(team[1], "totalBases", season=season)
            top5_bases = [int(item[2]) for item in bases[:5]]
            top5_bases_avg = sum(top5_bases) / len(top5_bases)
            leaders[f"{team[0]}-top5-totalBases-avg"] = top5_bases_avg

        return leaders

    def declareDf(self) -> pd.DataFrame:
        """
        method to declare data frame standard format and return an instance of it
        """
        game_df = pd.DataFrame(
            columns=[
                "game-id",
                "date",
                "home-team",
                "away-team",
                "did-home-win",
                "home-win-percentage",
                "away-win-percentage",
                "home-last10-avg-runs",
                "home-last10-avg-runs-allowed",
                "away-last10-avg-runs",
                "away-last10-avg-runs-allowed",
                "home-last10-avg-hits",
                "home-last10-avg-hits-allowed",
                "away-last10-avg-hits",
                "away-last10-avg-hits-allowed",
                "home-last10-avg-ops",
                "away-last10-avg-ops",
                "home-last10-avg-strikeouts",
                "away-last10-avg-strikeouts",
                "home-last10-avg-obp",
                "away-last10-avg-obp",
                "home-last10-avg-avg",
                "away-last10-avg-avg",
                "home-last10-avg-rbi",
                "away-last10-avg-rbi",
                "home-starter-career-era",
                "away-starter-career-era",
                "home-starter-season-era",
                "away-starter-season-era",
                "home-starter-season-avg",
                "away-starter-season-avg",
                "home-starter-season-runs-per9",
                "away-starter-season-runs-per9",
                "home-starter-season-win-percentage",
                "away-starter-season-win-percentage",
                "home-starter-season-whip",
                "away-starter-season-whip",
                "home-starter-season-strike-percentage",
                "away-starter-season-strike-percentage",
                "home-top5-hr-avg",
                "away-top5-hr-avg",
                "home-top5-rbi-avg",
                "away-top5-rbi-avg",
                "home-top5-batting-avg",
                "away-top5-batting-avg",
                "home-top5-stolenBases-avg",
                "away-top5-stolenBases-avg",
                "home-top5-totalBases-avg",
                "away-top5-totalBases-avg",
            ]
        )
        return game_df

    def make_game_df(self, gamePk: str) -> pd.DataFrame:
        """
        method that will construct a data frame for a single game given the game id

        Args:
            gamePk: unique game ID of the game

        Returns:
            game_df: data frame with data points about a specific game
        """
        start_time = time.time()
        game_df = self.declareDf()
        game_df["did-home-win"] = game_df["did-home-win"].astype(bool)
        string_cols = ["date", "home-team", "away-team"]
        game_df[string_cols] = game_df[string_cols].astype(str)
        game = statsapi.schedule(game_id=gamePk)[0]
        game_df.at[0, "did-home-win"] = (
            True
            if game.get("winning_team") == game["home_name"]
            else (False if game.get("winning_team") == game["away_name"] else None)
        )
        game_df.at[0, "date"] = game["game_date"]
        game_df.at[0, "game-id"] = game["game_id"]
        game_df.at[0, "home-team"], game_df.at[0, "away-team"] = (
            game["home_name"],
            game["away_name"],
        )
        ret = self.get_win_percentage(gamePk)
        if ret:
            game_df.at[0, "home-win-percentage"] = ret[0]
            game_df.at[0, "away-win-percentage"] = ret[1]
        last10 = self.get_last10_stats(gamePk)
        for col in last10:
            game_df.at[0, col] = last10[col]
        pitching_stats = self.get_starting_pitcher_stats(gamePk)
        for col in pitching_stats:
            game_df.at[0, col] = pitching_stats[col]
        leaders = self.get_team_leaders(gamePk)
        for col in leaders:
            game_df.at[0, col] = leaders[col]
        function_time = time.time() - start_time
        print(
            f"Constructed training data from {game['summary']}"
            f" in {round(function_time,2)} seconds."
        )
        return game_df

    def get_data(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        file_path: Optional[str] = None,
        save_to_file: Optional[bool] = True,
    ) -> pd.DataFrame:
        """
        method to get historical MLB data for the given team and save it to a file

        Args:
            start_date: first date to start retrieving game data from (YYYY-MM-DD)
            end_date: last date to retrieve game data from (YYYY-MM-DD).
                -> defaults to current day
            file_path: path to save data file to for persistent storage
            save_to_file: bool indicating if you wish the data to be stored

        Returns:
            data: python dataframe with the requested time range game data
        """
        if not end_date:
            end_date = date.today().strftime("%m/%d/%Y")
        if save_to_file:
            formatted_end = end_date.replace("/", "-")
            formatted_start = start_date.replace("/", "-")
            if not file_path:
                file_path = f"./data/mlb{formatted_start}_{formatted_end}.xlsx"
        start_obj = datetime.strptime(start_date, "%m/%d/%Y")
        end_obj = datetime.strptime(end_date, "%m/%d/%Y")
        start_comp = start_obj.strftime("%Y-%m-%d")
        end_comp = end_obj.strftime("%Y-%m-%d")
        start_year = int(start_date[-4:])
        end_year = int(end_date[-4:])
        games = []
        for year in range(start_year, end_year + 1):
            year_start = f"01/01/{year}"
            year_end = f"12/31/{year}"
            possible_games = statsapi.schedule(start_date=year_start, end_date=year_end)
            games.extend(
                [
                    game
                    for game in possible_games
                    if game.get("game_type") in ["R", "F", "D", "L", "W", "C", "P"]
                    and game.get("status") == "Final"
                    and start_comp <= game["game_date"] <= end_comp
                ]
            )
        ids = [game.get("game_id") for game in games]
        print(f"Found {str(len(ids))} games in range. Beginning data retrieval!")
        data = self.declareDf()
        for game_id in ids:
            game_df = self.make_game_df(game_id)
            data = pd.concat([data, game_df], ignore_index=True)
        if save_to_file:
            try:
                data.to_excel(file_path, index=False)
                print(f"Successfully saved data to {file_path}.")
            except Exception as e:
                print(f"An exception has occured while saving data to disk: {e}")
        return data

    def get_array(
        self, gamePk: str, model_name: str, order: str
    ) -> Optional[Union[Tuple[None, str], np.ndarray]]:
        """
        method to get an array of a game's features to make predictions with
            -> specific data augmentation steps described in depth in notebook

        Args:
            gamePk: id of the game to get features from
            model_name: name of the model to be used
                -> must be valid entry in MODELS
            order: order to put data features in

        Returns:
            x_pred: features array to give to model
        """
        with contextlib.redirect_stdout(io.StringIO()):
            df = self.make_game_df(gamePk)
        df.drop(
            columns=["game-id", "date", "home-team", "away-team", "did-home-win"],
            inplace=True,
        )
        if order == "order1":
            df = df[order1]
        elif order == "order2":
            df = df[order2]
        scalers = os.path.join(cwd, "models/scalers")
        path_to_scaler = os.path.join(scalers, (model_name + "_scaler.pkl"))
        with open(path_to_scaler, "rb") as file:
            scaler = pickle.load(file)
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = scaler.transform(df)
        x_pred = df
        return x_pred

    def next_game_array(
        self, team: str, model_name: str, order: str
    ) -> Optional[Union[np.ndarray, Tuple[None, str]]]:
        """
        method to produce features array for a team's next unplayed game

        Args:
            team: string of team's name (e.g. "New York Mets")
            model_name: name of the model to be used
                -> must be valid entry in MODELS
            order: feature order to be used (defaults to order2)

        Returns:
            x_pred: features array to give to model
        """
        next = self.get_next_game(team)
        if not next or not next[0]:
            return None, f"Error retrieving data for {team}'s next game."
        id = next[0]
        x_pred = self.get_array(id, model_name, order)
        return x_pred

    def predict_game(
        self, gamePk: str, num_simulations=10, perturbation_scale=0.001
    ) -> Optional[Union[Tuple[None, str], Tuple[str, float, Dict]]]:
        """
        method to make prediction on team's next game using specified model

        Args:
            team: string of team's name

        Returns:
            winner: team predicted to win
            prediction: the model's raw predicted value [0,1]
            game_info: python dictionary with info about the game

            or None, <error-msg>
        """

        # retrieve model and order to use from .env
        env_file_path = os.path.join(cwd, ".env")
        load_dotenv(env_file_path)

        env_model = os.getenv("SELECTED_MODEL")
        if not env_model:
            return None, "No 'SELECTED_MODEL' found in .env file for retrieval."
        model_name = env_model

        env_order = os.getenv("FEATURE_ORDER")
        if not env_order:
            return None, "No 'FEATURE_ORDER' found in .env file for retrieval."
        order = env_order

        x_pred = self.get_array(gamePk, model_name, order)

        if x_pred is None:
            return (
                None,
                "Failed to retrieve information about the game.",
            )
        model_path = os.path.join("./models/", model_name) + ".txt"
        if not os.path.exists(model_path):
            return (
                None,
                f"Failed to retrieve model, {model_name}. "
                f"Ensure it is placed in the models folder",
            )
        model = lgb.Booster(model_file=model_path)

        # simulate multiple predictions with perturbed samples
        simulated_predictions = []
        for _ in range(num_simulations):
            perturbation = np.random.normal(
                loc=0, scale=perturbation_scale, size=x_pred.shape
            )
            perturbed_input = x_pred + perturbation
            prediction = model.predict(perturbed_input)
            prediction = float(prediction[0])
            simulated_predictions.append(prediction)
        mean_prediction = np.mean(simulated_predictions)
        game = statsapi.schedule(game_id=gamePk)[0]
        if not game:
            return (
                None,
                "Failed to retrieve information about game.",
            )
        game_info = {}
        game_info["datetime"] = game.get("game_datetime")
        game_info["date"] = game.get("game_date")
        game_info["away"] = game.get("away_name")
        game_info["home"] = game.get("home_name")
        game_info["home"] = game.get("home_name")
        game_info["home_probable"] = game.get("home_probable_pitcher")
        game_info["away_probable"] = game.get("away_probable_pitcher")
        game_info["venue"] = game.get("venue_name")
        game_info["national_broadcasts"] = game.get("national_broadcasts")
        game_info["series_status"] = game.get("series_status")
        game_info["summary"] = game.get("summary")
        game_info["game_id"] = game.get("game_id")
        if mean_prediction >= 0.5:
            winner = game_info["home"]
        else:
            winner = game_info["away"]
        return winner, mean_prediction, game_info

    def predict_next_game(
        self, team: str, num_simulations=10, perturbation_scale=0.001
    ) -> Optional[Union[Tuple[None, str], Tuple[str, float, Dict]]]:
        """
        method to make prediction on team's next game using specified model

        Args:
            team: string of team's name

        Returns:
            winner: team predicted to win
            prediction: the model's raw predicted value [0,1]
            game_info: python dictionary with info about the game

            or None, <error-msg>
        """

        # retrieve model and order to use from .env
        env_file_path = os.path.join(cwd, ".env")
        load_dotenv(env_file_path)

        env_model = os.getenv("SELECTED_MODEL")
        if not env_model:
            return None, "No 'SELECTED_MODEL' found in .env file for retrieval."
        model_name = env_model

        env_order = os.getenv("FEATURE_ORDER")
        if not env_order:
            return None, "No 'FEATURE_ORDER' found in .env file for retrieval."
        order = env_order

        x_pred = self.next_game_array(team, model_name, order)
        if x_pred is None:
            return (
                None,
                f"Failed to retrieve information about next game for the {team}.",
            )
        model_path = os.path.join("./models/", model_name) + ".txt"
        if not os.path.exists(model_path):
            return (
                None,
                f"Failed to retrieve model, {model_name}. "
                f"Ensure it is placed in the models folder",
            )
        model = lgb.Booster(model_file=model_path)

        # simulate multiple predictions with perturbed samples
        simulated_predictions = []
        for _ in range(num_simulations):
            perturbation = np.random.normal(
                loc=0, scale=perturbation_scale, size=x_pred.shape
            )
            perturbed_input = x_pred + perturbation
            prediction = model.predict(perturbed_input)
            prediction = float(prediction[0])
            simulated_predictions.append(prediction)
        mean_prediction = np.mean(simulated_predictions)
        next_game_ret = self.get_next_game(team)
        if not next_game_ret or not next_game_ret[1]:
            return (
                None,
                f"Failed to retrieve information about next game for the {team}.",
            )
        next_game = next_game_ret[1]
        game_info = {}
        game_info["datetime"] = next_game["game_datetime"]
        game_info["date"] = next_game["game_date"]
        game_info["away"] = next_game["away_name"]
        game_info["home"] = next_game["home_name"]
        game_info["home"] = next_game["home_name"]
        game_info["home_probable"] = next_game["home_probable_pitcher"]
        game_info["away_probable"] = next_game["away_probable_pitcher"]
        game_info["venue"] = next_game["venue_name"]
        game_info["national_broadcasts"] = next_game["national_broadcasts"]
        game_info["series_status"] = next_game["series_status"]
        game_info["summary"] = next_game["summary"]
        game_info["game_id"] = next_game["game_id"]
        if mean_prediction >= 0.5:
            winner = game_info["home"]
        else:
            winner = game_info["away"]
        return winner, mean_prediction, game_info


class TeamStats(LeagueStats):
    def __init__(self, team: str):
        self.retrieve_ids(IDS)
        self.name = team
        self.abbreviation = team_to_abbreviation[self.name]
        self.id = team_to_id[self.name]
        div = self.get_division(self.name)
        if div:
            self.divisionName, self.divisionId = div
        self.divisionStandings = self.get_division_standings(self.divisionId)
        if self.divisionStandings:
            (
                self.wins,
                self.loses,
                self.divisionRank,
                self.divisionGB,
                self.leagueRank,
            ) = self.get_team_standings(self.name, self.divisionStandings)
        next = self.get_next_game()
        last = self.get_last_game()
        if next:
            self.nextGameId, self.nextGame = next
        if last:
            self.lastGameId, self.lastGame = last

    def __repr__(self):
        return f"{self.name} ({self.abbreviation})"

    def get_next_game(self) -> Optional[Union[Tuple[str, Dict], Tuple[None, None]]]:
        """
        method to get data about the team's next unstarted game

        Returns:
            gamePk: id of the team's next to-be-played game
            schedule: python dictionary with game details
        """
        gamePk = statsapi.next_game(self.id)
        next = statsapi.schedule(game_id=gamePk)
        return gamePk, next[0]

    def get_last_game(self) -> Optional[Union[Tuple[str, Dict], Tuple[None, None]]]:
        """
        method to get data about the team's last completed game

        Returns:
            gamePk: id of the team's next to-be-played game
            schedule: python dictionary with game details
        """
        gamePk = statsapi.last_game(self.id)
        next = statsapi.schedule(game_id=gamePk)
        return gamePk, next[0]

    def get_data(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        file_path: Optional[str] = None,
        save_to_file: Optional[bool] = True,
    ) -> pd.DataFrame:
        """
        method to get historical MLB data for the given team and save it to a file

        Args:
            start_date: first date to start retrieving game data from (YYYY-MM-DD)
            end_date: last date to retrieve game data from (YYYY-MM-DD).
                -> defaults to current day
            file_path: path to save data file to for persistent storage
            save_to_file: bool indicating if you wish the data to be stored

        Returns:
            data: python dataframe with the requested time range game data
        """
        if not end_date:
            end_date = date.today().strftime("%m/%d/%Y")
        if save_to_file:
            formatted_end = end_date.replace("/", "-")
            formatted_start = start_date.replace("/", "-")
            if not file_path:
                file_path = (
                    f"./data/{self.abbreviation}_{formatted_start}_{formatted_end}.xlsx"
                )
        start_obj = datetime.strptime(start_date, "%m/%d/%Y")
        end_obj = datetime.strptime(end_date, "%m/%d/%Y")
        start_comp = start_obj.strftime("%Y-%m-%d")
        end_comp = end_obj.strftime("%Y-%m-%d")
        start_year = int(start_date[-4:])
        end_year = int(end_date[-4:])
        games = []
        for year in range(start_year, end_year + 1):
            year_start = f"01/01/{year}"
            year_end = f"12/31/{year}"
            possible_games = statsapi.schedule(
                start_date=year_start, end_date=year_end, team=self.id
            )
            games.extend(
                [
                    game
                    for game in possible_games
                    if game.get("game_type") in ["R", "F", "D", "L", "W", "C", "P"]
                    and game.get("status") == "Final"
                    and start_comp <= game["game_date"] <= end_comp
                ]
            )
        ids = [game.get("game_id") for game in games]
        print(f"Found {str(len(ids))} games in range. Beginning data retrieval!")
        data = self.declareDf()
        for game_id in ids:
            game_df = self.make_game_df(game_id)
            data = pd.concat([data, game_df], ignore_index=True)
        if save_to_file:
            try:
                data.to_excel(file_path, index=False)
                print(f"Successfully saved data to {file_path}.")
            except Exception as e:
                print(f"An exception has occured while saving data to disk: {e}")
        return data


def main():
    # call class methods...
    pass


if __name__ == "__main__":
    main()

from typing import List, Tuple, Optional, Union, Dict
from datetime import datetime, timedelta, date
import lightgbm as lgb  # type: ignore
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import statsapi  # type: ignore
import contextlib
import subprocess
import pickle
import time
import csv
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
    "elo_abbreviation",
]
MODELS = {
    "mets6year": ["mets6year.txt", "mets6year_scaler.pkl"],
    "mlb2023": ["mlb2023.txt", "mlb2023_scaler.pkl"],
    "mlb3year": ["mlb3year.txt", "mlb3year_scaler.pkl"],
}

# to satisfy type checker...
id_to_team: Dict[str, str] = {}
team_to_id: Dict[str, str] = {}
team_to_abbreviation: Dict[str, str] = {}
league_dict: Dict[str, int] = {}
division_teams: Dict[str, List[str]] = {}
division_to_id: Dict[str, int] = {}
id_to_division: Dict[int, str] = {}
elo_abbreviation: Dict[str, str] = {}

cwd = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PATH_TO_ELO = os.path.join(cwd, "data/mlb_elo.csv")


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

    def get_game_elo(self, gamePk: str) -> Dict:
        """
        method that will get the ELO ratings for a specific game given game id

        Args:
            gamePk: game id of the game to retrieve data from

        Returns:
            elo_stats: python dictionary with many fields containing elo data
        """
        game = statsapi.schedule(game_id=gamePk)[0]
        home_team, away_team = game["home_name"], game["away_name"]
        game_date = game["game_date"]
        elo_stats = {}
        with open(PATH_TO_ELO, "r") as elo:
            elo_reader = csv.DictReader(elo)
            home, away = (
                elo_abbreviation.get(home_team),
                elo_abbreviation.get(away_team),
            )
            # TODO: more efficient search alg
            for row in elo_reader:
                date = row["date"]
                if (
                    (row["team1"] == home)
                    and (row["team2"] == away)
                    and (date == game_date)
                ):
                    elo_stats["home-elo-pregame"] = row["elo1_pre"]
                    elo_stats["away-elo-pregame"] = row["elo2_pre"]
                    elo_stats["home-elo-probability"] = row["elo_prob1"]
                    elo_stats["away-elo-probability"] = row["elo_prob2"]
                    elo_stats["home-rating-pregame"] = row["rating1_pre"]
                    elo_stats["away-rating-pregame"] = row["rating2_pre"]
                    elo_stats["home-pitcher-rgs"] = row["pitcher1_rgs"]
                    elo_stats["away-pitcher-rgs"] = row["pitcher2_rgs"]
                    elo_stats["home-rating-probability"] = row["rating_prob1"]
                    elo_stats["away-rating-probability"] = row["rating_prob2"]
        return elo_stats

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
            starters_stats[f"{pitcher[0]}-starter-career-era"] = career_stats["era"]
            starters_stats[f"{pitcher[0]}-starter-season-era"] = season_stats["era"]
            starters_stats[f"{pitcher[0]}-starter-season-avg"] = season_stats["avg"]
            starters_stats[f"{pitcher[0]}-starter-season-runs-per9"] = season_stats[
                "runsScoredPer9"
            ]
            try:
                win_pct = float(season_stats["winPercentage"])
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
            ) = (0, 0, 0, 0, 0.0, 0, 0.0)
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
                "home-elo-pregame",
                "away-elo-pregame",
                "home-elo-probability",
                "away-elo-probability",
                "home-rating-pregame",
                "away-rating-pregame",
                "home-pitcher-rgs",
                "away-pitcher-rgs",
                "home-rating-probability",
                "away-rating-probability",
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
        elo_stats = self.get_game_elo(gamePk)
        for col in elo_stats:
            game_df.at[0, col] = elo_stats[col]
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
        self, gamePk: str, model_name: str
    ) -> Optional[Union[Tuple[None, str], np.ndarray]]:
        """
        method to get an array of a game's features to make predictions with
            -> specific data augmentation steps described in depth in notebook

        Args:
            gamePk: id of the game to get features from
            model_name: name of the model to be used
                -> must be valid entry in MODELS

        Returns:
            x_pred: features array to give to model
        """
        with contextlib.redirect_stdout(io.StringIO()):
            df = self.make_game_df(gamePk)
        df.drop(
            columns=["game-id", "date", "home-team", "away-team", "did-home-win"],
            inplace=True,
        )
        order1 = [
            "home-win-percentage",
            "away-win-percentage",
            "home-starter-season-era",
            "away-starter-season-era",
            "home-elo-probability",
            "away-elo-probability",
            "home-rating-probability",
            "away-rating-probability",
            "home-starter-season-win-percentage",
            "away-starter-season-win-percentage",
            "home-last10-avg-runs",
            "away-last10-avg-runs",
            "home-last10-avg-ops",
            "away-last10-avg-ops",
            "home-last10-avg-runs-allowed",
            "away-last10-avg-runs-allowed",
            "home-starter-season-avg",
            "away-starter-season-avg",
            "home-elo-pregame",
            "away-elo-pregame",
            "home-pitcher-rgs",
            "away-pitcher-rgs",
            "home-last10-avg-hits",
            "away-last10-avg-hits",
            "home-last10-avg-hits-allowed",
            "away-last10-avg-hits-allowed",
            "home-last10-avg-obp",
            "away-last10-avg-obp",
            "home-rating-pregame",
            "away-rating-pregame",
            "home-starter-season-runs-per9",
            "away-starter-season-runs-per9",
            "home-last10-avg-strikeouts",
            "away-last10-avg-strikeouts",
            "home-starter-career-era",
            "away-starter-career-era",
        ]
        df = df[order1]
        scalers = os.path.join(cwd, 'models/scalers')
        path_to_scaler = os.path.join(scalers, (model_name + '.pkl'))
        with open(path_to_scaler, "rb") as file:
            scaler = pickle.load(file)
        columns_to_scale = [
            "home-starter-season-era",
            "away-starter-season-era",
            "home-last10-avg-runs",
            "away-last10-avg-runs",
            "home-last10-avg-runs-allowed",
            "away-last10-avg-runs-allowed",
            "home-elo-pregame",
            "away-elo-pregame",
            "home-pitcher-rgs",
            "away-pitcher-rgs",
            "home-last10-avg-hits",
            "away-last10-avg-hits",
            "home-last10-avg-hits-allowed",
            "away-last10-avg-hits-allowed",
            "home-rating-pregame",
            "away-rating-pregame",
            "home-starter-season-runs-per9",
            "away-starter-season-runs-per9",
            "home-last10-avg-strikeouts",
            "away-last10-avg-strikeouts",
            "home-starter-career-era",
            "away-starter-career-era",
        ]
        for col in df[columns_to_scale].columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df[columns_to_scale] = scaler.transform(df[columns_to_scale])
        x_pred = df.values
        return x_pred

    def next_game_array(
        self, team: str, model_name: str
    ) -> Optional[Union[np.ndarray, Tuple[None, str]]]:
        """
        method to produce features array for a team's next unplayed game

        Args:
            team: string of team's name (e.g. "New York Mets")
            model_name: name of the model to be used
                -> must be valid entry in MODELS

        Returns:
            x_pred: features array to give to model
        """
        next = self.get_next_game(team)
        if not next or not next[0]:
            return None, f"Error retrieving data for {team}'s next game."
        id = next[0]
        x_pred = self.get_array(id, model_name)
        return x_pred

    def predict_next_game(
        self, model_name: str, team: str
    ) -> Optional[Union[Tuple[None, str], Tuple[str, float, Dict]]]:
        """
        method to make prediction on team's next game using specified model

        Args:
            model_name: string of model's name
                -> must be in ./models/ and entry in MODELS
            team: string of team's name

        Returns:
            winner: team predicted to win
            prediction: the model's raw predicted value [0,1]
            game_info: python dictionary with info about the game

            or None, <error-msg>
        """
        if model_name not in MODELS:
            return None, f"{model_name} not found as valid model."
        x_pred = self.next_game_array(team, model_name)
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
        prediction = model.predict(x_pred)
        prediction = float(prediction[0])
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
        if prediction >= 0.5:
            winner = game_info["home"]
        else:
            winner = game_info["away"]
        return winner, prediction, game_info


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

    def next_game_array(self, model_name: str) -> Optional[Union[np.ndarray, None]]:
        """
        method to produce features array for the team's next unplayed game

        Args:
            model_name: name of the model to be used
                -> must be valid entry in MODELS

        Returns:
            x_pred: features array to give to model
        """
        next = self.get_next_game()
        if not next or not next[0]:
            return None
        id = next[0]
        x_pred = self.get_array(id, model_name)
        return x_pred


def main():
    mlb = LeagueStats()
    # call class methods...


if __name__ == "__main__":
    main()

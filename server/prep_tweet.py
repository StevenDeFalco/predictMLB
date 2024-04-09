from server.get_odds import get_todays_odds
from server.tweet_generator import gen_game_line
from dotenv import load_dotenv  # type: ignore
from datetime import datetime
import pandas as pd  # type: ignore
import subprocess
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_data_path() -> str:
    """
    function that will fetch the current data sheet pathfrom .env file
    """
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_file_path = os.path.join(parent_dir, ".env")
    load_dotenv(env_file_path)
    data_sheet = os.getenv("DATA_SHEET_PATH")
    return data_sheet if data_sheet is not None else "data/predictions.xlsx"


def prepare(game_info: pd.Series) -> str:
    """
    function to update odds, construct tweet, and tweet prediction
        -> get latest odds
        -> update odds in pandas Series
        -> update row in excel sheet to match pandas series with new odds
        -> generate tweet using tweet_generator.gen_game_line
        -> return game line for tweet 

    Args:
        game_info: pandas series with all game info

    Returns:
        tweet: string of line to tweet
    """
    data_file = os.path.join(parent_dir, get_data_path())
    games, retrieval_time = get_todays_odds()
    home_odds, away_odds, home_odds_bookmaker, away_odds_bookmaker = (
        None,
        None,
        None,
        None,
    )
    for game in games:
        if (
            game.get("home_team") == game_info.get("home")
            and game.get("away_team") == game_info.get("away")
            and game.get("time") == game_info.get("time")
        ):
            home, away = game_info["home"], game_info["away"]
            home_odds = str(game.get(f"{home}_odds"))
            away_odds = str(game.get(f"{away}_odds"))
            home_odds_bookmaker = game.get(f"{home}_bookmaker")
            away_odds_bookmaker = game.get(f"{away}_bookmaker")
            break
    df = pd.read_excel(data_file)
    id = game_info.get("game_id")
    row_index = df.loc[df["game_id"] == id].index[0]
    df.at[row_index, "home_odds"] = (
        home_odds if home_odds else df.at[row_index, "home_odds"]
    )
    df.at[row_index, "away_odds"] = (
        away_odds if away_odds else df.at[row_index, "away_odds"]
    )
    df.at[row_index, "home_odds_bookmaker"] = (
        home_odds_bookmaker
        if home_odds_bookmaker
        else df.at[row_index, "home_odds_bookmaker"]
    )
    df.at[row_index, "away_odds_bookmaker"] = (
        away_odds_bookmaker
        if away_odds_bookmaker
        else df.at[row_index, "away_odds_bookmaker"]
    )
    df.at[row_index, "odds_retrieval_time"] = (
        retrieval_time if home_odds else df.at[row_index, "odds_retrieval_time"]
    )
    print(
        f"\n{datetime.now().strftime('%D - %I:%M:%S %p')}... Odds checked for updates: "
        f"{game_info['away']} ({'no update' if not away_odds else str(away_odds)}) @ "
        f"{game_info['home']} ({'no update' if not home_odds else str(home_odds)})\n"
    )
    updated_game_row = df.loc[row_index]
    tweet = gen_game_line(updated_game_row)
    df.at[row_index, "tweet"] = tweet
    df.to_excel(data_file, index=False)
    return tweet

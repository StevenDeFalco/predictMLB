from server.get_odds import get_todays_odds
from server.tweet_generator import gen_prediction_tweet
from datetime import datetime
import pandas as pd  # type: ignore
import subprocess


def prepare(game_info: pd.Series) -> None:
    """
    function to update odds, construct tweet, and tweet prediction
        -> get latest odds
        -> update odds in pandas Series
        -> update row in excel sheet to match pandas series w new odds
        -> generate tweet using tweet.generator.py
        -> invoke subprocess tweet.py to tweet prediction
        -> return...

    Args:
        game_info: pandas series with all game info

    Returns:
        None
    """
    file_path = "../data/predictions.xlsx"
    games, retrieval_time = get_todays_odds()
    home_odds, away_odds, home_odds_bookmaker, away_odds_bookmaker = (
        None,
        None,
        None,
        None,
    )
    for game in games:
        if (
            game.get("home") == game_info.get("home")
            and game.get("away") == game_info.get("away")
            and game.get("time") == game_info.get("time")
        ):
            home, away = game_info["home"], game_info["away"]
            home_odds = str(game.get(f"{home}_odds"))
            away_odds = str(game.get(f"{away}_odds"))
            home_odds_bookmaker = game.get(f"{home}_bookmaker")
            away_odds_bookmaker = game.get(f"{away}_bookmaker")
            break
    df = pd.read_excel(file_path)
    row_index = df[df.eq(game_info).all(axis=1)].index[0]
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
        f"\n{datetime.now().strftime('%D - %T')}... Odds updated: "
        f"{game_info['away']} ({'no update' if not away_odds else away_odds}) @ "
        f"{game_info['home']} ({'no update' if not home_odds else home_odds})"
    )
    df.to_excel(file_path, index=False)
    info = df.loc[row_index].copy()
    home, away = info["home"], info["away"]
    winner = info["predicted_winner"]
    if winner == home:
        winner_odds = info["home_odds"]
        loser, loser_odds = away, info["away_odds"]
        w_bookmaker = info["home_odds_bookmaker"]
        l_bookmaker = info["away_odds_bookmaker"]
    else:  # winner == away
        winner_odds = info["away_odds"]
        loser, loser_odds = home, info["home_odds"]
        w_bookmaker = info["away_odds_bookmaker"]
        l_bookmaker = info["home_odds_bookmaker"]
    tweet = gen_prediction_tweet(
        winner,
        loser,
        info["time"],
        info["venue"],
        winner_odds,
        loser_odds,
        w_bookmaker,
        l_bookmaker,
    )
    try:
        process = subprocess.Popen(
            ["python3", "./tweet.py", tweet],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        process.wait()
        stdout, stderr = process.communicate()
        print(stdout.strip())
        print(stderr.strip())
        return_code = process.poll()
        if return_code != 0:
            print(f"Error calling tweet.py: return code={return_code}")
    except subprocess.CalledProcessError as e:
        print(
            f"\n{datetime.now().strftime('%D - %T')}... "
            f"Exception calling tweet.py to tweet prediction: {e}"
        )

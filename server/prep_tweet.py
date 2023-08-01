from server.get_odds import get_todays_odds
from server.tweet_generator import gen_prediction_tweet
from datetime import datetime
import pandas as pd  # type: ignore
import subprocess
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def prepare(game_info: pd.Series) -> None:
    """
    function to update odds, construct tweet, and tweet prediction
        -> get latest odds
        -> update odds in pandas Series
        -> update row in excel sheet to match pandas series with new odds
        -> generate tweet using tweet_generator.py
        -> invoke subprocess tweet.py to tweet prediction
        -> return...

    Args:
        game_info: pandas series with all game info

    Returns:
        None
    """
    data_file = os.path.join(parent_dir, "data/predictions.xlsx")
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
    if home_odds and away_odds:
        home_odds = ("+" + str(home_odds)) if (int(home_odds) > 100) else str(home_odds)
        away_odds = ("+" + str(away_odds)) if (int(away_odds) > 100) else str(away_odds)
    print(
        f"\n{datetime.now().strftime('%D - %T')}... Odds checked for updates: "
        f"{game_info['away']} ({'no update' if not away_odds else str(away_odds)}) @ "
        f"{game_info['home']} ({'no update' if not home_odds else str(home_odds)})\n"
    )
    home, away = df.at[row_index, "home"], df.at[row_index, "away"]
    winner = df.at[row_index, "predicted_winner"]
    if winner == home:
        winner_odds = df.at[row_index, "home_odds"]
        loser, loser_odds = away, df.at[row_index, "away_odds"]
        w_bookmaker = df.at[row_index, "home_odds_bookmaker"]
        l_bookmaker = df.at[row_index, "away_odds_bookmaker"]
    else:  # winner == away
        winner_odds = df.at[row_index, "away_odds"]
        loser, loser_odds = home, df.at[row_index, "home_odds"]
        w_bookmaker = df.at[row_index, "away_odds_bookmaker"]
        l_bookmaker = df.at[row_index, "home_odds_bookmaker"]
    tweet = gen_prediction_tweet(
        winner,
        loser,
        df.at[row_index, "time"],
        df.at[row_index, "venue"],
        winner_odds,
        loser_odds,
        w_bookmaker,
        l_bookmaker,
    )
    df.at[row_index, "tweet"] = tweet
    try:
        cwd = os.path.dirname(os.path.abspath(__file__))
        script_dir = os.path.join(cwd, "tweet.py")
        process = subprocess.Popen(
            ["python3", script_dir, tweet],
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
            df.at[row_index, "tweeted?"] = False
        else:
            df.at[row_index, "tweeted?"] = True
    except subprocess.CalledProcessError as e:
        print(
            f"\n{datetime.now().strftime('%D - %T')}... "
            f"Exception calling tweet.py to tweet prediction: {e}"
        )
    df.to_excel(data_file, index=False)

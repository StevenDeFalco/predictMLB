from re import A
from server.tweet_generator import gen_result_tweet, gen_game_line, create_tweets
from apscheduler.schedulers.background import BlockingScheduler  # type: ignore
from apscheduler.events import (
    EVENT_SCHEDULER_STARTED,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
)
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from server.get_odds import get_todays_odds
from server.prep_tweet import prepare
from dotenv import load_dotenv  # type: ignore
from data import LeagueStats
import pandas as pd  # type: ignore
import subprocess
import threading
import statsapi  # type: ignore
import pytz  # type: ignore
import time
import os

# use model defined in .env or by default 'mlb4year'
selected_model = "mlb4year"
cwd = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(cwd, ".env")
load_dotenv(env_file_path)
ret = os.getenv("SELECTED_MODEL")
selected_model = ret if ret is not None else selected_model

global_correct: int = 0
global_wrong: int = 0
global_biggest_upset: Optional[List] = None
global_upset_diff: int = 0
global_results: Optional[Tuple[str, str]] = None

mlb = LeagueStats()

lock = threading.Lock()

eastern = pytz.timezone("America/New_York")

# define daily_scheduler as global var
daily_scheduler = None


def print_next_job(event) -> None:
    """function to print details about next scheduled job"""
    time.sleep(1)
    ret = daily_scheduler.get_jobs()
    if daily_scheduler.running and len(ret) == 0:
        time.sleep(5)
        daily_scheduler.shutdown(wait=False)
        return
    next_job = ret[0] if (ret != []) else None
    if next_job is not None:
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
            f"Next Scheduled Job"
        )
        print(f"Job Name: {next_job.name}")
        run_time = next_job.next_run_time
        et_time = run_time.astimezone(eastern)
        formatted_time = et_time.strftime("%I:%M %p")
        print(f"Next Execution Time: {formatted_time} ET")
        time.sleep(1)
    return


def update_row(row: pd.Series) -> pd.Series:
    """
    function to update the row data of completed games

    Args:
        row: Row data as a pandas Series object.

    Returns:
        updated_row: The updated row with prediction accuracy and other information.
    """
    global global_correct, global_wrong, global_biggest_upset, global_upset_diff
    predicted_winner = row["predicted_winner"]
    id = row["game_id"]
    game = statsapi.schedule(game_id=id)[0]
    if game["status"] != "Final":
        return row
    actual_winner = game.get("winning_team")
    prediction_accuracy = (
        1.0
        if (actual_winner == predicted_winner)
        else (0.0 if actual_winner is not None else None)
    )
    losing_team = row["home"] if actual_winner == row["away"] else row["away"]
    if actual_winner == row["home"]:
        winner_odds, loser_odds = row["home_odds"], row["away_odds"]
    else:  # actual_winner == row["away"]:
        winner_odds, loser_odds = row["away_odds"], row["home_odds"]
    if prediction_accuracy == 1.0:
        global_correct += 1
        odds_diff = int((abs(winner_odds) - 100) + (abs(loser_odds) - 100))
        if odds_diff > global_upset_diff and winner_odds > 100:
            global_upset_diff = odds_diff
            global_biggest_upset = [actual_winner, winner_odds, losing_team, loser_odds]
        print(
            f"Correct! Your prediction - {predicted_winner} - "
            f"defeated the {losing_team}."
        )
    else:
        global_wrong += 1
        print(
            f"Wrong! Your prediction - {predicted_winner} - "
            f"lost to the {actual_winner}."
        )
    updated_row = row.copy()
    # update any row information needed given that the game is now complete
    updated_row["prediction_accuracy"] = prediction_accuracy
    updated_row["home_score"] = game["home_score"]
    updated_row["away_score"] = game["away_score"]
    updated_row["winning_pitcher"] = game["winning_pitcher"]
    updated_row["losing_pitcher"] = game["losing_pitcher"]
    updated_row["datetime"] = game.get("datetime")
    updated_row["game_id"] = game["game_id"]
    updated_row["summary"] = game["summary"]
    return updated_row


def load_unchecked_predictions_from_excel(
    file_name: str,
) -> Optional[pd.DataFrame]:
    """
    function to load unchecked predictions from the excel sheet back into pd dataframe
        -> i.e. predictions that don't yet have an input for prediction_accuracy

    Args:
        file_name: string file name to retrieve past predictions from (.xlsx)

    Returns:
        df: data frame with past predictions
    """
    global global_results, global_correct, global_wrong
    global global_biggest_upset, global_upset_diff
    # reset before checking results
    global_correct = 0
    global_wrong = 0
    global_biggest_upset = None
    global_upset_diff = 0
    global_results = None
    try:
        df = pd.read_excel(file_name)
        df_missing_accuracy = df[df["prediction_accuracy"].isnull()]
        df_missing_accuracy = df_missing_accuracy.apply(update_row, axis=1)
        if (global_correct + global_wrong) > 0:
            print("\n")
            percentage = (
                str(
                    int(
                        100
                        * round((global_correct / (global_correct + global_wrong)), 2)
                    )
                )
                + "%"
            )
            correct_wrong = (
                f"{str(global_correct)}/{str(global_wrong + global_correct)}"
            )
            global_results = correct_wrong, percentage
            if global_biggest_upset is not None:
                is_upset = True
                (
                    upset_winner,
                    upset_w_odds,
                    upset_loser,
                    upset_l_odds,
                ) = global_biggest_upset
                res = gen_result_tweet(
                    correct_wrong,
                    percentage,
                    is_upset,
                    upset_winner,
                    upset_loser,
                    upset_w_odds,
                    upset_l_odds,
                )
            else:
                res = (
                    f"I was {percentage} ({correct_wrong}) accurate "
                    f"in predicting yesterday's MLB games."
                )
            if res:
                try:
                    tweet_script = os.path.join(cwd, "server/tweet.py")
                    process = subprocess.Popen(
                        ["python3", tweet_script, res],
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
                        f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
                        f"\nError tweeting results{e}\n"
                    )
        df.update(df_missing_accuracy)
        df.to_excel(file_name, index=False)
        return df
    except FileNotFoundError:
        return None


def safely_prepare(row: pd.Series) -> str:
    """
    function to orchastrate mutual exclusion
    -> protecting overrides on predictions.xlsx

    Args:
        row: pandas series with a single game's info

    Returns: 
        tweet_line = line of tweet from the game prepared
    """
    try:
        lock.acquire()
        tweet_line = prepare(row)
    finally:
        lock.release()
    return tweet_line


def schedule_job(row: pd.Series, tweet_time: datetime) -> None:
    """function to add safely_prepare(row) to the scheduler at tweet_time"""
    daily_scheduler.add_job(
        safely_prepare, args=[row], trigger="date", run_date=tweet_time
    )


def tweet_for_row(row: pd.Series) -> str:
    """
    function to generate a single line in prediction tweet 

    Args: 
        row: pandas series with game information 

    Returns:
        tweet_line: string representing one line of the tweet
            -> format: <winning-team> (ml odds) to defeat <losing-team> (ml odds)
    """
    home = row["home"] 
    away = row["away"]
    home_odds = row["home_odds"]
    away_odds = row["away_odds"]
    home_bookmaker = row["home_odds_bookmaker"]
    away_bookmaker = row["away_odds_bookmaker"]
    pred = row["predicted_winner"] 
    if pred == home:
        winner, loser = home, away 
        winner_odds, loser_odds = (home_odds, home_bookmaker), (away_odds, away_bookmaker)
    else:
        winner, loser = away, home 
        winner_odds, loser_odds = (away_odds, away_bookmaker), (home_odds, home_bookmaker)
    winning_part = f"{winner} ({winner_odds[0]} on {winner_odds[1]})"
    losing_part = f"{loser} ({loser_odds[0]} on {loser_odds[1]})"
    tweet_line = f"{winning_part} to defeat {losing_part}"
    return tweet_line


def generate_daily_predictions(
    model: str = selected_model, date: datetime = datetime.now()
) -> List:
    """
    function to generate predictions for one day of MLB games...
    ...and save them with other pertinent game information

    Args:
        model: model to use
            -> must be defined in MODELS
        date: datetime object representing day to predict on

    Returns:
        tweet_lines: List of strings, each representing a line of the tweet 
    """
    if date is not datetime.now():
        # NOT IMPLEMENTED: generating predictions for future days
        pass
    data_file = os.path.join(cwd, "data/predictions.xlsx")
    scheduled_ids = []
    model = selected_model
    tweet_lines = []
    try:
        df = pd.read_excel(data_file)
        tweet_times = pd.to_datetime(df["time_to_tweet"]).dt.tz_localize(pytz.utc)
        existing_dates = tweet_times.dt.tz_convert(eastern).dt.date.unique()
        existing_dates_list = [str(date) for date in existing_dates]
        check_date = str(date.date())
        if check_date in existing_dates_list:
            tt = pd.to_datetime(df["time_to_tweet"]).dt.tz_localize(pytz.utc)
            tt = tt.dt.tz_convert(eastern).dt.date
            mask = (tt == date.date()) & (df["tweeted?"] == False)
            to_tweet_today = df[mask]
            if not to_tweet_today.empty:
                print(
                    f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
                    f"\nFound {str(len(to_tweet_today))} "
                    f"games in sheet that need to be published (tweeted)\n"
                )
                for _, row in to_tweet_today.iterrows():
                    # TODO: replace below loop with new tweet logic
                    scheduled_ids.append(row["game_id"])
                    line = safely_prepare(row)
                    tweet_lines.append(line)
                    print(
                        f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... \nAdded game "
                        f"({row['away']} @ {row['home']}) to tweet (from sheet)"
                    )
    except FileNotFoundError:
        df = pd.DataFrame()

    all_games, odds_time = get_todays_odds()
    game_predictions: List[Dict] = []
    print(
        f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}..."
        f"\nMaking predictions using {selected_model} model\n"
    )

    # loop to get game_ids of all games to make predictions on (saved to scheduled_ids)
    for game in all_games:
        if game.get("date") != "Today":
            continue
        today = datetime.now().strftime("%m/%d/%Y")
        teams_games = mlb.get_days_games(game.get("home_team"), today)
        if not teams_games:
            continue
        for day_game in teams_games:
            if day_game['game_datetime'] != game['commence_time']:
                continue
            if (day_game.get("game_id") not in scheduled_ids) and (
                day_game.get("game_date")
                == datetime.now(eastern).date().strftime("%Y-%m-%d")
            ):
                scheduled_ids.append((day_game.get("game_id"), game))

    # loop to make predictions and schedule all the games in scheduled_ids
    for gameObj in scheduled_ids:
        try:
            gamePk = gameObj[0]
            game = gameObj[1]
            ret = mlb.predict_game(gamePk)
            if ret is None or ret[0] is None:
                continue
            winner, prediction, info = ret[0], ret[1], ret[2]
        except Exception as e:
            print(f"Error predicting next game: \n{e}\n")
            continue
        if not winner:
            continue
        home, away = info["home"], info["away"]
        info["predicted_winner"] = winner
        info["model"] = model
        info["predicted_winner_location"] = "home" if (winner is home) else "away"
        info["prediction_value"] = prediction
        info["time"] = game["time"]
        info["favorite"] = game.get("favorite")
        info["home_odds"] = str(game.get(f"{home}_odds"))
        info["away_odds"] = str(game.get(f"{away}_odds"))
        info["home_odds_bookmaker"] = game.get(f"{home}_bookmaker")
        info["away_odds_bookmaker"] = game.get(f"{away}_bookmaker")
        info["odds_retrieval_time"] = odds_time
        info["prediction_generation_time"] = datetime.now()
        info["prediction_accuracy"] = None
        info["home_score"] = None
        info["away_score"] = None
        info["winning_pitcher"] = None
        info["losing_pitcher"] = None
        info["tweeted?"] = False
        tweet = gen_game_line(info)
        info["tweet"] = tweet
        tweet_time = datetime.now().replace(hour=9, minute=45, second=0, microsecond=0)
        info["time_to_tweet"] = tweet_time.replace(tzinfo=None)
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... \nAdded game "
            f"({info['away']} @ {info['home']}) to prediction tweet"
        )
        game_predictions.append(info)

    df_new = pd.DataFrame(game_predictions)
    column_order = [
        "prediction_accuracy",
        "date",
        "time",
        "home",
        "home_probable",
        "away",
        "away_probable",
        "predicted_winner",
        "model",
        "favorite",
        "home_odds",
        "home_odds_bookmaker",
        "away_odds",
        "away_odds_bookmaker",
        "home_score",
        "away_score",
        "winning_pitcher",
        "losing_pitcher",
        "prediction_value",
        "venue",
        "series_status",
        "national_broadcasts",
        "odds_retrieval_time",
        "prediction_generation_time",
        "datetime",
        "game_id",
        "summary",
        "tweet",
        "time_to_tweet",
        "tweeted?",
    ]
    try:
        if len(df_new) > 0:
            df_new = df_new[column_order]
            df = pd.concat([df, df_new], ignore_index=True)
            df.to_excel(data_file, index=False)
        else:
            print(
                f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... \n"
                f"No new predictions made for games\n"
            )
    except Exception as _:
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... \n"
            f"No new games to added to predictions.xlsx\n"
        )
    return tweet_lines


def send_tweet(tweet: str) -> bool:
    """
    Function to send a tweet 

    Args: 
        tweet: tweet to send

    Returns: 
        bool: True or False to represent success or failure

    """
    try:
        tweet_script = os.path.join(cwd, "server/tweet.py")
        process = subprocess.Popen(
            ["python3", tweet_script, tweet],
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
            return False 
        return True
    except subprocess.CalledProcessError as e:
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
            f"\nError tweeting results{e}\n"
        )
        return False


def schedule_tweets(tweet_lines: List[str]) -> None: 
    """
    Function to schedule the prediction tweet(s) for the day 
        -> Will make call to tweet_generator.py for body of tweet(s)
        -> Will schedule add tweet script subprocess for each tweet

    Args: 
        tweet_lines: list of prediction strings for each individual game

    Returns: 
        None
    """
    tweets = create_tweets(tweet_lines)
    tweet_time = datetime.now().replace(hour=9, minute=45, second=0, microsecond=0)
    for tweet in tweets:
        daily_scheduler.add_job(
            send_tweet, args=[tweet], trigger="date", run_date=tweet_time
        )
    return


def check_and_predict():
    global daily_scheduler
    daily_scheduler = None
    data_file = os.path.join(cwd, "data/predictions.xlsx")
    try:
        load_unchecked_predictions_from_excel(data_file)
    except Exception as e:
        print(f"Error checking past predictions in {data_file}. {e}")

    # create daily scheduler
    daily_scheduler = BlockingScheduler(
        job_defaults={"coalesce": False},
        timezone=eastern,
    )
    daily_scheduler.add_listener(print_next_job, EVENT_SCHEDULER_STARTED)
    daily_scheduler.add_listener(print_next_job, EVENT_JOB_EXECUTED)
    daily_scheduler.add_listener(print_next_job, EVENT_JOB_MISSED)

    tweet_lines = generate_daily_predictions()
    try:
        schedule_tweets(tweet_lines)
    except Exception as e:
        print(f"Error sending prediction tweet(s). {e}")

    # start call is blocking, so scheduler shutdown in listener when last event finished
    daily_scheduler.start()
    print(
        f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
        f"\nAll prediction tweets sent. "
        f"Exiting predict.py check_and_predict\n"
    )
    time.sleep(10)
    daily_scheduler = None
    return


if __name__ == "__main__":
    check_and_predict()

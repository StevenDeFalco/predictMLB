"""COPY OF make_predictions.py WITH CHANGES TO MAKE IT A SUITABLE RECURRING PROCESS"""

from server.tweet_generator import gen_result_tweet, gen_prediction_tweet
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore
from apscheduler.events import (
    EVENT_SCHEDULER_STARTED,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
)
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from server.get_odds import get_todays_odds
from server.prep_tweet import prepare
from data import LeagueStats
import pandas as pd  # type: ignore
import subprocess
import threading
import statsapi  # type: ignore
import pytz  # type: ignore
import time
import os

MODELS = ["mlb3year", "mlb2023", "mets6year"]
selected_model = MODELS[0]

global_correct: int = 0
global_wrong: int = 0
global_biggest_upset: Optional[List] = None
global_upset_diff: int = 0
global_results: Optional[Tuple[str, str]] = None

mlb = LeagueStats()

lock = threading.Lock()

cwd = os.path.dirname(os.path.abspath(__file__))
eastern = pytz.timezone("US/Eastern")


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
    global global_results
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
                    f"Of yesterday's MLB games, I predicted {correct_wrong} correctly, "
                    f"and thus had a prediction accuracy of {percentage}. "
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


def safely_prepare(row: pd.Series) -> None:
    """
    function to orchastrate mutual exclusion to the prepare function

    Args:
        row: pandas series with a single game's info
    """
    try:
        lock.acquire()
        prepare(row)
    finally:
        lock.release()


def print_next_job(event) -> None:
    """function to print details about next scheduled job"""
    print(f"{datetime.now(eastern).strftime('%D - %I:%M %p')}... Next Scheduled Job")
    next_job = daily_scheduler.get_jobs()[0] if daily_scheduler.get_jobs()[0] else None
    if next_job is not None:
        print(f"\nJob Name: {next_job.name}")
        run_time = next_job.next_run_time
        et_time = run_time.astimezone(eastern)
        formatted_time = et_time.strftime("%I:%M %p")
        print(f"Next Execution Time: {formatted_time} ET")
        print(f"Trigger: {next_job.trigger}\n")
    return


def schedule_job(
    scheduler: BackgroundScheduler, row: pd.Series, tweet_time: datetime
) -> None:
    """function to add safely_prepare(row) to the scheduler at tweet_time"""
    scheduler.add_listener(print_next_job, EVENT_JOB_EXECUTED)
    scheduler.add_job(safely_prepare, args=[row], trigger="date", run_date=tweet_time)


def generate_daily_predictions(
    model: str, scheduler: BackgroundScheduler, date: datetime = datetime.now()
) -> List[Dict]:
    """
    function to generate predictions for one day of MLB games...
    ...and save them with other pertinent game information

    Args:
        model: model to use
            -> must be defined in MODELS
        scheduler: schedule to add the prediction tweet to
        date: datetime object representing day to predict on

    Returns:
        game_predictions: list of dictionaries with prediction + odds information
    """
    if date is not datetime.now():
        # NOT IMPLEMENTED: generating predictions for future days
        pass
    data_file = os.path.join(cwd, "data/predictions.xlsx")
    scheduled_ids = []

    try:
        df = pd.read_excel(data_file)
        existing_dates = (
            pd.to_datetime(df["time_to_tweet"]).dt.tz_convert(eastern).dt.date.unique()
        )
        existing_dates_list = [str(date) for date in existing_dates]
        check_date = str(date.date())
        if check_date in existing_dates_list:
            print(
                f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
                f"\nFound some tweets in spreadsheet that need to be scheduled\n"
            )
            tt = pd.to_datetime(df["time_to_tweet"]).dt.tz_convert(eastern).dt.date
            mask = (tt == date.date()) & (df["tweeted?"] == False)
            to_tweet_today = df[mask]
            if not to_tweet_today.empty:
                print(
                    f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
                    f"\nFound {str(len(to_tweet_today))} tweets in sheet that need to be scheduled\n"
                )
                for _, row in to_tweet_today.iterrows():
                    scheduled_ids.append(row["game_id"])
                    tweet_time = pd.to_datetime(row["tweet_time"])
                    schedule_job(scheduler, row, tweet_time)
                    print(
                        f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... \nAdded game "
                        f"({row['away']} @ {row['home']}) to tweet schedule "
                        f"for {tweet_time.astimezone(eastern).strftime('%I:%M %p')}\n"
                    )
    except FileNotFoundError:
        df = pd.DataFrame()

    all_games, odds_time = get_todays_odds()
    game_predictions: List[Dict] = []
    print(
        f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}..."
        f"\nMaking predictions using {selected_model} model\n"
    )
    for game in all_games:
        try:
            ret = mlb.predict_next_game(selected_model, game["home_team"])
            if ret is None or ret[0] is None:
                continue
            winner, prediction, info = ret[0], ret[1], ret[2]
            if info["game_id"] in scheduled_ids:
                continue
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
        tweet = gen_prediction_tweet(
            winner,
            (info["home"] if info["away"] == winner else info["away"]),
            info["time"],
            info["venue"],
        )
        info["tweet"] = tweet
        tweet_time = pd.to_datetime(info["datetime"]) - timedelta(hours=1)
        info["time_to_tweet"] = tweet_time.replace(tzinfo=None)
        schedule_job(scheduler, info, tweet_time)
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... \nAdded game "
            f"({info['away']} @ {info['home']}) to tweet schedule "
            f"for {tweet_time.astimezone(eastern).strftime('%I:%M %p')}\n"
        )
        scheduled_ids.append(info['game_id'])
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
    df_new = df_new[column_order]
    df = pd.concat([df, df_new], ignore_index=True)
    df.to_excel(data_file, index=False)
    return game_predictions


daily_scheduler = BackgroundScheduler(
    job_defaults={"coalesce": False},
    timezone=timezone(timedelta(hours=-4)),
)


def check_and_predict(selected_model):
    data_file = os.path.join(cwd, "data/predictions.xlsx")
    try:
        load_unchecked_predictions_from_excel(data_file)
    except Exception as e:
        print(f"Error checking past predictions in {data_file}. {e}")
    daily_scheduler.add_listener(print_next_job, EVENT_SCHEDULER_STARTED)
    daily_scheduler.add_listener(print_next_job, EVENT_JOB_MISSED)
    generate_daily_predictions(selected_model, daily_scheduler)
    daily_scheduler.start()
    try:
        while daily_scheduler.get_jobs():
            time.sleep(1)
        print(
            f"{datetime.now(eastern).strftime('%D - %I:%M:%S %p')}... "
            f"\nAll daily prediction tweets complete. "
            f"Exiting predict.py check_and_predict\n"
        )
    finally:
        daily_scheduler.shutdown(wait=True)
        sys.exit(0)


if __name__ == "__main__":
    check_and_predict(MODELS[0])

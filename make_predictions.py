from get_odds import get_todays_odds
from data import LeagueStats
from datetime import datetime
from typing import Dict, List
import pandas as pd

mlb = LeagueStats()


def generate_daily_predictions(date: datetime = datetime.now()) -> List[Dict]:
    """
    function to generate predictions for one day of MLB games...
    ...and save them with other pertinent game information

    Args:
        date: datetime object representing day to predict on

    Returns:
        game_predictions: list of dictionaries with prediction + odds information
    """
    if date is not datetime.now():
        # NOT IMPLEMENTED: generating predictions for future days
        pass

    file_name = "./data/predictions.xlsx"
    try:
        df = pd.read_excel(file_name)
        existing_dates = pd.to_datetime(df["datetime"]).dt.date.unique()
        if date.date() in existing_dates:
            predictions = df.loc[
                pd.to_datetime(df["datetime"]).dt.date == date.date()
            ].to_dict("records")
            return predictions
    except FileNotFoundError:
        df = pd.DataFrame()

    all_games, odds_time = get_todays_odds()
    game_predictions: List[Dict] = []
    for game in all_games:
        try:
            winner, prediction, info = mlb.predict_next_game(
                "mlb2023", game["home_team"]
            )
        except:
            continue
        if not winner:
            continue
        home, away = info["home"], info["away"]
        info["predicted_winner"] = winner
        info["predicted_winner_location"] = "home" if (winner is home) else "away"
        info["prediction_value"] = prediction
        info["time"] = game["time"]
        info["favorite"] = game["favorite"]
        info["home_odds"] = game[f"{home}_odds"]
        info["away_odds"] = game[f"{away}_odds"]
        info["home_odds_bookmaker"] = game[f"{home}_bookmaker"]
        info["away_odds_bookmaker"] = game[f"{away}_bookmaker"]
        info["odds_retrieval_time"] = odds_time
        info["prediction_accuracy"] = None
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
        "favorite",
        "home_odds",
        "home_odds_bookmaker",
        "away_odds",
        "away_odds_bookmaker",
        "prediction_value",
        "venue",
        "series_status",
        "national_broadcasts",
        "odds_retrieval_time",
        "datetime",
        "summary"
    ]
    df_new = df_new[column_order]
    df = pd.concat([df, df_new], ignore_index=True)
    df.to_excel(file_name, index=False)

    return game_predictions


if __name__ == "__main__":
    generate_daily_predictions()

from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from dotenv import load_dotenv  # type: ignore
import requests  # type: ignore
import calendar
import pytz  # type: ignore
import json
import os

# minimum time between requests
REQUEST_COOLDOWN = 3600  # 1 hour


def make_request() -> Optional[Tuple[Optional[Dict], Optional[datetime]]]:
    # load environment variables from .env
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env_file_path = os.path.join(parent_dir, ".env")
    load_dotenv(env_file_path)
    # access the API key
    apikey = os.getenv("ODDS_API_KEY")
    # API endpoint
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    # query parameters
    params = {
        "apiKey": apikey,
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
    }
    data: Dict = None
    request_time: datetime = None
    data_file = os.path.join(parent_dir, "data/todays_odds.json")
    if os.path.exists(data_file):
        modified_time = os.path.getmtime(data_file)
        current_time = datetime.now().timestamp()
        time_difference = current_time - modified_time
        # read file data without making new request
        if time_difference < REQUEST_COOLDOWN:
            with open(data_file, "r") as file:
                data = json.load(file)
            request_time = datetime.fromtimestamp(modified_time)
        else:
            # makes API request
            response = requests.get(url, params)
            # check if response is successful
            if response.status_code == 200:
                # parse JSON response
                data = response.json()
                # save data to file
                with open(data_file, "w") as file:
                    json.dump(data, file)
                request_time = datetime.now()
            else:
                print("Error occureed. Status code: ", response.status_code)
    else:
        # makes API request
        response = requests.get(url, params)
        # check if response is successful
        if response.status_code == 200:
            # parse JSON response
            data = response.json()
            # save data to file
            with open(data_file, "w") as file:
                json.dump(data, file)
            request_time = datetime.now()
        else:
            print("Error occureed. Status code: ", response.status_code)
    if data is None or request_time is None:
        return None
    return data, request_time


def get_favorite(game: Dict) -> Optional[str]:
    """function to calculate the team favorited to win the game"""
    outcomes = game["bookmakers"][0]["markets"][0]["outcomes"]
    favorite = None
    lowest_odds = float("inf")
    for outcome in outcomes:
        odds = outcome["price"]
        if odds < lowest_odds:
            lowest_odds = odds
            favorite = outcome["name"]
    return favorite


def get_best_odds(game: Dict) -> Dict:
    best_odds: Dict = {}
    for bookmaker in game["bookmakers"]:
        for market in bookmaker["markets"]:
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    team = outcome["name"]
                    odds = outcome["price"]
                    if team in best_odds:
                        if int(odds) > int(best_odds[team]["odds"]):
                            best_odds[team]["odds"] = (
                                str(odds) if (int(odds) <= 0) else f"+{odds}"
                            )
                            best_odds[team]["bookmaker"] = bookmaker["title"]
                    else:
                        best_odds[team] = {
                            "odds": str(odds) if (int(odds) <= 0) else f"+{odds}",
                            "bookmaker": bookmaker["title"],
                        }
    return best_odds


def make_twelve_hour(time):
    """returns 12 hour version of 24 hour clock time"""
    time_parts = time.split(":")
    hour = int(time_parts[0])
    minute = int(time_parts[1])
    ending = " am"
    if hour == 0:
        hour = 12
    elif hour > 12:
        ending = " pm"
        hour -= 12
    elif hour == 12:
        ending = " pm"
    time_formatted = f"{hour:02d}:{minute:02d}{ending}"
    return time_formatted


def format_date(date):
    """returns formatted date in EST"""
    now = datetime.now(pytz.timezone("US/Eastern"))
    if date.date() == now.date():
        date_formatted = "Today"
    else:
        month = calendar.month_name[int(date.strftime("%m"))]
        day = str(int(date.strftime("%d")))
        date_formatted = f"{day} {month}"
    return date_formatted


def process_data(data):
    """returns list of objects with pertinent data for simple display"""
    games = []
    # current time
    for game in data:
        game_info = {}
        UTC_date = datetime.strptime(game["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
        EST_date = UTC_date.astimezone(pytz.timezone("US/Eastern")) - timedelta(hours=4)
        formatted_date = format_date(EST_date)
        if formatted_date != "Today":
            continue
        game_info["date"] = formatted_date
        game_info["time"] = make_twelve_hour(EST_date.strftime("%H:%M"))
        game_info["home_team"] = game["home_team"]
        game_info["away_team"] = game["away_team"]
        best_odds = get_best_odds(game)
        game_info["favorite"] = get_favorite(game)
        for team, odds_info in best_odds.items():
            game_info[f"{team}_odds"] = odds_info["odds"]
            game_info[f"{team}_bookmaker"] = odds_info["bookmaker"]
        games.append(game_info)
    return games


def get_todays_odds():
    """
    function to get the odds of games occurring today

    Returns:
        games: list of python dictionaries representing individual MLB games
        time: time of the request to get the odds (most recent odds retrieval)
    """
    res = make_request()
    if not res:
        return None
    data, time = res
    games = process_data(data)
    return games, time

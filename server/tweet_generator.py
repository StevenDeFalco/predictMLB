from datetime import datetime
from typing import List
import pandas as pd
import pytz
import json

TWITTER_MAX_CHAR_COUNT = 268

def gen_game_line(row: pd.Series) -> str:
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
    # if home_odds are positive (e.g. +150)
    if int(home_odds) >= 100:
        home_odds = f"+{str(int(home_odds))}"
    away_odds = row["away_odds"]
    # if away_odds are positive (e.g. +150)
    if int(away_odds) >= 100:
        away_odds = f"+{str(int(away_odds))}"
    home_bookmaker = row["home_odds_bookmaker"]
    away_bookmaker = row["away_odds_bookmaker"]
    pred = row["predicted_winner"] 
    if pred == home:
        winner, loser = home, away 
        winner_odds, loser_odds = (home_odds, home_bookmaker), (away_odds, away_bookmaker)
    else:
        winner, loser = away, home 
        winner_odds, loser_odds = (away_odds, away_bookmaker), (home_odds, home_bookmaker)
    # winning_part = f"{winner} ({winner_odds[0]} on {winner_odds[1]})"
    # losing_part = f"{loser} ({loser_odds[0]} on {loser_odds[1]})"
    with open('data/ids.json', 'r') as f:
        data = json.load(f)
    winner_id = data['team_to_id'][winner]
    winner_abb = data['id_to_team'][str(winner_id)]['abbreviation']
    loser_id = data['team_to_id'][loser]
    loser_abb = data['id_to_team'][str(loser_id)]['abbreviation']
    winning_part = f"{winner_abb} ({winner_odds[0]})"
    losing_part = f"{loser_abb} ({loser_odds[0]})"
    tweet_line = f"{winning_part} to defeat {losing_part}"
    return tweet_line


def create_tweets(tweet_lines: List[str]) -> List[str]:
    """
    Function to create the individual tweets given the lines

    Args: 
        tweet_lines: list of strings (one for each line)
        MAX_TWEET_LENGTH: max length for body (excluding lead in)
        MAX_LINES_PER_TWEET: max number of lines in each tweet

    Returns:
        tweets: list of tweets to be sent
    """
    tweets = []
    num_lines = len(tweet_lines)
    # get todays date
    eastern = pytz.timezone("America/New_York")
    today = datetime.now(eastern).date()
    formatted_date = today.strftime("%d %B %Y")
    leadin_msg = f"Predictions for {formatted_date}"
    # Map from number of games today --> games in tweet layout
    # used to ensure even distribution of games across tweets
    num_tweet_map = {
        1: [1],
        2: [2],
        3: [3], 
        4: [4],
        5: [5],
        6: [6],
        7: [7], 
        8: [4,4],
        9: [5,4],
        10: [5,5], 
        11: [6,5],
        12: [6,6],
        13: [7,6],
        14: [7,7],
        15: [5,5,5],
        16: [6,5,5],
        17: [6,6,5],
        18: [6,6,6]
    }
    tweets_layout = num_tweet_map.get(num_lines)
    num_tweets = len(tweets_layout)
    current_tweet = ""
    for i, line_ct in enumerate(tweets_layout):
        if num_tweets == 1:
            current_tweet = f"{leadin_msg}"
        else:
            current_tweet = f"{leadin_msg} ({str(i+1)}/{str(num_tweets)})"
        for _ in range(int(line_ct)):
            current_tweet += f"\n• {tweet_lines[0]}"
            tweet_lines = tweet_lines[1:]
        tweets.append(current_tweet)

    return tweets



def gen_result_tweet(
    correct_wrong: str,
    percentage: str,
    is_upset: bool,
    upset_winner: str,
    upset_loser: str,
    upset_winner_odds: str,
    upset_loser_odds: str,
) -> str:
    msg = (
        f"I was {percentage} ({correct_wrong}) accurate "
        f"in predicting yesterday's MLB games."
    )
    if is_upset:
        msg += (
            f" My best pick was the {upset_winner} (+{upset_winner_odds}) upsetting"
            f" the {upset_loser} ({upset_loser_odds}) (odds from 09:30 gameday)"
        )
    return msg

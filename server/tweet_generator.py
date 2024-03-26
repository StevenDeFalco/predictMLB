from typing import List
from datetime import date
import pandas as pd

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
    winning_part = f"{winner} ({winner_odds[0]})"
    losing_part = f"{loser} ({loser_odds[0]})"
    tweet_line = f"{winning_part} to defeat {losing_part}"
    return tweet_line


def create_tweets(tweet_lines: List[str], MAX_TWEET_LENGTH=215, MAX_LINES_PER_TWEET=3) -> List[str]:
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
    today = date.today()
    formatted_date = today.strftime("%d %B %Y")
    leadin_msg = f"Here are my predictions for {formatted_date}"
    # Map from number of games today --> games in tweet layout
    # used to ensure even distribution of games across tweets
    # e.g. "7" --> (3,2,2) means first tweet has 3
    num_tweet_map = {
        1: [1],
        2: [2],
        3: [3], 
        4: [2,2],
        5: [3,2],
        6: [3,3],
        7: [3,2,2], 
        8: [3,3,2],
        9: [3,3,3],
        10: [3,3,2,2], 
        11: [3,3,3,2],
        12: [3,3,3,3],
        13: [3,3,3,2,2],
        14: [3,3,3,3,2],
        15: [3,3,3,3,3],
        16: [3,3,3,3,2,2],
        17: [3,3,3,3,3,2],
        18: [3,3,3,3,3,3]
    }
    tweets_layout = num_tweet_map[num_lines]
    print(tweets_layout)
    num_tweets = len(tweets_layout)
    current_tweet = ""
    for i, line_ct in enumerate(tweets_layout):
        current_tweet = f"{leadin_msg} ({str(i+1)}/{str(num_tweets)})"
        for _ in range(int(line_ct)):
            current_tweet += f"\n{tweet_lines[0]}"
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
            f"Among these predictions, I had correctly anticipated the {upset_winner} "
            f"(+{upset_winner_odds}) defeating the {upset_loser} ({upset_loser_odds}) "
            f"(Odds from 09:30 yesterday)"
        )
    return msg

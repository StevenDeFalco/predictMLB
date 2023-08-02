from datetime import datetime
from dotenv import load_dotenv  # type: ignore
import tweepy  # type: ignore
import sys
import os

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
cwd = os.path.dirname(os.path.abspath(__file__))
env_file_path = os.path.join(parent_dir, ".env")

load_dotenv(env_file_path)

api_key = os.getenv("CONSUMER_KEY")
api_secret = os.getenv("CONSUMER_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

client = tweepy.Client(
    consumer_key=api_key,
    consumer_secret=api_secret,
    access_token=access_token,
    access_token_secret=access_token_secret,
)

if len(sys.argv) > 1:
    tweet = sys.argv[1]

    print(f"\n{datetime.now().strftime('%D - %T')}... \nTweeting: '{tweet}'\n")

    tweet_log = os.path.join(cwd, "tweets.txt")
    with open(tweet_log, "a") as f:
        f.write(tweet + "\n")

    try:
        client.create_tweet(text=tweet)
        sys.exit(0)
    except Exception as e:
        print(f"Error tweeting: {e}")
        sys.exit(1)

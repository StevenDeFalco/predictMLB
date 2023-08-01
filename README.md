# mlb-predict

### [@predictMLB on Twitter](https://twitter.com/predictmlb)
### Summer project 2023

Twitter bot that publishs MLB game predictions made by a machine learning model trained on historical MLB data. The bot tweets it's results from yesterday each morning at ~ 09:30 NY time and tweets individual game predictions with live odds ~ 1 hour before the each game's start.


## Data Retrieval and Processing

All of the data used in this project comes from *two major sources*: the MLB statsapi as accessed through the [MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) python wrapper and the FiveThirtyEight [MLB ELO Dataset](https://www.kaggle.com/datasets/fivethirtyeight/fivethirtyeight-mlb-elo-dataset). 

### data.py

The first first part of this project entailed defining a generalized method for retrieving data from multiple sources and different API endpoints and combining that data into a  single datastructure that I could use to represent a single MLB game between two teams. The data.py module defines two classes: LeagueStats and a TeamStats (a child of LeagueStats). Once instantiated, LeagueStats offers many methods that can be used to make calls for specific data and data groups in a team agnostic format. For example we may do the following to intuitively extract information from the api. 

```

from data import LeagueStats 

mlb = LeagueStats()

last_game_id, last_game_info = mlb.get_last_game("New York Mets")

winning_pitcher = last_game_info['winning_pitcher']
losing_pitcher  = last_game_info['losing_pitcher']

print(f"W: {winning_pitcher}, L: {losing_pitcher}")
# "W: Justin Verlander, L: Trevor Williams"

```

Additionally, we can use the TeamStats class which must be instantiated for a single MLB team to retrieve data with a more focused scope. The TeamStats class inherit many methods from LeagueStats along with offerring a few unique ones, and some which are overriden to address the one team individually. As shown there are ways for a human to interact with the module and gain meaningful insight; however, the intent of this module is not to be used manually but it is meant to be a useful tool in the automation of large-scale data retrieval. Thus, this module offers a method to construct a single row (pandas.Series) with over 40 features representing one MLB game and of course a method that can be used to do this over a given length of time and merge all the rows into a single pandas.DataFrame: this method is get_data. The get_data method is the primary means for assembling the training dataset that is used to tune the ML model. 

### What data is used?

Each game is represented as one row of a pandas DataFrame with 41 features. *Note* that not all 41 features are trainable: this 41 includes the label (did-home-team-win) along with non-trainable data such as team names (each training data point has 36 features). The major three areas of data that are included in each game's data is last 10 *day* averages, starting pitcher statistics, and ELO rankings (each to be elaborated on below). Each team's season winning percentage prior to that game is also used. **Keep in mind** that my data is all structured in a home-team vs. away-team format meaning that every statistic we use for the home team is also used for the away team. Additionally, the labels for training (and thus how predictions are made) all depends on whether or not the home team wins the game. 

#### Last 10 Day Averages 

For each team: runs (batting), runs allowed (fielding), hits (batting), hits allowed (fielding), OPS (batting) (On-base percentage Plus Slugging percentage), strikeouts (fielding), and OBP (On-Base Percentage). 

These were chosen with the goal of using an even split between offensive (batting) and defensive (fielding) statistics to quantify a team's recent (last 10 *days*) performance on both sides of the ball. 

#### Starting Pitcher Statistics 

For each starting pitcher: career ERA (Earned Run Average), season ERA (Earned Run Average), season runs allowed per 9 innings, and season win percentage (on games started). 

Starting pitching is massively important in many games and often is a large factor in a team's success on any given day; however this isn't always the case and thus I didn't want to flood my data with many more starting pitcher stats. I use some career stats to indicate the overall/long-term merit of a pitcher, while the rest only represent the current season of play as to try to sample their current momentum and likelihood of playing well. 

#### ELO Rankings 

For each team: pregame ELO, ELO probability to win, pregame ELO rating, pitcher RGS (Rolling Game Score), ELO rating probability. 

These stats are conglomerates of many different factors that could go into a team's success and return that in some various composite stats. In this category, I largely trust the managers of the database; however, historical performance provides proof of merit for these stats. 

### data_retriever.py

This script is the method through which large amounts of data retrieval (seasons at a time) can safely take place. The MLB statsapi has, in my experience, had some miscellaneous issues with failed requests and timeouts, so in this script the data retrieval is split into appropriately sized chunks to ensure data is written to disk frequently enough to avoid extensive repeated computation in case of API error. This script takes in a start date, end date, and optionally a team (or by deafult the entire league!) and will make calls to the aforementioned data.py module to construct data. All data is dumped into an excel (.xlsx) file in the format of a pandas DataFrame for easy viewing and eventual retrieval back into memory.  


## Machine Learning and The Models

*explanation to come...*

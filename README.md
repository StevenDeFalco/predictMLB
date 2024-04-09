# mlb-predict

### [@predictMLB on Twitter](https://twitter.com/predictmlb)
### Summer project 2023

Twitter bot that publishs MLB game predictions made by a machine learning model trained on historical MLB data. The bot tweets it's results from yesterday each morning at ~ 09:30 NY time and tweets individual game predictions with the best live odds ~ 1 hour before the each game's start.


## Data Retrieval and Processing

All of the data used in this project comes from *one major source*: the MLB statsapi as accessed through the [MLB-StatsAPI](https://github.com/toddrob99/MLB-StatsAPI) python wrapper.

### `data.py`

The first first part of this project entailed defining a generalized method for retrieving data from multiple sources and different API endpoints and combining that data into a  single datastructure that I could use to represent a single MLB game between two teams. The `data.py` module defines two classes: `LeagueStats` and a `TeamStats` (a child of LeagueStats). Once instantiated, `LeagueStats` offers many methods that can be used to make calls for specific data and data groups in a team agnostic format. For example we may do the following to intuitively extract information from the api. 

```

from data import LeagueStats 

mlb = LeagueStats()

last_game_id, last_game_info = mlb.get_last_game("New York Mets")

winning_pitcher = last_game_info['winning_pitcher']
losing_pitcher  = last_game_info['losing_pitcher']

print(f"W: {winning_pitcher}, L: {losing_pitcher}")
# "W: Justin Verlander, L: Trevor Williams"

```

Additionally, we can use the `TeamStats` class which must be instantiated for a single MLB team to retrieve data with a more focused scope. The `TeamStats` class inherit many methods from `LeagueStats` along with offerring a few unique ones, and some which are overriden to address the one team individually. As shown there are ways for a human to interact with the module and gain meaningful insight; however, the intent of this module is not to be used manually but it is meant to be a useful tool in the automation of large-scale data retrieval. Thus, this module offers a method to construct a single row (`pandas.Series`) with over 40 features representing one MLB game and of course a method that can be used to do this over a given length of time and merge all the rows into a single `pandas.DataFrame`: this method is `get_data`. The `get_data` method is the primary means for assembling the training dataset that is used to tune the ML model. 

### What data is used?

Each game is represented as one row of a pandas DataFrame with 49 features. *Note* that not all 49 features are trainable: this 49 includes the label (did-home-team-win) along with non-trainable data such as team names (each training data point has 44 features). The major three areas of data that are included in each game's data is last 10 *day* averages, starting pitcher statistics, and stat averages across a team's top 5 players in that statistics. Each team's season winning percentage prior to that game is also used. **Keep in mind** that my data is all structured in a home-team vs. away-team format meaning that every statistic we use for the home team is also used for the away team. Additionally, the labels for training (and thus how predictions are made) all depends on whether or not the home team wins the game. 

#### Last 10 Day Averages 

For each team: runs (batting), runs allowed (fielding), hits (batting), hits allowed (fielding), OPS (batting) (On-base percentage Plus Slugging percentage), strikeouts (fielding), and OBP (On-Base Percentage). 

These were chosen with the goal of using an even split between offensive (batting) and defensive (fielding) statistics to quantify a team's recent (last 10 *days*) performance on both sides of the ball. 

#### Starting Pitcher Statistics 

For each starting pitcher: career ERA (Earned Run Average), season ERA (Earned Run Average), season runs allowed per 9 innings, and season win percentage (on games started). 

Starting pitching is massively important in many games and often is a large factor in a team's success on any given day; however this isn't always the case and thus I didn't want to flood my data with many more starting pitcher stats. I use some career stats to indicate the overall/long-term merit of a pitcher, while the rest only represent the current season of play as to try to sample their current momentum and likelihood of playing well. 

#### Top 5 Player Averages

For each team: homeruns hit average, RBIs average, batting average average, stolen bases average, total bases average.

To clear up confusion, these are the categories and for each category I search for a team's leaders in those statistics (top 5 players). I then take the average of the team leaders' respective number (of RBIs for example) to get to the top5-rbi-average. These statistics are meant to go beyond just quantifying the value of a team's best player and instead try to measure the depth of a team's good players. A team with a deep hitting roster, may have a batting average among their top 5 that is near .300 while a team with a .300 player and many lesser hitters will have a top5-batting-average that is significantly weighed down. 

### `data_retriever.py`

This script is the method through which large amounts of data retrieval (seasons at a time) can safely take place. The MLB statsapi has, in my experience, had some miscellaneous issues with failed requests and timeouts, so in this script the data retrieval is split into appropriately sized chunks to ensure data is written to disk frequently enough to avoid extensive repeated computation in case of API error. This script takes in a start date, end date, and optionally a team (or by deafult the entire league!) and will make calls to the aforementioned `data.py` module to construct data. All data is dumped into an excel (.xlsx) file in the format of a `pandas.DataFrame` for easy viewing and eventual retrieval back into memory.  


## Machine Learning and The Models

After establishing the infrastructure to intake large amounts of data, the next step was to collect a lot fo data and prepare it for training the machine learning (ML) model. 

### mlb4year 

This is the the first model trained since mid August 2023 when I switched to a new data blend. Mlb4year takes data from all games across the past 4 seasons (2020, 2021, 2022, 2023) and constructs a training set consisting of all valid samples from this time period. 

### Preparing the data for training

This explanation will closely follow that which is written in [mlb-predict.ipynb](https://github.com/StevenDeFalco/mlb-predict/blob/main/mlb-predict.ipynb). For each model I first load the data all back into memory in a single pandas DataFrame. Then I drop the non-training features which include game-id (for API use only), date, home-team, and away-team. I then separate the label (did-home-team-win) into its own array. At this point, I arrange the order of the features in my samples; there are two primary orders, that I experimented with.

#### order1 (adjacent comparison)

Order1 has the most important features first with each home statistic immediately followed by the away team's counter part. This allows for many meaningful comparisons between adjacent features. For example, the first features, in order, are home win percentage, away win percentage, home starting pitcher season era, away starting pitcher season era, etc. This pattern continues in an order that I believe leads to less and less important statistics. Ideally, the earliest features are weighed most heavily by the model and it is able to extract meaning the direct comparison of adjacent (home vs. away) statitics. 

#### order2 (team separation)

Order2 employs the same ordering of features from most important/influential to least import; however, all of the home team's statistics come first and are followed by all of the away-team's statistics. This, in theory, would skew the data higher on one side of the middle value of the array, and ideally the reasonable prediction for our model would be the side of the array that the data is skewed towards: home or away.

I end up using order2 for my model (after testing both), but there truly wasn't a large discernable difference between the two when examining on the testing set. 

The next step in preparing the data is to drop samples that have more than 10 missing values. Keep in mind the data isn't always perfect. Sometimes the boxscore will be missing some values for a game or the API will fail to retrieve some data etc, so I account for this by dropping samples that are missing too many features. Then I perform min-max normalization on features that do not already fall within the range of [0,1]; these scalers are saved to the disk for use when preparing a sample for prediction. Finally, we randomize the indices of the data and split into training and testing groups (85/15 split). 

### Training with lightgbm

In an effort to maximize my accuracy as fast as possible, I opted to finetune an existing framework. LightGBM is a gradient boosting framework that is known to have very high-performance and be very computationally efficient. For my training, I imported the framework, converted my dataset to the required format, specified parameters including the objective of binary classification, and the let the model train. 

My mlb4year model uses 6295 training samples (6295 x 44 features) with a testing set of 1111 samples. I have a test set accuracy of ~ 66% on this model. This number was achieved after a bit of hyperparameter tuning, but I found that even across all my preliminary training and tuning, 60% accuracy was relatively easy to achieve and I could only get up to about 5% more accuracy. These 5% differences are essentially negligible, however, with such small testing sets (<=1000 samples). 

## Making predictions 

To make predictions using my trained model, I have to get real data that I want to make a prediction on and prepare it so that it is in the same format that we used to train the model. In `data.py` there are methods defined to do this. `get_array` takes a game id and model and will construct the sample, drop appropriate features, use the correct scaler to scale values, and then return the numpy array to be used with the model. `next_game_array` will create this array when given a particular team. Finally, the top level method, `predict_next_game` can be passed a team name and it will construct the array, retrieve the model weights from the disk, and make a prediction. In an effort to potentially improve accuracy and the robustness of my model, I construct a number of slightly perturbed samples and make a prediction for each one. The prediction results (a continuous value in [0,1]) are then averaged out from all the perturbed sample predictions and this is the prediction that is taken. The `predict_next_game` method will return this averaged prediction value, along with information, and the predicted winner. 

### *Note about predictions*

The labels given to the model are binary where 1 represents a game in which the home team won, and 0 represents a game in which the away team won. Making a prediction using the model generates a continuous value [0,1]. To determine the predicted winner, the floating point value is simply rounded up or down and this binary value indicates whether the model predicts that the home team will win or lose. 

## The Main Script and Interfacing with Twitter 

With all the infrastructure in place to make predictions on upcoming games, I just need a way to log and publish the predictions/results. `main.py` is the script that I run in the background on my AWS Lightsail instance continuously and which calls functions and forks new processes throughout the day to make predictions, update my data sheets, and upload to [twitter](https://twitter.com/predictmlb). To start the process, I simply run the script using `nohup` and the code will manage itself along with providing status update and completion notifications to my `output.log` file which I can log into and check in real-time from any terminal instance attached to that machine. 

`nohup python3 -u main.py > output.log`

`tail -f output.log`

### `main.py`

In the main script itself, I instantiate a `apscheduler.BlockingScheduler` which I use to add a recurring cron event for 9:30 am ET everyday which calls the `check_and_predict` function from `predict.py`. All that this script does is schedules that process for everyday at 9:30, waits for it to complete and schedules it again for the next day. 

### `predict.py` 

In this module, first a new `apscheduler.BlockingScheduler` is instantiated and then `check_and_predict` is ran. First it will run a function called `load_unchecked_predictions_from_excel` which, intuitively, loads predictions stored in the predictions sheet that haven't yet been checked for accuracy. This function checks whether the predictions were correct, and upon completion of this check will send a tweet summarizing number correct vs. wrong and additonally will highlight an upset that I had predicted correctly, if there is one of note (i.e. a betting underdog defeats a favorite). Next `generate_daily_predictions` is called and this function will load any tweets that need to be sent that day which are in the sheet already and it will add those to the daily schedule of tweets, it will additionally make predictions on all remaining games and those to the tweet schedule as well. Then throughout the day, the schedule will fork new processes to prepare and send tweets at their scheduled time (1 hour before gametime). Before tweets are sent, they must be run through the `prep_tweet.py` file which ensures that the odds were updated within the last 15 minutes and if not will update them; I limit my system to 1 odds request per 15 minutes because I use an API for that with a monthly request limit. 

## Conclusion

This is the general overview of my project. I've really enjoyed creating this and feel that I got a lot of good practice and learning all throughout. As of writing this however (04 August 2023), I have many plans to continue new development on this project along with, of course, maintaining the current system (at least until the end of the MLB season). 

### Some goals for this project's future 

- interact with a LLM for text-generation to create unique tweets for each game 
- grow the twitter account?
- other sports? (NBA, NFL)

### Goals completed

- improve ML model (higher accuracy): move away from ELO statistics, try using larger datasets for training 
- tune typerparameters further

## Changes

### 08/18/2023 - New Data Blend (no more ELO)

FiveThirtyEight discontinued support of their MLB ELO sheet and thus I was somewhat forced to stop using it. I replaced all my my ELO statistics in the samples with the new 'top5' stats and some supplemental ones in the exisitng categories. Back testing accuracy only slightly increased with this new data blend (mlb4year), but the change was necessary. All of the descriptions above have been updated and are free from mentions of ELO statistics and my 3 original models that I trained using the data blend that included ELO stats. mlb4year is my first and (right now) only model using the new data blend. 

### 04/09/2024 - New tweet format

At the start of the 2024 season, I had been working in a branch called "newtweet" where I developed a new format for tweeting the predictions and results to Twitter (X). Instead of creating and scheduling individual tweets to be sent out (at different points throughout the day) for each individual MLB game, the prediction tweets are consolidated in form and all sent at 09:45 AM everyday. The new format only uses the team abbreviation (e.g NYM) and the best living ML betting odds for each team. At most, 7 games can be put in each tweet, so on most days there will be 2 or 3 tweets sent 5 seconds apart and in an order that allows them to be read straight down (1,2, and then 3) in the timeline. Additionally, issues regarding doublheader games have been fixed so that both games will be found, predicted, and tweeted separately with accurate odds; they are distinguishable in a tweet since the start time for each game will be added. Finally, the result tweet is changed in format and verbiage to more simply state the percentage correct as well as the best "pick" from yesterday's games (if there was one). The best pick simply refers to the biggest betting underdog that the model correctly had predicted. This new format makes the Twitter bot much more accessible and approachable as everything is clearly laid out in a consolidated and simple fashion. 

import statsapi, time, csv
import pandas as pd
import api_ids as ids 

PATH_TO_ELO='./raw_data/mlb_elo.csv'

class TeamStats:

    def get_division(self):
        """
        method to get the division of the given team

        Returns: 
            division name string (e.g. "AL West", "NL East", etc...), division API id (e.g 201)
        """
        for division in ids.division_teams:
            if self.name in ids.division_teams[division]:
                return division, ids.division_to_id[division]

    def get_division_standings(self): 
        """
        method to get current division standings of an MLB team

        Retuns: 
            standings: python dictionary containing division standings data 
        """
        standings = statsapi.standings_data("103,104")[self.divisionId]['teams']
        return standings
    
    def get_team_standings(self):
        """
        method to get wins, loses, division rank, div games back, and league rank

        Returns:
            wins: integer number of wins for the season
            loses: integer number of loses for the season 
            division rank: integer rank within division 
            games back: number of games back behind division leader (if 0 then '-')
            league rank: integer rank within league
        """
        for team in self.divisionStandings:
            if team['name'] == self.name:
                w,l,gb = team['w'], team['l'], team['gb']
                drank, lrank = team['div_rank'], team['league_rank']
        return w,l,drank,gb,lrank
    
    def get_next_game(self):
        """
        method to get data about the team's next unstarted game 

        Returns:
            gamePk: id of the team's next to-be-played game
            schedule: python dictionary with game details
        """
        gamePk = statsapi.next_game(self.id)
        next = statsapi.schedule(game_id=gamePk)
        return gamePk, next[0]

    def __init__(self, team):
        self.name = team
        self.id = ids.team_to_id[self.name]
        self.divisionName, self.divisionId = self.get_division()
        self.divisionStandings = self.get_division_standings()
        self.wins, self.loses, self.divisionRank, self.divisionGB, self.leagueRank = self.get_team_standings()
        self.nextGameId, self.nextGame = self.get_next_game()

    def get_game_elo(self, date, home_team, away_team):
        """
        method that will get the ELO ratings for a specific game given the date and home/away teams

        Args:
            date: date of game played in format YYYY-MM-DD 
            home_team: full name of home team for desired game 
            away_team: full name of away team for desired game

        Returns:
            elo_stats: python dictionary with many fields containing elo data
        """
        elo_stats = {}
        with open(PATH_TO_ELO, 'r') as elo:
            elo_reader = csv.DictReader(elo)
            home, away = ids.team_to_abbreviation[home_team], ids.team_to_abbreviation[away_team]
            for row in elo_reader:
                date = row['date']
                if row['team1'] == home and row['team2'] == away:
                    elo_stats['home_elo_pre'] = row['elo1_pre']
                    elo_stats['away_elo_pre']= row['elo2_pre']
                    elo_stats['home_elo_prob'] = row['elo_prob1']
                    elo_stats['away_elo_prob'] = row['elo_prob2']
                    elo_stats['home_rating_pre'] = row['rating1_pre']
                    elo_stats['away_rating_pre'] = row['rating2_pre']
                    elo_stats['home_pitcher_rgs'] = row['pitcher1_rgs']
                    elo_stats['away_pitcher_rgs'] = row['pitcher2_rgs']
                    elo_stats['home_rating_prob'] = row['rating_prob1']
                    elo_stats['away_rating_prob'] = row['rating_prob2']
        return elo_stats

    def get_player_id(self, player_name, season=None):
        """
        method that will get the id of a player given their name 

        Args:
            player_name: a player's name in plain english 
            season: season to search for player within

        Returns:
            player_id: a player's id for use with the api as a parameter
        """
        player = statsapi.lookup_player(player_name, season=season)
        return player[0]['id'] or None

    def get_starting_pitcher_stats(self, gamePk):
        """
        method that will get the required stats about a starting pitcher given a game ID 

        Args:
            gamePk: game id of the game to retrieve data from

        Returns:
            starters_stats: python dictionary with many fields containing stats from both the home and away pitchers for a given game
                -> for both home/away... season era, career era, season era, season avg, seasons runs/9, season win percentage, 
        """
        starters_stats = {}
        game = statsapi.schedule(game_id=gamePk)[0]
        home_starter, away_starter = game['home_probable_pitcher'], game['away_probable_pitcher']
        season = game['game_date'][0:4]
        for pitcher in [('home', home_starter), ('away', away_starter)]:
            if not pitcher[1]:
                continue
            pitcher_id = self.get_player_id(pitcher[1], season=season)
            if not pitcher_id: 
                continue
            seasons = statsapi.player_stat_data(pitcher_id, group='pitching', type='yearByYear')['stats']
            season_stats = {}
            for year in seasons:
                if year['season'] == season:
                    season_stats = year['stats']
            career_stats = statsapi.player_stat_data(pitcher_id, group='pitching', type='career')['stats'][0]['stats']
            starters_stats[f"{pitcher[0]}-starter-career-era"] = career_stats['era']
            starters_stats[f"{pitcher[0]}-starter-season-era"] = season_stats['era']
            starters_stats[f"{pitcher[0]}-starter-season-avg"] = season_stats['avg']
            starters_stats[f"{pitcher[0]}-starter-season-runs-per9"] = season_stats['runsScoredPer9']
            starters_stats[f"{pitcher[0]}-starter-season-win-percentage'"] = season_stats['winPercentage']
        return starters_stats

    def make_game_df(self, gamePk):
        """
        method that will construct a data frame for a single game given the game id 

        Args:
            gamePk: unique game ID of the game

        Returns:
            game_df: data frame with data points about a specific game
        """
        game_df = pd.DataFrame(columns=['did-home-win',
                                        'date',
                                        'gamePk',
                                        'home-team',
                                        'away-team',
                                        'home-win-percentage',
                                        'away-win-percentage',
                                        'home-last10-avg-runs',
                                        'home-last10-avg-runs-allowed',
                                        'away-last10-avg-runs',
                                        'away-last10-avg-runs-allowed',
                                        'home-last10-avg-hits',
                                        'home-last10-avg-hits-allowed',
                                        'away-last10-avg-hits',
                                        'away-last10-avg-hits-allowed',
                                        'home-last10-avg-strikeouts',
                                        'away-last10-avg-strikeouts',
                                        'home-roster-batting-avg',
                                        'away-roster-batting-avg',
                                        'home-roster-ops',
                                        'away-roster-ops',
                                        'home-starter-career-era',
                                        'away-starter-career-era',
                                        'home-starter-season-era',
                                        'away-starter-seasons-era',
                                        'home-starter-season-avg',
                                        'away-starter-season-avg',
                                        'home-starter-season-runs-per9',
                                        'away-starter-season-runs-per9',
                                        'home-starter-season-win-percentage',
                                        'away-starter-season-win-percentage',
                                        'home-elo-pregame',
                                        'away-elo-pregame',
                                        'home-elo-probability',
                                        'away-elo-probability',
                                        'home-rating-pregame',
                                        'away-rating-pregame',
                                        'home-pitcher-rgs',
                                        'away-pitcher-rgs',
                                        'home-rating-prob',
                                        'away-rating-prob',
                                        ])


def main():
    nym = TeamStats("New York Mets")
    print(nym.get_starting_pitcher_stats(565997))
    # call class methods...

if __name__ == "__main__":
    main()

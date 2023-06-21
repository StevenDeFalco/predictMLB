import statsapi, time
import api_ids as ids 

class TeamStats:

    def get_division(self):
        """
        function to get the division of the given team

        Args:
            team: team name in the fully worded (teamName) format (e.g. "New York Mets")

        Returns: 
            division name string (e.g. "AL West", "NL East", etc...), division API id (e.g 201)
        """
        for division in ids.division_teams:
            if self.name in ids.division_teams[division]:
                return division, ids.division_to_id[division]

    def get_division_standings(self): 
        """
        function to get current division standings of an MLB team

        Args:
            division_id: id of division to get standings from (e.g. 201)

        Retuns: 
            standings: python dictionary containing division standings data 
        """
        standings = statsapi.standings_data("103,104")[self.divisionId]['teams']
        return standings
    
    def get_team_standings(self):
        """
        function to get wins, loses, division rank, div games back, and league rank

        Args:
            team: team name in fully written format (self.name, e.g. "New York Mets")

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

    def __init__(self, team):
        self.name = team
        self.id = ids.team_to_id[self.name]
        self.divisionName, self.divisionId = self.get_division()
        self.divisionStandings = self.get_division_standings()
        self.wins, self.loses, self.divisionRank, self.divisionGB, self.leagueRank = self.get_team_standings()

def main():
    ny_mets = TeamStats("New York Mets")
    # call class methods...

if __name__ == "__main__":
    main()

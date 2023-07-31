import statsapi  # type: ignore
import requests  # type: ignore
import json
import os


def get_elo_abbreviation():
    """
    function to get a dictionary for translating abbreviations used in the elo sheet

    Returns:
        elo_abbreviation: {teamName: elo-abbrev}
    """
    elo_abbreviation = {
        "Oakland Athletics": "OAK",
        "Pittsburgh Pirates": "PIT",
        "San Diego Padres": "SDP",
        "Seattle Mariners": "SEA",
        "San Francisco Giants": "SFG",
        "St. Louis Cardinals": "STL",
        "Tampa Bay Rays": "TBD",
        "Texas Rangers": "TEX",
        "Toronto Blue Jays": "TOR",
        "Minnesota Twins": "MIN",
        "Philadelphia Phillies": "PHI",
        "Atlanta Braves": "ATL",
        "Chicago White Sox": "CHW",
        "Miami Marlins": "FLA",
        "New York Yankees": "NYY",
        "Milwaukee Brewers": "MIL",
        "Los Angeles Angels": "ANA",
        "Arizona Diamondbacks": "ARI",
        "Baltimore Orioles": "BAL",
        "Boston Red Sox": "BOS",
        "Chicago Cubs": "CHC",
        "Cincinnati Reds": "CIN",
        "Cleveland Guardians": "CLE",
        "Colorado Rockies": "COL",
        "Detroit Tigers": "DET",
        "Houston Astros": "HOU",
        "Kansas City Royals": "KCR",
        "Los Angeles Dodgers": "LAD",
        "Washington Nationals": "WSN",
        "New York Mets": "NYM",
    }
    return elo_abbreviation


elo_abbreviation = get_elo_abbreviation()


def get_team_ids():
    """
    function to return two dictionaries for translating to and from team names / ids

    Returns:
        id_to_team: {id: {<team_info>}}
        team_to_id: {teamName: id}
        abbreviation_to_id: {abbreviation: id}
    """
    id_to_team, team_to_id = {}, {}
    for team in statsapi.lookup_team("", activeStatus="Y"):
        if team["id"] not in id_to_team:
            abbreviation = requests.get(
                f"https://statsapi.mlb.com/api/v1/teams/{team['id']}"
            ).json()["teams"][0]["abbreviation"]
            id_to_team[team["id"]] = {
                "name": team["name"],
                "teamName": team["teamName"],
                "abbreviation": abbreviation,
                "location": team["locationName"],
                "shortName": team["shortName"],
            }
    team_to_id = {value["name"]: key for key, value in id_to_team.items()}
    team_to_abbreviation = {
        value["name"]: value["abbreviation"] for _, value in id_to_team.items()
    }
    return id_to_team, team_to_id, team_to_abbreviation


# dictionaries for translating to/from teamName/id/abbreviation
id_to_team, team_to_id, team_to_abbreviation = get_team_ids()


def get_division_data():
    """
    function to construct a dictionary of format {division: [<division_teams>]}

    Returns:
        division_teams: {division: [<division_teams>]}
    """
    division_teams, division_to_id, id_to_division = {}, {}, {}
    standings = statsapi.standings_data(leagueId="103,104", division="all")
    for id in standings:
        if id not in division_teams:
            id_to_division[id] = standings[id]["div_name"]
            for team in standings[id]["teams"]:
                div_name = standings[id]["div_name"]
                if div_name not in division_teams:
                    division_teams[div_name] = []
                division_teams[div_name].append(team["name"])
    division_to_id = {value: key for key, value in id_to_division.items()}
    return division_teams, division_to_id, id_to_division


# dictionary to provide translation from 'n'ational or 'a'merican league to its API id
league_dict = {"a": 103, "n": 104}

# division_teams: dictionary to provide list of teams in each division
# division_to_id: dictionary to provide translation from division to its API id
# id_to_division: dictionary to provide translation from API id to division name
division_teams, division_to_id, id_to_division = get_division_data()

data = {
    "id_to_team": id_to_team,
    "team_to_id": team_to_id,
    "team_to_abbreviation": team_to_abbreviation,
    "league_dict": league_dict,
    "division_teams": division_teams,
    "division_to_id": division_to_id,
    "id_to_division": id_to_division,
    "elo_abbreviation": elo_abbreviation,
}

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
file_path = os.path.join(parent_dir, "data/ids.json")

with open(file_path, "w") as f:
    json.dump(data, f)

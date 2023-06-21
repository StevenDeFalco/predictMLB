import statsapi

def get_team_ids():
    """
    function to return two dictionaries for translating to and from team names / ids

    Returns:
        id_to_team: {id: {<team_info>}}
        team_to_id: {teamName: id}
    """
    id_to_team, team_to_id = {}, {}
    for team in statsapi.lookup_team('', activeStatus="Y"):
        if team['id'] not in id_to_team:
            id_to_team[team['id']] = {'name': team['name'], 
                                    'teamName': team['teamName'], 
                                    'location': team['locationName'],
                                    'shortName': team['shortName']}
    team_to_id = {value['name']: key for key, value in id_to_team.items()}
    return id_to_team, team_to_id

# dictionaries for translating to/from teamName/id
id_to_team, team_to_id = get_team_ids()

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
            id_to_division[id] = standings[id]['div_name']
            for team in standings[id]['teams']:
                div_name = standings[id]['div_name']
                if div_name not in division_teams:
                    division_teams[div_name] = []
                division_teams[div_name].append(team['name'])
    division_to_id = {value: key for key, value in id_to_division.items()}
    return division_teams, division_to_id, id_to_division

# dictionary to provide translation from 'n'ational or 'a'merican league to its API id
league_dict = {'a': 103, 'n': 104}

# division_teams: dictionary to provide list of teams in each division
# division_to_id: dictionary to provide translation from division to its API id
# id_to_division: dictionary to provide translation from API id to division name
division_teams, division_to_id, id_to_division = get_division_data()

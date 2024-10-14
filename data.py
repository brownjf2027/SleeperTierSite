# Sleeper Tiers
# BSD-3-Clause License
# Copyright (c) [2024] [Jasen Brown
import requests
import json
from datetime import datetime

PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
DRAFT_URL = "https://api.sleeper.app/v1/draft/"
USER_URL = "https://api.sleeper.app/v1/user/"
LEAGUES_BY_USER = "https://api.sleeper.app/v1/user/<user_id>/leagues/nfl/<season>"
DRAFTS_BY_USER = "https://api.sleeper.app/v1/user/<user_id>/drafts/nfl/<season>"
TOP_X_PLAYERS = 750


def get_projections(player_id, season):
    projections_url = f"https://api.sleeper.com/projections/nfl/player/{player_id}?season={season}&season_type=regular&grouping=season"
    parameters = {}
    response = requests.get(projections_url, params=parameters)
    response.raise_for_status()
    data = response.json()
    return data


def get_user(user_id: str):
    user_url = USER_URL + user_id
    parameters = {}
    response = requests.get(user_url, params=parameters)
    response.raise_for_status()
    data = response.json()
    print(data)
    return data


def get_draft(draft_id: str):
    parameters = {
        # "draft_id": draft_id
    }

    draft_api_url = DRAFT_URL + draft_id
    response = requests.get(draft_api_url, params=parameters)
    response.raise_for_status()
    data = response.json()

    with open("draft.json", "w") as data_file:
        json.dump(data, data_file, indent=4)
    return data


def get_draft_picks(draft_id: str):
    parameters = {
        # "draft_id": draft_id
    }

    draft_api_url = DRAFT_URL + draft_id + "/picks"
    response = requests.get(draft_api_url, params=parameters)
    response.raise_for_status()
    data = response.json()
    print(type(data))

    with open("draft_picks.json", "w") as data_file:
        json.dump(data, data_file, indent=4)
    return data


def update_players():
    parameters = {
    }

    response = requests.get("https://api.sleeper.app/v1/state/nfl")
    response.raise_for_status()
    data = response.json()
    nfl_year = data['league_season']

    response = requests.get(PLAYERS_URL, params=parameters)
    response.raise_for_status()
    data = response.json()

    for player, values in data.items():
        print(f"player: {player}")
        projections = get_projections(player, nfl_year)
        if projections:
            values['stats'] = projections['stats']
        else:
            values['stats'] = {}

    with open("players.json", "w") as data_file:
        json.dump(data, data_file, indent=4)


def get_csv():
    with open("csv_upload.json", "r") as data_file:
        players_data = json.load(data_file)
        return players_data


def get_leagues(year, user_id):
    leagues_url = LEAGUES_BY_USER.replace("<user_id>", user_id)
    leagues_url = leagues_url.replace("<season>", str(year))
    parameters = {}
    response = requests.get(leagues_url, params=parameters)
    response.raise_for_status()
    data = response.json()
    print(data)
    return data


def get_drafts(year, user_id):
    user_data = get_user(user_id)
    user = user_data["user_id"]
    drafts_url = DRAFTS_BY_USER.replace("<user_id>", user)
    drafts_url = drafts_url.replace("<season>", str(year))
    parameters = {}
    response = requests.get(drafts_url, params=parameters)
    response.raise_for_status()
    data = response.json()
    print(data)
    return data


def top_players():
    with open("top_players.json", "r") as data_file:
        players_data = json.load(data_file)
        return players_data


def get_players():
    with open("players.json", "r") as data_file:
        players_data = json.load(data_file)
        return players_data


def get_top_players():
    with open("players.json", "r") as data_file:
        players_data = json.load(data_file)

    top_players = {}

    # Filter players who have pts_half_ppr value
    players_with_adp = {k: v for k, v in players_data.items() if v['stats'].get('pts_half_ppr')}

    # Sort players based on pts_half_ppr value in reverse order (highest first)
    sorted_players = sorted(players_with_adp.items(), key=lambda x: x[1]['stats']['pts_half_ppr'], reverse=True)

    # Select top X players
    for player_id, player_data in sorted_players[:TOP_X_PLAYERS]:
        top_players[player_id] = player_data
        top_players[player_id]['tier'] = 99

    # print(f"{len(top_players)}")
    with open("top_players.json", "w") as data_file:
        json.dump(top_players, data_file, indent=4)

    return top_players


def get_rosters(league_id):
    response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    response.raise_for_status()
    data = response.json()
    return data


def get_rest_of_season_projections(player_id):
    """
    Given a player ID, fetches the player's weekly projection data from Sleeper API
    and returns the total points for pts_ppr, pts_half_ppr, and pts_std.
    """
    # Get the current NFL season year and week
    response = requests.get("https://api.sleeper.app/v1/state/nfl")
    response.raise_for_status()
    data = response.json()
    nfl_year = data['league_season']
    nfl_week = data['week']

    # Fetch projections for the player
    projections_base_url = f"https://api.sleeper.com/projections/nfl/player/{player_id}?season_type=regular&season={nfl_year}&grouping=week"
    response = requests.get(projections_base_url)
    response.raise_for_status()
    data = response.json()

    # Dictionary to store points data
    points_dict = {}

    # Iterate through each week and collect points data for weeks less than the current NFL week
    for week, details in data.items():
        if week.isdigit() and int(week) >= nfl_week:
            if details is not None:
                stats = details.get('stats', {})
                points_dict[int(week)] = {
                    'pts_ppr': stats.get('pts_ppr', 0),
                    'pts_half_ppr': stats.get('pts_half_ppr', 0),
                    'pts_std': stats.get('pts_std', 0)
                }
            else:
                points_dict[int(week)] = {'pts_ppr': 0, 'pts_half_ppr': 0, 'pts_std': 0}

    # Initialize total counters
    total_pts_ppr = 0
    total_pts_half_ppr = 0
    total_pts_std = 0

    # Iterate over the points_dict and sum up the values
    for week, points in points_dict.items():
        total_pts_ppr += points['pts_ppr']
        total_pts_half_ppr += points['pts_half_ppr']
        total_pts_std += points['pts_std']

    # Return the totals as a dictionary
    return {'weeks_detail': points_dict,
            'total_pts_ppr': total_pts_ppr,
            'total_pts_half_ppr': total_pts_half_ppr,
            'total_pts_std': total_pts_std
            }


def get_previous_projections(player_id):
    """
    Given a player ID, fetches the player's weekly projection data from Sleeper API
    and returns the total points for pts_ppr, pts_half_ppr, and pts_std.
    """
    # Get the current NFL season year and week
    response = requests.get("https://api.sleeper.app/v1/state/nfl")
    response.raise_for_status()
    data = response.json()
    nfl_year = data['league_season']
    nfl_week = data['week']

    # Fetch projections for the player
    projections_base_url = f"https://api.sleeper.com/projections/nfl/player/{player_id}?season_type=regular&season={nfl_year}&grouping=week"
    response = requests.get(projections_base_url)
    response.raise_for_status()
    data = response.json()

    # Dictionary to store points data
    points_dict = {}

    # Iterate through each week and collect points data for weeks less than the current NFL week
    for week, details in data.items():
        if week.isdigit() and int(week) < nfl_week:
            if details is not None:
                stats = details.get('stats', {})
                points_dict[int(week)] = {
                    'pts_ppr': stats.get('pts_ppr', 0),
                    'pts_half_ppr': stats.get('pts_half_ppr', 0),
                    'pts_std': stats.get('pts_std', 0)
                }
            else:
                points_dict[int(week)] = {'pts_ppr': 0, 'pts_half_ppr': 0, 'pts_std': 0}

    # Initialize total counters
    total_pts_ppr = 0
    total_pts_half_ppr = 0
    total_pts_std = 0
    non_zero_weeks = 0

    # Iterate over the points_dict and sum up the values
    for week, points in points_dict.items():
        total_pts_ppr += points['pts_ppr']
        total_pts_half_ppr += points['pts_half_ppr']
        total_pts_std += points['pts_std']

        if points['pts_half_ppr'] > 0:
            non_zero_weeks += 1

    # Return the totals as a dictionary
    return {'weeks_detail': points_dict,
            'total_pts_ppr': total_pts_ppr,
            'total_pts_half_ppr': total_pts_half_ppr,
            'total_pts_std': total_pts_std,
            'non_zero': non_zero_weeks
            }


def get_previous_scores(player_id):
    """
    Given a player ID, fetches the player's weekly projection data from Sleeper API
    and returns the total points for pts_ppr, pts_half_ppr, and pts_std.
    """
    # Get the current NFL season year and week
    response = requests.get("https://api.sleeper.app/v1/state/nfl")
    response.raise_for_status()
    data = response.json()
    nfl_year = data['league_season']
    nfl_week = data['week']

    # Fetch projections for the player
    stats_base_url = f"https://api.sleeper.com/stats/nfl/player/{player_id}?season_type=regular&season={nfl_year}&grouping=week"
    response = requests.get(stats_base_url)
    response.raise_for_status()
    data = response.json()

    # Dictionary to store points data
    points_dict = {}

    # Initialize total counters
    total_pts_ppr = 0
    total_pts_half_ppr = 0
    total_pts_std = 0
    total_active = 0

    # Iterate through each week and collect points data for weeks less than the current NFL week
    for week, details in data.items():
        if week.isdigit() and int(week) < nfl_week:
            if details is not None:
                stats = details.get('stats', {})
                points_dict[int(week)] = {
                    'pts_ppr': stats.get('pts_ppr', 0),
                    'pts_half_ppr': stats.get('pts_half_ppr', 0),
                    'pts_std': stats.get('pts_std', 0),
                    'active': stats.get('gms_active', 0)
                }
            else:
                points_dict[int(week)] = {'pts_ppr': 0, 'pts_half_ppr': 0, 'pts_std': 0, 'active': 0}

    # Iterate over the points_dict and sum up the values
    for week, points in points_dict.items():
        total_pts_ppr += points['pts_ppr']
        total_pts_half_ppr += points['pts_half_ppr']
        total_pts_std += points['pts_std']
        total_active += points['active']

    # Return the totals as a dictionary
    return {'weeks_detail': points_dict,
            'total_pts_ppr': total_pts_ppr,
            'total_pts_half_ppr': total_pts_half_ppr,
            'total_pts_std': total_pts_std,
            'non_zero': total_active
            }


def calculate_variance(player_id):
    """
    Given a player ID, calculates the variance between the player's previous projections and actual scores.
    Returns a dictionary with variance for pts_ppr, pts_half_ppr, and pts_std per week.
    """
    # Get previous projections and actual scores
    projections = get_previous_projections(player_id)
    scores = get_previous_scores(player_id)

    # Initialize dictionary to store variance data
    variance_dict = {}

    # Iterate through each week in projections and calculate the variance
    for week, proj_data in projections['weeks_detail'].items():
        actual_data = scores['weeks_detail'].get(week, {'pts_ppr': 0, 'pts_half_ppr': 0, 'pts_std': 0})

        variance_dict[week] = {
            'pts_ppr_variance': actual_data['pts_ppr'] - proj_data['pts_ppr'],
            'pts_half_ppr_variance': actual_data['pts_half_ppr'] - proj_data['pts_half_ppr'],
            'pts_std_variance': actual_data['pts_std'] - proj_data['pts_std']
        }

    # Return the variance along with totals for projections and actual scores
    return {
        'variance': variance_dict,
        'total_projection': projections,
        'total_actual_scores': scores
    }


def update_player_data_for_site():
    print(f"Updating player data at {datetime.now()}")
    update_players()
    get_top_players()
    print(f"Update finished at {datetime.now()}")


# get_draft("1071375774982234112")
# get_draft_picks("1052865939722690560")

# try:
#     user_data = get_user("jfbrown")
#     yr = datetime.now().year
#     drafts = get_drafts(yr, user_data["user_id"])
#     print(drafts)
#
# except requests.RequestException:
#     print("not found")
# update_players()

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
TOP_X_PLAYERS = 500


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
    response = requests.get(PLAYERS_URL, params=parameters)
    response.raise_for_status()
    data = response.json()

    for player, values in data.items():
        print(f"player: {player}")
        projections = get_projections(player, "2024")
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

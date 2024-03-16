import copy
import requests
import json

LEAGUE_URL_START = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
#year
LEAGUE_URL_MIDDLE = "/segments/0/leagues/"
# 278532 - league id
LEAGUE_URL_END= "?view=mDraftDetail&view=mSettings&view=mTeam&view=modular&view=mNav"

DRAFT_URL = "https://api.sleeper.app/v1/draft/"
USER_URL = "GET https://api.sleeper.app/v1/user/"
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


# update_players()
# get_top_players()
# get_draft("1071375774982234112")
# get_draft_picks("1052865939722690560")

from bs4 import BeautifulSoup
import requests
import json
import data

PLAYER = "8155"
user = data.get_user("jfbrown")
leagues = data.get_leagues(2024, user['user_id'])
print(leagues)
league_id = leagues[0]['league_id']

rosters = data.get_rosters(league_id)
roster = next((roster for roster in rosters if roster['owner_id'] == user['user_id']), None)

roster_detail = []
for player in roster['players']:
    variance_data = data.calculate_variance(player)
    roster_detail.append(
        dict(id=player, variance=variance_data)
                         )
print(roster)

# response = requests.get("https://fantasyfootball.theringer.com/")
# contents = response.text
#
# soup = BeautifulSoup(contents, "html.parser")
#
# script_tag = soup.find(name="script", id="__NEXT_DATA__")
#
# # print(soup.prettify())
#
# if script_tag:
#     script_content = script_tag.string
#     print("Script content:", script_content[:500])  # Print the first 500 characters for inspection
#     try:
#         data = json.loads(script_content)
#         players = data['props']['pageProps']['playerData']
#         qbs = data['props']['pageProps']['tiers']['qb']['halfpoint'][0]
#
#         qb_list = []
#         print(type(players))
#         for qb in qbs:
#             for player in players:
#                 print(player)
#                 print(qb)
#                 if player == qb:
#                     new_player = {
#                         "first_name": players[qb]['first_name'],
#                         "last_name": players[qb]['last_name'],
#                         "order_halfpoint": players[qb]['order_halfpoint']
#                     }
#                     qb_list.append(new_player)
#
#         print(qb_list)
#     except json.JSONDecodeError as e:
#         print("JSON decode error:", e)
# else:
#     print("No script tag with id '__NEXT_DATA__' found")
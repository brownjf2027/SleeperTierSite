from bs4 import BeautifulSoup
import requests
import json

response = requests.get("https://fantasyfootball.theringer.com/")
contents = response.text

soup = BeautifulSoup(contents, "html.parser")

# print(soup.prettify())

data = json.loads(soup.find(name="script", id="__NEXT_DATA__").text)

players = data['props']['pageProps']['playerData']
qbs = data['props']['pageProps']['tiers']['qb']['halfpoint'][0]

qb_list = []
print(type(players))
for qb in qbs:
    for player in players:
        print(player)
        print(qb)
        if player == qb:
            new_player = {
                "first_name": players[qb]['first_name'],
                "last_name": players[qb]['last_name'],
                "order_halfpoint": players[qb]['order_halfpoint']
            }
            qb_list.append(new_player)

print(qb_list)

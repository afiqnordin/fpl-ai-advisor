import requests

print("Connecting to FPL API...")

url = "https://fantasy.premierleague.com/api/bootstrap-static/"
response = requests.get(url)
data = response.json()

players = data['elements']
teams = data['teams']

print(f"✅ Connected! Total players: {len(players)}")
print()

# Top 5 players by total points
print("🏆 TOP 5 PLAYERS BY POINTS THIS SEASON:")
sorted_players = sorted(players, key=lambda x: x['total_points'], reverse=True)

for i, p in enumerate(sorted_players[:5]):
    team_name = teams[p['team']-1]['name']
    print(f"  {i+1}. {p['web_name']} ({team_name}) — £{p['now_cost']/10}m — {p['total_points']} pts — Form: {p['form']}")

print()

# Top 5 by form
print("🔥 TOP 5 IN-FORM PLAYERS RIGHT NOW:")
sorted_by_form = sorted(players, key=lambda x: float(x['form']), reverse=True)

for i, p in enumerate(sorted_by_form[:5]):
    team_name = teams[p['team']-1]['name']
    print(f"  {i+1}. {p['web_name']} ({team_name}) — £{p['now_cost']/10}m — Form: {p['form']} — {p['total_points']} pts")
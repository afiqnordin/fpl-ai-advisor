from fpl_auth import get_my_team, format_team_for_agent

print("Fetching your FPL team...")
team = get_my_team()
print(format_team_for_agent(team))
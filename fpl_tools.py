import requests

FPL_BASE = "https://fantasy.premierleague.com/api"

def _get_bootstrap():
    """Cached bootstrap fetch — all base FPL data"""
    return requests.get(f"{FPL_BASE}/bootstrap-static/").json()

def get_top_performers():
    """Top 15 in-form players with full context"""
    data = _get_bootstrap()
    players = data['elements']
    teams = {t['id']: t['name'] for t in data['teams']}
    position_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    sorted_players = sorted(players, key=lambda x: float(x['form']), reverse=True)

    result = []
    for p in sorted_players[:15]:
        status = {"a": "Available", "i": "Injured", "d": "Doubtful", "s": "Suspended"}.get(p['status'], "Unknown")
        result.append({
            "name": p['web_name'],
            "team": teams[p['team']],
            "position": position_map[p['element_type']],
            "price": p['now_cost'] / 10,
            "form": float(p['form']),
            "total_points": p['total_points'],
            "points_per_game": float(p['points_per_game']),
            "selected_by_percent": float(p['selected_by_percent']),
            "goals": p['goals_scored'],
            "assists": p['assists'],
            "clean_sheets": p['clean_sheets'],
            "status": status,
            "news": p['news'],
        })
    return result

def get_fixtures_next_3_gw():
    """Fixture difficulty for all teams across next 3 gameweeks"""
    data = _get_bootstrap()
    fixtures = requests.get(f"{FPL_BASE}/fixtures/").json()
    teams = {t['id']: t['name'] for t in data['teams']}

    events = data['events']
    current_gw = next((e['id'] for e in events if e['is_current']),
                      next((e['id'] for e in events if e['is_next']), 1))

    upcoming_gws = [current_gw + 1, current_gw + 2, current_gw + 3]
    upcoming = [f for f in fixtures if f['event'] in upcoming_gws]

    # Build per-team difficulty summary
    team_fixtures = {}
    for f in upcoming:
        h = teams.get(f['team_h'], 'Unknown')
        a = teams.get(f['team_a'], 'Unknown')

        if h not in team_fixtures:
            team_fixtures[h] = []
        if a not in team_fixtures:
            team_fixtures[a] = []

        team_fixtures[h].append({
            "gameweek": f['event'],
            "opponent": a,
            "venue": "Home",
            "difficulty": f['team_h_difficulty']
        })
        team_fixtures[a].append({
            "gameweek": f['event'],
            "opponent": h,
            "venue": "Away",
            "difficulty": f['team_a_difficulty']
        })

    # Add average difficulty score
    result = []
    for team, fixtures_list in team_fixtures.items():
        avg_diff = sum(f['difficulty'] for f in fixtures_list) / len(fixtures_list) if fixtures_list else 5
        result.append({
            "team": team,
            "avg_difficulty_next_3gw": round(avg_diff, 1),
            "fixtures": fixtures_list
        })

    return sorted(result, key=lambda x: x['avg_difficulty_next_3gw'])

def get_injured_and_unavailable():
    """All players who are injured, doubtful, suspended or on loan"""
    data = _get_bootstrap()
    players = data['elements']
    teams = {t['id']: t['name'] for t in data['teams']}

    unavailable = []
    for p in players:
        if p['status'] != 'a':
            status = {"i": "Injured", "d": "Doubtful", "s": "Suspended", "u": "Unavailable"}.get(p['status'], p['status'])
            unavailable.append({
                "name": p['web_name'],
                "team": teams[p['team']],
                "status": status,
                "news": p['news'],
                "chance_of_playing_next_round": p['chance_of_playing_next_round'],
            })
    return unavailable

def get_player_detailed_stats(player_name: str):
    """Deep stats on a specific player — use when evaluating a transfer target"""
    data = _get_bootstrap()
    players = data['elements']
    teams = {t['id']: t['name'] for t in data['teams']}
    position_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    match = next((p for p in players if player_name.lower() in p['web_name'].lower()), None)
    if not match:
        return {"error": f"Player '{player_name}' not found"}

    # Get gameweek history
    player_detail = requests.get(f"{FPL_BASE}/element-summary/{match['id']}/").json()
    last_5_gw = player_detail['history'][-5:] if player_detail['history'] else []
    recent_points = [gw['total_points'] for gw in last_5_gw]

    return {
        "name": match['web_name'],
        "team": teams[match['team']],
        "position": position_map[match['element_type']],
        "price": match['now_cost'] / 10,
        "form": float(match['form']),
        "total_points": match['total_points'],
        "points_per_game": float(match['points_per_game']),
        "goals": match['goals_scored'],
        "assists": match['assists'],
        "clean_sheets": match['clean_sheets'],
        "bonus_points": match['bonus'],
        "selected_by_percent": float(match['selected_by_percent']),
        "status": match['status'],
        "news": match['news'],
        "last_5_gameweeks_points": recent_points,
        "expected_goals": match.get('expected_goals', 'N/A'),
        "expected_assists": match.get('expected_assists', 'N/A'),
        "expected_goal_involvements": match.get('expected_goal_involvements', 'N/A'),
    }

def get_value_picks(max_price: float, position: str):
    """Find best value players under a price threshold for a given position"""
    data = _get_bootstrap()
    players = data['elements']
    teams = {t['id']: t['name'] for t in data['teams']}
    position_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    position_id = {"GK": 1, "DEF": 2, "MID": 3, "FWD": 4}.get(position.upper())

    filtered = [
        p for p in players
        if p['now_cost'] / 10 <= max_price
        and p['element_type'] == position_id
        and p['status'] == 'a'
        and float(p['form']) > 0
    ]

    sorted_players = sorted(filtered, key=lambda x: float(x['points_per_game']), reverse=True)

    result = []
    for p in sorted_players[:10]:
        result.append({
            "name": p['web_name'],
            "team": teams[p['team']],
            "position": position_map[p['element_type']],
            "price": p['now_cost'] / 10,
            "form": float(p['form']),
            "points_per_game": float(p['points_per_game']),
            "total_points": p['total_points'],
            "selected_by_percent": float(p['selected_by_percent']),
        })
    return result
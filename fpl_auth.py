import requests
import os
from datetime import datetime, timezone

FPL_BASE = "https://fantasy.premierleague.com/api"

def get_my_team():
    """
    Fetches your team using public FPL endpoints.
    Only requires FPL_MANAGER_ID — no login needed.
    Free transfers read from FPL_FREE_TRANSFERS env variable.
    """
    manager_id = os.environ.get("FPL_MANAGER_ID")

    if not manager_id:
        raise ValueError("Missing FPL_MANAGER_ID environment variable")

    session = requests.Session()

    # ── GET BOOTSTRAP DATA ─────────────────────────────
    bootstrap = session.get(f"{FPL_BASE}/bootstrap-static/").json()
    players_lookup = {p['id']: p for p in bootstrap['elements']}
    teams_lookup   = {t['id']: t['name'] for t in bootstrap['teams']}
    position_map   = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    # ── FIND CURRENT GAMEWEEK ──────────────────────────
    events        = bootstrap['events']
    current_event = next((e for e in events if e['is_current']), None)
    next_event    = next((e for e in events if e['is_next']), None)

    if current_event:
        deadline = datetime.fromisoformat(
            current_event['deadline_time'].replace('Z', '+00:00')
        )
        now = datetime.now(timezone.utc)
        if now > deadline and next_event:
            current_gw = next_event['id']
        else:
            current_gw = current_event['id']
    elif next_event:
        current_gw = next_event['id']
    else:
        current_gw = 1

    # ── GET YOUR TEAM PICKS ────────────────────────────
    picks_url      = f"{FPL_BASE}/entry/{manager_id}/event/{current_gw}/picks/"
    picks_response = session.get(picks_url)

    if picks_response.status_code != 200:
        picks_url      = f"{FPL_BASE}/entry/{manager_id}/event/{current_gw - 1}/picks/"
        picks_response = session.get(picks_url)

    picks_data = picks_response.json()

    # ── GET BUDGET ─────────────────────────────────────
    entry_data = session.get(f"{FPL_BASE}/entry/{manager_id}/").json()
    bank       = entry_data.get('last_deadline_bank', 0) / 10

    # ── FREE TRANSFERS ─────────────────────────────────
    # FPL public API does not expose next GW free transfers directly.
    # Read from FPL_FREE_TRANSFERS env variable — set this in GitHub Secrets.
    # Update it manually each week when your count changes.
    # Default: 1 (always safe minimum)
    ft            = os.environ.get("FPL_FREE_TRANSFERS", "1")
    free_transfers = int(ft)

    # ── ENRICH PICKS WITH PLAYER DATA ─────────────────
    my_players = []
    for pick in picks_data['picks']:
        player = players_lookup[pick['element']]
        my_players.append({
            "name":           player['web_name'],
            "full_name":      f"{player['first_name']} {player['second_name']}",
            "team":           teams_lookup[player['team']],
            "position":       position_map[player['element_type']],
            "price":          player['now_cost'] / 10,
            "form":           float(player['form']),
            "total_points":   player['total_points'],
            "points_per_game":float(player['points_per_game']),
            "status":         player['status'],
            "news":           player['news'],
            "is_captain":     pick['is_captain'],
            "is_vice_captain":pick['is_vice_captain'],
            "multiplier":     pick['multiplier'],
        })

    return {
        "manager_id":       manager_id,
        "current_gameweek": current_gw,
        "budget_remaining": bank,
        "free_transfers":   free_transfers,
        "players":          my_players
    }


def format_team_for_agent(team_data: dict) -> str:
    """Formats your team into a clean string for the agent prompt."""
    lines = []
    lines.append(f"Gameweek: {team_data['current_gameweek']}")
    lines.append(f"Budget in bank: £{team_data['budget_remaining']}m")
    lines.append(f"Free transfers: {team_data['free_transfers']}")
    lines.append("")
    lines.append("Current squad:")

    for pos in ["GK", "DEF", "MID", "FWD"]:
        pos_players = [p for p in team_data['players'] if p['position'] == pos]
        for p in pos_players:
            captain = " 👑 CAPTAIN" if p['is_captain'] else ""
            vc      = " © VC"       if p['is_vice_captain'] else ""
            bench   = " (BENCH)"    if p['multiplier'] == 0 else ""
            status  = f" ⚠️ {p['news']}" if p['status'] != 'a' else ""
            lines.append(
                f"  {pos} | {p['name']} ({p['team']}) "
                f"£{p['price']}m | Form: {p['form']} | "
                f"{p['total_points']}pts{captain}{vc}{bench}{status}"
            )

    return "\n".join(lines)
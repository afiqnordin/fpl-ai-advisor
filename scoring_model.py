# scoring_model.py
# Moneyball-inspired player scoring model for FPL
# Ranks every player using weighted statistical metrics
# Claude reasons on top of these scores — not raw intuition

def normalise(value, min_val, max_val):
    """Scale any value to 0-1 range for fair comparison across metrics"""
    if max_val == min_val:
        return 0
    return max(0, min(1, (value - min_val) / (max_val - min_val)))


def score_players(players_raw: list, fixtures_by_team: dict) -> list:
    """
    Takes raw FPL player data and fixture difficulty data.
    Returns every player with a composite Moneyball score attached.

    Scoring dimensions:
      xG per 90        20% — underlying goal threat (luck-normalised)
      xA per 90        15% — underlying creative threat
      Points per game  20% — consistency over the season
      Fixture score    20% — next 3 GW difficulty (easier = higher)
      Price efficiency 15% — total points per £1m spent
      Bonus rate       10% — bonus points per game played
    
    Differential multiplier:
      Low ownership players get a boost — Moneyball edge logic.
      Finding undervalued assets = rank upside over other managers.
    """

    # ── WEIGHTS ───────────────────────────────────────────
    WEIGHTS = {
        "xg_per90":        0.20,
        "xa_per90":        0.15,
        "points_per_game": 0.20,
        "fixture_score":   0.20,
        "price_efficiency":0.15,
        "bonus_rate":      0.10,
    }

    # ── EXTRACT RAW VALUES ────────────────────────────────
    scored = []

    for p in players_raw:
        # Skip unavailable players entirely
        if p['status'] not in ['a', 'd']:
            continue

        # Skip players with no minutes (no data to score)
        minutes = p.get('minutes', 0)
        if minutes < 90:
            continue

        price = p['now_cost'] / 10
        games_played = max(1, minutes // 90)

        # xG and xA per 90 mins
        xg = float(p.get('expected_goals', 0) or 0)
        xa = float(p.get('expected_assists', 0) or 0)
        xg_per90 = (xg / minutes) * 90 if minutes > 0 else 0
        xa_per90 = (xa / minutes) * 90 if minutes > 0 else 0

        # Points per game
        ppg = float(p.get('points_per_game', 0) or 0)

        # Price efficiency — points per £1m
        total_points = p.get('total_points', 0)
        price_efficiency = total_points / price if price > 0 else 0

        # Bonus rate — bonus points per game played
        bonus = p.get('bonus', 0)
        bonus_rate = bonus / games_played if games_played > 0 else 0

        # Fixture score — avg difficulty next 3 GW, inverted
        # (difficulty 1 = easiest = highest fixture score)
        team_name = p.get('_team_name', '')
        team_fixtures = fixtures_by_team.get(team_name, [])
        if team_fixtures:
            avg_difficulty = sum(
                f['difficulty'] for f in team_fixtures[:3]
            ) / min(3, len(team_fixtures))
        else:
            avg_difficulty = 3  # neutral if no fixture data
        fixture_score = (6 - avg_difficulty) / 5  # invert: easy = high score

        # Ownership
        ownership = float(p.get('selected_by_percent', 0) or 0)

        scored.append({
            "id": p['id'],
            "name": p['web_name'],
            "team": p.get('_team_name', ''),
            "position": p.get('_position', ''),
            "price": price,
            "status": p['status'],
            "news": p.get('news', ''),
            "ownership_percent": ownership,
            "total_points": total_points,
            "minutes": minutes,

            # Raw metrics (for transparency in agent output)
            "metrics": {
                "xg_per90": round(xg_per90, 3),
                "xa_per90": round(xa_per90, 3),
                "points_per_game": ppg,
                "fixture_score": round(fixture_score, 3),
                "price_efficiency": round(price_efficiency, 2),
                "bonus_rate": round(bonus_rate, 2),
                "avg_fixture_difficulty": round(avg_difficulty, 1),
            }
        })

    # ── NORMALISE EACH METRIC ACROSS ALL PLAYERS ──────────
    # So metrics with different scales are fairly weighted
    for metric in WEIGHTS.keys():
        values = [p["metrics"][metric] for p in scored]
        min_v, max_v = min(values), max(values)
        for p in scored:
            p["metrics"][f"{metric}_norm"] = normalise(
                p["metrics"][metric], min_v, max_v
            )

    # ── COMPUTE COMPOSITE SCORE ───────────────────────────
    for p in scored:
        raw_score = sum(
            WEIGHTS[metric] * p["metrics"][f"{metric}_norm"]
            for metric in WEIGHTS.keys()
        )

        # Differential multiplier — Moneyball edge
        # Low ownership = higher upside vs the field
        differential_boost = 1 + (1 - p["ownership_percent"] / 100) * 0.3
        p["moneyball_score"] = round(raw_score * differential_boost * 100, 1)

    # ── SORT BY SCORE ─────────────────────────────────────
    scored.sort(key=lambda x: x["moneyball_score"], reverse=True)

    return scored


def get_scored_players(bootstrap_data: dict, fixtures_by_team: dict) -> list:
    """
    Entry point. Takes bootstrap API data + fixture lookup.
    Returns full scored + ranked player list.
    """
    raw_players = bootstrap_data['elements']
    teams = {t['id']: t['name'] for t in bootstrap_data['teams']}
    position_map = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

    # Enrich players with team name and position label
    for p in raw_players:
        p['_team_name'] = teams.get(p['team'], 'Unknown')
        p['_position'] = position_map.get(p['element_type'], 'Unknown')

    return score_players(raw_players, fixtures_by_team)


def format_top_candidates(scored_players: list, position: str = None,
                           max_price: float = None, limit: int = 15,
                           exclude_names: list = None) -> str:
    """
    Formats top scored players into a clean string for the agent prompt.
    Optionally filter by position and max price.
    Excludes players already in the manager's squad.
    """
    filtered = scored_players

    if position:
        filtered = [p for p in filtered if p['position'] == position]

    if max_price:
        filtered = [p for p in filtered if p['price'] <= max_price]

    if exclude_names:
        exclude_lower = [n.lower() for n in exclude_names]
        filtered = [
            p for p in filtered
            if p['name'].lower() not in exclude_lower
        ]

    top = filtered[:limit]

    lines = []
    for i, p in enumerate(top):
        m = p['metrics']
        status = "⚠️ Doubtful" if p['status'] == 'd' else "✅"
        lines.append(
            f"{i+1}. {p['name']} ({p['team']}, {p['position']}) "
            f"£{p['price']}m | Score: {p['moneyball_score']}/100 | "
            f"PPG: {m['points_per_game']} | "
            f"xG/90: {m['xg_per90']} | xA/90: {m['xa_per90']} | "
            f"Fixture ease: {m['fixture_score']:.2f} | "
            f"Owned: {p['ownership_percent']}% | {status}"
        )
        if p['news']:
            lines.append(f"   ⚠️ {p['news']}")

    return "\n".join(lines)
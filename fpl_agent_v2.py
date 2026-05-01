# fpl_agent_v2.py
# Agentic FPL Transfer Advisor
# Moneyball persona + scoring model + web search + tool loop

import anthropic
import os
import json
import requests
from datetime import datetime, timezone

from fpl_auth import get_my_team, format_team_for_agent
from fpl_tools import (
    get_top_performers,
    get_fixtures_next_3_gw,
    get_injured_and_unavailable,
    get_player_detailed_stats,
    get_value_picks,
    get_fixtures_by_team
)
from scoring_model import get_scored_players, format_top_candidates
from email_formatter import format_email_html, format_email_subject
from email_sender import send_email

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


# ── DEADLINE GATE ─────────────────────────────────────
def should_run_today(bootstrap_data: dict) -> tuple:
    events = bootstrap_data['events']
    now = datetime.now(timezone.utc)

    upcoming = [
        e for e in events
        if datetime.fromisoformat(
            e['deadline_time'].replace('Z', '+00:00')
        ) > now
    ]

    if not upcoming:
        return False, "No upcoming gameweeks found"

    next_deadline = datetime.fromisoformat(
        upcoming[0]['deadline_time'].replace('Z', '+00:00')
    )
    hours_until = (next_deadline - now).total_seconds() / 3600

    if hours_until <= 48:
        return True, f"GW{upcoming[0]['id']} deadline in {hours_until:.0f} hours"
    else:
        return False, f"GW{upcoming[0]['id']} deadline in {hours_until:.0f} hours — too early"


# ── TOOL DEFINITIONS ──────────────────────────────────
TOOLS = [
    {
        "name": "get_top_performers",
        "description": "Get top 15 in-form players with stats. Use as a starting point.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_fixtures_next_3_gw",
        "description": "Get fixture difficulty for all teams across next 3 gameweeks.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_injured_and_unavailable",
        "description": "Get all injured, doubtful or suspended players. Always check before recommending.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_player_detailed_stats",
        "description": "Deep stats on a specific player including last 5 GW points and xG/xA. Use to validate candidates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "Player surname e.g. 'Salah', 'Palmer', 'Mbeumo'"
                }
            },
            "required": ["player_name"]
        }
    },
    {
        "name": "get_value_picks",
        "description": "Find best value players under a budget for a position. Use when budget is tight.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_price": {"type": "number", "description": "Max price in £m e.g. 6.5"},
                "position": {"type": "string", "description": "GK, DEF, MID or FWD"}
            },
            "required": ["max_price", "position"]
        }
    },
    {
        "name": "search_news",
        "description": "Search the web for latest injury news, press conference updates, or team news for a player or team. Use before finalising any recommendation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query e.g. 'Salah injury news this week' or 'Arsenal team news GW33'"
                }
            },
            "required": ["query"]
        }
    }
]


# ── TOOL EXECUTOR ─────────────────────────────────────
def execute_tool(tool_name: str, tool_input: dict) -> dict:
    print(f"  🔧 [{tool_name}] {tool_input if tool_input else ''}")

    if tool_name == "get_top_performers":
        return get_top_performers()
    elif tool_name == "get_fixtures_next_3_gw":
        return get_fixtures_next_3_gw()
    elif tool_name == "get_injured_and_unavailable":
        return get_injured_and_unavailable()
    elif tool_name == "get_player_detailed_stats":
        return get_player_detailed_stats(tool_input.get("player_name", ""))
    elif tool_name == "get_value_picks":
        return get_value_picks(
            tool_input.get("max_price", 10.0),
            tool_input.get("position", "MID")
        )
    elif tool_name == "search_news":
        return {"error": "Web search handled natively by Anthropic"}
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ── MAIN AGENT ────────────────────────────────────────
def run_agent():
    print("=" * 60)
    print("🤖 FPL MONEYBALL ADVISOR")
    print("=" * 60)
    print()

    # Fetch bootstrap data once — reuse across everything
    print("📡 Fetching FPL data...")
    bootstrap = requests.get(
        "https://fantasy.premierleague.com/api/bootstrap-static/"
    ).json()

    # Deadline gate
    should_run, reason = should_run_today(bootstrap)
    print(f"⏰ {reason}")
    if not should_run:
        print("😴 Agent standing down — no action needed today.")
        return

    print("🚨 Within 48hr window — running full analysis...\n")

    # Load live team
    print("📋 Fetching your live squad...")
    team_data = get_my_team()
    team_text = format_team_for_agent(team_data)
    print("✅ Squad loaded.\n")

    # Run scoring model
    print("📊 Running Moneyball scoring model...")
    fixtures_by_team = get_fixtures_by_team()
    scored_players = get_scored_players(bootstrap, fixtures_by_team)

    # Get your squad names for exclusion
    my_player_names = [p['name'] for p in team_data['players']]

    # Format top candidates by position (excluding your players)
    top_mids = format_top_candidates(
        scored_players, position="MID",
        max_price=team_data['budget_remaining'] + 15,
        exclude_names=my_player_names, limit=10
    )
    top_fwds = format_top_candidates(
        scored_players, position="FWD",
        max_price=team_data['budget_remaining'] + 15,
        exclude_names=my_player_names, limit=10
    )
    top_defs = format_top_candidates(
        scored_players, position="DEF",
        max_price=team_data['budget_remaining'] + 15,
        exclude_names=my_player_names, limit=10
    )

    print("✅ Scoring model complete.\n")

    # ── MONEYBALL PERSONA ──────────────────────────────
    system_prompt = """You are a data scientist embedded in a Premier League analytics department. Your FPL philosophy is Moneyball — you distrust eye test and media narrative. You trust numbers.

Your priorities:
1. xG and xA per 90 — underlying production, luck-normalised
2. Consistency — points per game over explosiveness
3. Fixture runs — next 3 GW difficulty, not just this week
4. Differential value — low ownership + high output = rank upside
5. Price efficiency — points per £1m spent

The Moneyball Score (0-100) is pre-computed for every player. Trust it.

CRITICAL: Your ENTIRE response must be ONLY the JSON object. Start your response with { and end with }. No introduction, no explanation, no markdown fences. Just raw JSON.
Required JSON structure:
{
  "recommendations": [
    {
      "problem": "Brief problem description e.g. Man City blank risk",
      "confidence": "High|Medium|Low",
      "player_out": {
        "name": "player name",
        "team": "team name",
        "price": 0.0,
        "moneyball_score": 0.0,
        "metrics": {
          "xg_per90": 0.0,
          "xa_per90": 0.0,
          "points_per_game": 0.0,
          "fixture_score": 0.0
        }
      },
      "options": [
        {
          "name": "player name",
          "team": "team name",
          "price": 0.0,
          "moneyball_score": 0.0,
          "ownership_percent": 0.0,
          "metrics": {
            "xg_per90": 0.0,
            "xa_per90": 0.0,
            "points_per_game": 0.0,
            "fixture_score": 0.0
          }
        }
      ],
      "numbers": {
        "xg_per90":         {"out": "0.00", "in": "0.00"},
        "xa_per90":         {"out": "0.00", "in": "0.00"},
        "points_per_game":  {"out": "0.0",  "in": "0.0"},
        "form":             {"out": "0.0",  "in": "0.0"},
        "fixture_ease":     {"out": "2/5",  "in": "4/5"},
        "ownership_percent":{"out": "38%",  "in": "18%"},
        "moneyball_score":  {"out": "34",   "in": "84"}
      },
      "news": "One sentence from your web search about the recommended IN player",
      "reasoning": "2-3 sentences analytical justification citing specific numbers"
    }
  ],
  "captain": {
    "name": "player name",
    "reason": "One sentence statistical reason"
  },
  "avoid": {
    "name": "player name",
    "reason": "One sentence statistical reason"
  },
  "hidden_gem": {
    "name": "player name",
    "reason": "One sentence — low ownership, strong underlying stats",
    "score": 0.0
  }
}"""

    user_message = f"""Analyse my squad and recommend transfers for Gameweek {team_data['current_gameweek']}.

{team_text}

━━ MONEYBALL SCORES — TOP MIDFIELDERS (not in my squad) ━━
{top_mids}

━━ MONEYBALL SCORES — TOP FORWARDS (not in my squad) ━━
{top_fwds}

━━ MONEYBALL SCORES — TOP DEFENDERS (not in my squad) ━━
{top_defs}

Key constraints:
- Budget: £{team_data['budget_remaining']}m in bank
- Free transfers: {team_data['free_transfers']}
- Only recommend transfers for my STARTING XI (multiplier > 0). Ignore bench players entirely — do not recommend transferring out any bench player.
- My starting XI players are: {', '.join([p['name'] for p in team_data['players'] if p['multiplier'] > 0])}

Instructions:
1. Check injuries first
2. Search news for your top 2-3 candidates before recommending
3. Cross-reference Moneyball scores with fixture data
4. Give me transfer options ranked by statistical confidence. Give exactly {team_data['free_transfers']} recommendation(s) — one per free transfer — each targeting a different starting XI player.
5. Flag any blank gameweek risks in my current squad
6. Respond ONLY with the JSON structure specified. No text outside the JSON."""

    messages = [{"role": "user", "content": user_message}]

    # ── AGENTIC LOOP ───────────────────────────────────
    print("🧠 Agent reasoning...\n")
    iteration = 0
    max_iterations = 15
    agent_output = None

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model="claude-sonnet-4-6",
            #model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS + [{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # Skip web search — Anthropic handles it natively
                    if block.name == "web_search":
                        continue
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            raw_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    raw_text += block.text

            print()
            print("=" * 60)
            print("Raw agent output:")
            print(raw_text[:500])
            print("=" * 60)

            try:
                clean = raw_text.strip()
                # Handle markdown fences
                if "```json" in clean:
                    clean = clean.split("```json")[1].split("```")[0]
                elif "```" in clean:
                    clean = clean.split("```")[1].split("```")[0]
                # Strip any text before first { and after last }
                if "{" in clean:
                    start = clean.index("{")
                    end   = clean.rindex("}") + 1
                    clean = clean[start:end]
                agent_output = json.loads(clean.strip())
                print("✅ JSON parsed successfully")
            except json.JSONDecodeError as e:
                print(f"❌ JSON parse error: {e}")
                print("Falling back to empty output")
                agent_output = {
                    "recommendations": [],
                    "captain": {"name": "Check manually", "reason": "JSON parse failed"},
                    "avoid": {"name": "N/A", "reason": ""},
                    "hidden_gem": {"name": "N/A", "reason": "", "score": 0}
                }

            print(f"✅ Agent completed in {iteration} reasoning steps.")
            break

    # ── SEND EMAIL ─────────────────────────────────────
    if agent_output:
        print()
        html, images = format_email_html(agent_output, team_data, fixtures_by_team)
        subject      = format_email_subject(team_data)
        send_email(subject, html, images)


if __name__ == "__main__":
    run_agent()
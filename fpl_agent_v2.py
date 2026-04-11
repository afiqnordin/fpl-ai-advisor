import anthropic
import os
import json
from datetime import datetime, timezone

def should_run_today(bootstrap_data: dict) -> tuple[bool, str]:
    """
    Checks if we're within 48 hours of the next relevant deadline.
    Returns (should_run, reason_string)
    """
    events = bootstrap_data['events']
    now = datetime.now(timezone.utc)

    # Find the next upcoming deadline
    upcoming = [
        e for e in events
        if datetime.fromisoformat(e['deadline_time'].replace('Z', '+00:00')) > now
    ]

    if not upcoming:
        return False, "No upcoming gameweeks found"

    next_deadline = datetime.fromisoformat(
        upcoming[0]['deadline_time'].replace('Z', '+00:00')
    )
    hours_until_deadline = (next_deadline - now).total_seconds() / 3600

    if hours_until_deadline <= 48:
        return True, f"GW{upcoming[0]['id']} deadline in {hours_until_deadline:.0f} hours"
    else:
        return False, f"GW{upcoming[0]['id']} deadline in {hours_until_deadline:.0f} hours — too early"
from email_formatter import format_email_html, format_email_subject
from email_sender import send_email
from fpl_auth import get_my_team, format_team_for_agent
from fpl_tools import (
    get_top_performers,
    get_fixtures_next_3_gw,
    get_injured_and_unavailable,
    get_player_detailed_stats,
    get_value_picks
)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── TOOL DEFINITIONS ──────────────────────────────────
TOOLS = [
    {
        "name": "get_top_performers",
        "description": "Get top 15 in-form Premier League players with price, form, points, goals, assists and injury status. Always call this first.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_fixtures_next_3_gw",
        "description": "Get fixture difficulty ratings for all PL teams across the next 3 gameweeks. Use this to identify teams with easy runs.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_injured_and_unavailable",
        "description": "Get all players who are injured, doubtful, suspended or unavailable. Check this to avoid recommending unavailable players.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_player_detailed_stats",
        "description": "Get deep stats on a specific player including last 5 GW points, xG, xA. Use this to validate a transfer target before recommending.",
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
        "description": "Find best value players under a budget threshold for a specific position. Use this when the manager has limited budget.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_price": {
                    "type": "number",
                    "description": "Maximum price in £m e.g. 6.5"
                },
                "position": {
                    "type": "string",
                    "description": "Position: GK, DEF, MID or FWD"
                }
            },
            "required": ["max_price", "position"]
        }
    }
]

# ── TOOL EXECUTOR ─────────────────────────────────────
def execute_tool(tool_name, tool_input):
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
        return get_value_picks(tool_input.get("max_price", 10.0), tool_input.get("position", "MID"))
    else:
        return {"error": f"Unknown tool: {tool_name}"}

# ── AGENT LOOP ────────────────────────────────────────
def run_agent():
    print("=" * 60)
    print("🤖 FPL AGENTIC ADVISOR — GW ANALYSIS")
    print("=" * 60)
    print()

    # Load live team
    print("📡 Fetching your live FPL team...")
    team_data = get_my_team()
    team_text = format_team_for_agent(team_data)
    print("✅ Team loaded.\n")
    print(team_text)
    print()
    # Check if we should run today
    import requests
    bootstrap = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/").json()
    should_run, reason = should_run_today(bootstrap)

    print(f"⏰ Deadline check: {reason}")

    if not should_run:
        print("😴 Agent standing down — no action needed today.")
        return

    print("🚨 Within 48hr window — running full analysis...")
    print()
    system_prompt = """You are an elite FPL analyst agent with access to live Premier League data tools.

Your job is to give highly specific, data-driven transfer recommendations for THIS manager's exact squad.

Rules:
- Always use tools to gather data. Never guess.
- Check injuries before recommending anyone.
- Account for the manager's exact budget — they have very little in the bank.
- Consider fixture difficulty for the next 3 gameweeks, not just this week.
- Never recommend a player the manager already owns.
- Use get_player_detailed_stats to validate your top candidates before finalising.
- Factor in xG and xA when available — form can be misleading without underlying stats.

Output format (use this exactly):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔄 TRANSFER RECOMMENDATIONS — GW[X]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ PRIORITY TRANSFER
   OUT: [Player] (£Xm) → IN: [Player] (£Xm)
   Cost: £Xm | Budget after: £Xm
   Reason: [2-3 sentences — form, fixtures, stats]
   Confidence: High / Medium / Low

2️⃣ ALTERNATIVE TRANSFER
   OUT: [Player] → IN: [Player]
   ...

3️⃣ DIFFERENTIAL PICK (low ownership, high ceiling)
   OUT: [Player] → IN: [Player]
   ...

👑 CAPTAIN PICK: [Player] | [Reason]
⚠️  AVOID THIS WEEK: [Player] | [Reason]
📊 KEY INSIGHT: [One data-driven observation about the manager's squad]"""

    user_message = f"""Analyse my FPL squad and give me transfer recommendations for Gameweek {team_data['current_gameweek']}.

{team_text}

Important context:
- My budget is very tight (£{team_data['budget_remaining']}m in bank)
- I have {team_data['free_transfers']} free transfer(s)
- Haaland, Guéhi and Donnarumma are likely in a Man City blank — factor this in
- A.Ramsey on my bench is on loan to Leicester — completely useless
- Ekitiké has very low form (0.7) at £9.2m — may need addressing

Use your tools to analyse the market and give me specific, actionable recommendations."""

    messages = [{"role": "user", "content": user_message}]

    print("🧠 Agent reasoning...\n")

    # ── THE AGENTIC LOOP ──────────────────────────────
    iteration = 0
    max_iterations = 15

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            recommendation_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    recommendation_text += block.text

            # Print to terminal
            print()
            print("=" * 60)
            print(recommendation_text)
            print("=" * 60)
            print(f"✅ Agent completed in {iteration} reasoning steps.")

            # Send email
            print()
            html = format_email_html(recommendation_text, team_data)
            subject = format_email_subject(team_data)
            send_email(subject, html)
            break
        

    return messages

if __name__ == "__main__":
    run_agent()
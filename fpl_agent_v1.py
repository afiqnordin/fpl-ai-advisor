import requests
import anthropic
import os

# ── CLIENTS ──────────────────────────────────────────
fpl_client = requests.Session()
ai_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ── STEP 1: PULL LIVE FPL DATA ────────────────────────
print("📡 Fetching live FPL data...")
url = "https://fantasy.premierleague.com/api/bootstrap-static/"
data = fpl_client.get(url).json()

players = data['elements']
teams = data['teams']

# Build team name lookup
team_lookup = {t['id']: t['name'] for t in teams}

# ── STEP 2: FIND BEST CANDIDATES ──────────────────────
# Top 10 by form (these are your transfer targets)
sorted_by_form = sorted(players, key=lambda x: float(x['form']), reverse=True)
top_candidates = sorted_by_form[:10]

# Format for Claude
candidates_text = ""
for i, p in enumerate(top_candidates):
    team_name = team_lookup[p['team']]
    status = p['status']  # 'a' = available, 'i' = injured, 'd' = doubtful
    status_label = {"a": "✅ Available", "i": "❌ Injured", "d": "⚠️ Doubtful"}.get(status, status)
    
    candidates_text += f"""
{i+1}. {p['web_name']} ({team_name})
   Price: £{p['now_cost']/10}m | Points: {p['total_points']} | Form: {p['form']}
   Selected by: {p['selected_by_percent']}% of managers | Status: {status_label}
"""

# ── STEP 3: ASK CLAUDE TO REASON ──────────────────────
print("🤖 Agent is reasoning over transfer candidates...")
print()

prompt = f"""You are an elite FPL analyst agent. Your job is to recommend the top 3 transfer targets for this gameweek.

Here are the current top in-form players across the Premier League:

{candidates_text}

My constraints:
- Budget: £1.5m in the bank (standard assumption for now)
- Free transfers available: 1
- I want to maximise points over the next 3 gameweeks, not just this week

Your task:
1. Analyse each candidate considering form, price, ownership, and injury risk
2. Recommend your TOP 3 transfer targets in ranked order
3. For each: give the player name, one sharp reason why, and your confidence level (High / Medium / Low)
4. End with one sentence on who to AVOID this week and why

Be direct. Be specific. No generic advice."""

message = ai_client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1500,
    messages=[{"role": "user", "content": prompt}]
)

# ── STEP 4: PRINT THE RECOMMENDATION ──────────────────
print("=" * 60)
print("🎯 FPL AGENT — TRANSFER RECOMMENDATIONS")
print("=" * 60)
print()
print(message.content[0].text)
print()
print("=" * 60)
print("✅ Agent run complete.")
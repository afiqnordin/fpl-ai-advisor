# email_formatter.py
# Assembles the final HTML email from structured agent output.
# Charts embedded via CID attachment — works in Gmail.
# Only shows starting XI (multiplier > 0), not bench.

from datetime import datetime
from chart_generator import (
    generate_fixture_heatmap,
    generate_player_comparison_chart,
)

STATUS_CONFIG = {
    'a': ('✅', '#27ae60', 'Available'),
    'd': ('⚠️',  '#f39c12', 'Doubtful'),
    'i': ('❌', '#e74c3c', 'Injured'),
    's': ('🚫', '#e74c3c', 'Suspended'),
}


def _img_tag(cid: str, alt: str = "", width: str = "100%") -> str:
    """References an attached image by Content-ID — works in Gmail."""
    return (f'<img src="cid:{cid}" '
            f'alt="{alt}" width="{width}" '
            f'style="display:block; margin: 0 auto;" />')


def _squad_status_row(player: dict) -> str:
    """Renders one player row in the squad status table."""
    status = player.get('status', 'a')
    icon, colour, label = STATUS_CONFIG.get(status, ('✅', '#27ae60', 'Available'))
    captain = " 👑" if player.get('is_captain') else ""
    vc      = " ©"  if player.get('is_vice_captain') else ""
    news    = (f"<br><span style='color:{colour};font-size:11px'>"
               f"{player.get('news','')}</span>") \
              if player.get('news') else ""

    try:
        form_val   = float(player.get('form', 0))
        form_colour = '#f39c12' if form_val >= 6 else '#2c3e50'
    except Exception:
        form_colour = '#2c3e50'

    return f"""
    <tr style="border-bottom:1px solid #f0f0f0;">
      <td style="padding:7px 10px;font-weight:500;color:#2c3e50;">
        {player['name']}{captain}{vc}{news}
      </td>
      <td style="padding:7px 10px;color:#666;font-size:12px;">{player['team']}</td>
      <td style="padding:7px 10px;color:#666;font-size:12px;">{player['position']}</td>
      <td style="padding:7px 10px;font-size:12px;">£{player['price']}m</td>
      <td style="padding:7px 10px;font-size:12px;color:{form_colour};">
        {player.get('form', 'N/A')}
      </td>
      <td style="padding:7px 10px;font-size:12px;">{player.get('total_points',0)}pts</td>
      <td style="padding:7px 10px;font-size:13px;color:{colour};">{icon}</td>
    </tr>"""


def _recommendation_block(rec: dict, index: int) -> tuple:
    """
    Renders one full recommendation block.
    Only recommends players that are in the starting XI.
    Returns: (html_string, chart_bytes_or_None, chart_cid_string)
    """
    conf        = rec.get('confidence', 'Medium')
    conf_colour = {'High': '#27ae60', 'Medium': '#f39c12',
                   'Low': '#e74c3c'}.get(conf, '#f39c12')

    badge_colour = ['#3498db', '#27ae60', '#9b59b6'][index % 3]
    badge_labels = ['PRIORITY TRANSFER', 'SECOND TRANSFER', 'DIFFERENTIAL PICK']
    badge_label  = badge_labels[index % 3]

    # ── 3 OPTION CARDS ────────────────────────────────
    options_html = ""
    for i, opt in enumerate(rec.get('options', [])[:3]):
        is_best   = i == 0
        border    = f"3px solid {badge_colour}" if is_best else "1px solid #e0e0e0"
        bg        = "#f0f7ff" if is_best else "white"
        star      = " ⭐" if is_best else ""
        score     = float(opt.get('moneyball_score', 0))
        score_pct = min(int(score), 100)
        score_col = ('#27ae60' if score >= 70
                     else '#f39c12' if score >= 50
                     else '#e74c3c')

        options_html += f"""
        <td style="width:33%;padding:8px;vertical-align:top;">
          <div style="border:{border};border-radius:10px;padding:14px;
                      background:{bg};text-align:center;">
            <div style="font-size:11px;color:#888;text-transform:uppercase;
                        letter-spacing:0.5px;">Option {i+1}{star}</div>
            <div style="font-size:16px;font-weight:700;
                        color:#2c3e50;margin:6px 0;">
              {opt.get('name','?')}
            </div>
            <div style="font-size:12px;color:#666;">
              {opt.get('team','')} · £{opt.get('price',0)}m
            </div>
            <div style="font-size:11px;color:#888;margin-top:4px;">
              Owned: {opt.get('ownership_percent',0)}%
            </div>
            <div style="background:#f0f0f0;border-radius:4px;
                        height:6px;margin:10px 0 4px;">
              <div style="background:{score_col};width:{score_pct}%;
                          height:6px;border-radius:4px;"></div>
            </div>
            <div style="font-size:13px;font-weight:700;color:{score_col};">
              {score:.0f}/100
            </div>
          </div>
        </td>"""

    # ── COMPARISON CHART (OUT vs best IN) ─────────────
    player_out  = rec.get('player_out', {})
    best_in     = rec.get('options', [{}])[0]
    chart_cid   = f"chart_{index}"
    chart_bytes = None
    chart_html  = ""

    if player_out and best_in:
        try:
            chart_bytes = generate_player_comparison_chart(player_out, best_in)
            chart_html  = f"""
            <div style="margin:16px 0;">
              {_img_tag(chart_cid, 'Player Comparison Chart')}
            </div>"""
        except Exception as e:
            chart_html = (f"<p style='color:#aaa;font-size:12px;'>"
                          f"Chart unavailable: {e}</p>")

    # ── NUMBERS TABLE ──────────────────────────────────
    numbers   = rec.get('numbers', {})
    nums_html = ""
    if numbers:
        metric_labels = {
            'xg_per90':          'xG per 90',
            'xa_per90':          'xA per 90',
            'points_per_game':   'Points per Game',
            'form':              'Form (last 30d)',
            'fixture_ease':      'Fixture Ease (next 3)',
            'ownership_percent': 'Ownership %',
            'moneyball_score':   'Moneyball Score',
        }
        rows = ""
        for key, label in metric_labels.items():
            if key in numbers:
                out_v = numbers[key].get('out', 'N/A')
                in_v  = numbers[key].get('in',  'N/A')
                try:
                    better = (float(str(in_v).replace('%', '')) >
                              float(str(out_v).replace('%', '')))
                    in_col = '#27ae60' if better else '#e74c3c'
                except Exception:
                    in_col = '#2c3e50'

                rows += f"""
                <tr style="border-bottom:1px solid #f5f5f5;">
                  <td style="padding:6px 12px;font-size:12px;color:#555;">
                    {label}</td>
                  <td style="padding:6px 12px;font-size:12px;color:#e74c3c;
                              font-weight:500;text-align:center;">{out_v}</td>
                  <td style="padding:6px 12px;font-size:12px;color:{in_col};
                              font-weight:600;text-align:center;">{in_v}</td>
                </tr>"""

        nums_html = f"""
        <table style="width:100%;border-collapse:collapse;margin:12px 0;
                      background:#fafafa;border-radius:8px;">
          <thead>
            <tr style="background:#f0f0f0;">
              <th style="padding:8px 12px;font-size:11px;text-align:left;
                          color:#888;font-weight:600;">METRIC</th>
              <th style="padding:8px 12px;font-size:11px;text-align:center;
                          color:#e74c3c;font-weight:600;">
                OUT: {player_out.get('name','?')}</th>
              <th style="padding:8px 12px;font-size:11px;text-align:center;
                          color:#27ae60;font-weight:600;">
                IN: {best_in.get('name','?')}</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""

    # ── NEWS + REASONING ───────────────────────────────
    news      = rec.get('news', '')
    reasoning = rec.get('reasoning', '')

    news_html = f"""
    <div style="background:#fff8e1;border-left:3px solid #f39c12;
                padding:10px 14px;border-radius:0 6px 6px 0;
                margin:12px 0;font-size:13px;color:#555;">
      <strong>📰 News Check:</strong> {news}
    </div>""" if news else ""

    reasoning_html = f"""
    <div style="background:#f0f7ff;border-left:3px solid #3498db;
                padding:10px 14px;border-radius:0 6px 6px 0;
                margin:12px 0;font-size:13px;color:#2c3e50;line-height:1.6;">
      <strong>🧠 Analysis:</strong> {reasoning}
    </div>""" if reasoning else ""

    html = f"""
    <div style="background:white;border:1px solid #e0e0e0;
                border-top:4px solid {badge_colour};
                border-radius:10px;padding:20px;margin:16px 0;">

      <div style="display:inline-block;background:{badge_colour};color:white;
                  font-size:10px;font-weight:700;padding:3px 10px;
                  border-radius:20px;letter-spacing:1px;margin-bottom:12px;">
        {badge_label}
      </div>

      <div style="font-size:15px;color:#888;margin-bottom:4px;">
        🔴 Problem: {rec.get('problem','')}
      </div>
      <div style="font-size:18px;font-weight:700;color:#2c3e50;">
        OUT: {player_out.get('name','?')}
        <span style="color:#888;font-size:14px;">
          (£{player_out.get('price',0)}m)
        </span>
      </div>

      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        <tr>{options_html}</tr>
      </table>

      <div style="border-top:1px solid #f0f0f0;padding-top:16px;margin-top:8px;">
        <div style="font-size:12px;font-weight:600;color:#888;
                    text-transform:uppercase;letter-spacing:0.5px;
                    margin-bottom:8px;">
          📊 Statistical Comparison
        </div>
        {chart_html}
        {nums_html}
      </div>

      {news_html}
      {reasoning_html}

      <div style="text-align:right;margin-top:12px;">
        <span style="background:{conf_colour};color:white;font-size:11px;
                     font-weight:700;padding:3px 12px;border-radius:20px;">
          Confidence: {conf}
        </span>
      </div>
    </div>"""

    return html, chart_bytes, chart_cid


def format_email_html(agent_output: dict,
                      team_data: dict,
                      fixtures_by_team: dict) -> tuple:
    """
    Master function — assembles the full HTML email.
    Only uses starting XI (multiplier > 0) throughout.
    Returns: (html_string, images_dict)
    images_dict: {"cid": bytes} for CID email attachment.
    """
    gw             = team_data['current_gameweek']
    budget         = team_data['budget_remaining']
    free_transfers = team_data['free_transfers']
    date_str       = datetime.now().strftime("%A, %d %B %Y · %I:%M%p MYT")

    # Starting XI only
    starters = [p for p in team_data['players'] if p['multiplier'] > 0]

    images = {}  # CID → bytes, passed to email sender

    # ── HEATMAP ────────────────────────────────────────
    try:
        heatmap_bytes  = generate_fixture_heatmap(starters, fixtures_by_team, gw)
        images['heatmap'] = heatmap_bytes
        heatmap_html   = f"""
        <div style="background:white;border:1px solid #e0e0e0;
                    border-radius:10px;padding:20px;margin:16px 0;">
          <h2 style="color:#2c3e50;font-size:15px;
                     margin:0 0 16px 0;font-weight:700;">
            📊 Fixture Difficulty Heatmap — Starting XI
          </h2>
          {_img_tag('heatmap', 'Fixture Heatmap')}
        </div>"""
    except Exception as e:
        heatmap_html = f"<p style='color:#aaa;'>Heatmap unavailable: {e}</p>"

    # ── SQUAD TABLE (starters only) ────────────────────
    squad_rows = ""
    for pos in ["GK", "DEF", "MID", "FWD"]:
        for p in [x for x in starters if x['position'] == pos]:
            squad_rows += _squad_status_row(p)

    # ── RECOMMENDATIONS ────────────────────────────────
    recs_html = ""
    for i, rec in enumerate(agent_output.get('recommendations', [])):
        block_html, chart_bytes, chart_cid = _recommendation_block(rec, i)
        recs_html += block_html
        if chart_bytes:
            images[chart_cid] = chart_bytes

    # ── QUICK SUMMARY ──────────────────────────────────
    captain    = agent_output.get('captain', {})
    avoid      = agent_output.get('avoid', {})
    hidden_gem = agent_output.get('hidden_gem', {})

    summary_html = f"""
    <div style="background:white;border:1px solid #e0e0e0;
                border-radius:10px;padding:20px;margin:16px 0;">
      <h2 style="color:#2c3e50;font-size:15px;margin:0 0 16px 0;
                 font-weight:700;">Quick Summary</h2>
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:10px;background:#fff8e1;border-radius:8px;
                     width:33%;text-align:center;vertical-align:top;">
            <div style="font-size:20px;">👑</div>
            <div style="font-size:11px;color:#888;font-weight:600;
                        margin:4px 0;">CAPTAIN</div>
            <div style="font-size:15px;font-weight:700;color:#2c3e50;">
              {captain.get('name','TBC')}</div>
            <div style="font-size:11px;color:#666;margin-top:4px;">
              {captain.get('reason','')}</div>
          </td>
          <td style="width:2%;"></td>
          <td style="padding:10px;background:#fff0f0;border-radius:8px;
                     width:33%;text-align:center;vertical-align:top;">
            <div style="font-size:20px;">⚠️</div>
            <div style="font-size:11px;color:#888;font-weight:600;
                        margin:4px 0;">AVOID</div>
            <div style="font-size:15px;font-weight:700;color:#2c3e50;">
              {avoid.get('name','TBC')}</div>
            <div style="font-size:11px;color:#666;margin-top:4px;">
              {avoid.get('reason','')}</div>
          </td>
          <td style="width:2%;"></td>
          <td style="padding:10px;background:#f0fff4;border-radius:8px;
                     width:33%;text-align:center;vertical-align:top;">
            <div style="font-size:20px;">💎</div>
            <div style="font-size:11px;color:#888;font-weight:600;
                        margin:4px 0;">HIDDEN GEM</div>
            <div style="font-size:15px;font-weight:700;color:#2c3e50;">
              {hidden_gem.get('name','TBC')}</div>
            <div style="font-size:11px;color:#666;margin-top:4px;">
              {hidden_gem.get('reason','')}</div>
          </td>
        </tr>
      </table>
    </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f5f5f5;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);
              border-radius:16px 16px 0 0;padding:28px;text-align:center;">
    <div style="font-size:36px;margin-bottom:6px;">⚽</div>
    <h1 style="color:white;margin:0;font-size:22px;font-weight:700;">
      FPL Moneyball Advisor
    </h1>
    <p style="color:#a0aec0;margin:6px 0 0;font-size:13px;">
      Gameweek {gw} · {free_transfers} Free Transfer{'s' if free_transfers != 1 else ''} · £{budget}m in bank
    </p>
    <p style="color:#718096;margin:4px 0 0;font-size:11px;">{date_str}</p>
  </div>

  <!-- SQUAD STATUS — STARTING XI ONLY -->
  <div style="background:white;padding:20px;border:1px solid #e0e0e0;border-top:none;">
    <h2 style="color:#2c3e50;font-size:15px;margin:0 0 12px;font-weight:700;">
      📋 Starting XI Status
    </h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead>
        <tr style="background:#f8f9fa;">
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">PLAYER</th>
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">CLUB</th>
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">POS</th>
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">PRICE</th>
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">FORM</th>
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">PTS</th>
          <th style="padding:7px 10px;text-align:left;color:#888;
                     font-weight:600;font-size:11px;">STATUS</th>
        </tr>
      </thead>
      <tbody>{squad_rows}</tbody>
    </table>
  </div>

  <!-- HEATMAP -->
  {heatmap_html}

  <!-- RECOMMENDATIONS -->
  <h2 style="color:#2c3e50;font-size:16px;margin:24px 0 4px;font-weight:700;">
    🎯 Transfer Recommendations
  </h2>
  {recs_html}

  <!-- SUMMARY -->
  {summary_html}

  <!-- FOOTER -->
  <div style="background:#2c3e50;border-radius:0 0 16px 16px;
              padding:16px;text-align:center;margin-top:0;">
    <p style="color:#a0aec0;margin:0;font-size:11px;">
      FPL Moneyball Advisor · Powered by Claude (Anthropic) + FPL API
    </p>
    <p style="color:#718096;margin:4px 0 0;font-size:10px;">
      Moneyball Scoring Model v1.0 · Data: FPL API + Live Web Search
    </p>
  </div>

</div>
</body>
</html>"""

    return html, images


def format_email_subject(team_data: dict) -> str:
    gw = team_data['current_gameweek']
    return f"⚽ FPL Moneyball Advisor — GW{gw} Transfer Recommendations"
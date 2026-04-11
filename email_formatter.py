from datetime import datetime

def format_email_html(recommendation_text: str, team_data: dict) -> str:
    """
    Converts agent recommendation text into a clean HTML email.
    """
    gw = team_data['current_gameweek']
    budget = team_data['budget_remaining']
    free_transfers = team_data['free_transfers']
    date_str = datetime.now().strftime("%A, %d %B %Y")

    # Format squad list for email
    squad_rows = ""
    for p in team_data['players']:
        captain = " 👑" if p['is_captain'] else ""
        vc = " ©" if p['is_vice_captain'] else ""
        bench = "bench" if p['multiplier'] == 0 else "starting"
        status_colour = "#e74c3c" if p['status'] != 'a' else "#27ae60"
        status_dot = f"<span style='color:{status_colour}'>●</span>"

        squad_rows += f"""
        <tr style="border-bottom: 1px solid #f0f0f0;">
            <td style="padding: 8px 12px; font-weight: 500;">{p['name']}{captain}{vc}</td>
            <td style="padding: 8px 12px; color: #666;">{p['team']}</td>
            <td style="padding: 8px 12px; color: #666;">{p['position']}</td>
            <td style="padding: 8px 12px;">£{p['price']}m</td>
            <td style="padding: 8px 12px; color: #f39c12;">{p['form']}</td>
            <td style="padding: 8px 12px;">{p['total_points']}pts</td>
            <td style="padding: 8px 12px;">{status_dot} {bench}</td>
        </tr>
        """

    # Convert recommendation text to HTML paragraphs
    rec_html = ""
    for line in recommendation_text.split('\n'):
        line = line.strip()
        if not line:
            rec_html += "<br>"
        elif line.startswith('━'):
            rec_html += f"<hr style='border: 1px solid #e0e0e0; margin: 16px 0;'>"
        elif any(line.startswith(x) for x in ['1️⃣', '2️⃣', '3️⃣']):
            rec_html += f"<h3 style='color: #2c3e50; margin: 24px 0 8px 0;'>{line}</h3>"
        elif line.startswith('👑') or line.startswith('⚠️') or line.startswith('📊'):
            rec_html += f"<p style='background: #f8f9fa; padding: 12px 16px; border-radius: 6px; margin: 8px 0;'><strong>{line}</strong></p>"
        elif line.startswith('OUT:') or line.startswith('IN:') or line.startswith('Cost:'):
            rec_html += f"<p style='margin: 4px 0; padding-left: 16px; color: #555;'>{line}</p>"
        elif line.startswith('Reason:'):
            rec_html += f"<p style='margin: 8px 0; padding-left: 16px; font-style: italic; color: #444;'>{line}</p>"
        elif line.startswith('Confidence:'):
            colour = "#27ae60" if "High" in line else "#f39c12" if "Medium" in line else "#e74c3c"
            rec_html += f"<p style='margin: 4px 0; padding-left: 16px;'><span style='color:{colour}; font-weight: bold;'>{line}</span></p>"
        else:
            rec_html += f"<p style='margin: 6px 0; color: #333;'>{line}</p>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5f5f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        
        <div style="max-width: 680px; margin: 0 auto; padding: 24px 16px;">
            
            <!-- HEADER -->
            <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); 
                        border-radius: 16px 16px 0 0; padding: 32px; text-align: center;">
                <div style="font-size: 40px; margin-bottom: 8px;">⚽</div>
                <h1 style="color: white; margin: 0; font-size: 24px; font-weight: 700;">
                    FPL AI Advisor
                </h1>
                <p style="color: #a0aec0; margin: 8px 0 0 0; font-size: 14px;">
                    Gameweek {gw} Transfer Recommendations
                </p>
                <p style="color: #718096; margin: 4px 0 0 0; font-size: 12px;">{date_str}</p>
            </div>

            <!-- SQUAD SUMMARY -->
            <div style="background: white; padding: 24px; border-left: 1px solid #e0e0e0; border-right: 1px solid #e0e0e0;">
                <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 16px;">
                    📋 Your Current Squad
                </h2>
                <div style="display: flex; gap: 24px; margin-bottom: 16px;">
                    <div style="background: #f8f9fa; padding: 12px 20px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 20px; font-weight: 700; color: #2c3e50;">GW{gw}</div>
                        <div style="font-size: 11px; color: #888; margin-top: 2px;">Gameweek</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 12px 20px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 20px; font-weight: 700; color: #27ae60;">£{budget}m</div>
                        <div style="font-size: 11px; color: #888; margin-top: 2px;">In Bank</div>
                    </div>
                    <div style="background: #f8f9fa; padding: 12px 20px; border-radius: 8px; text-align: center;">
                        <div style="font-size: 20px; font-weight: 700; color: #3498db;">{free_transfers}</div>
                        <div style="font-size: 11px; color: #888; margin-top: 2px;">Free Transfers</div>
                    </div>
                </div>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                    <thead>
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Player</th>
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Team</th>
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Pos</th>
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Price</th>
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Form</th>
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Pts</th>
                            <th style="padding: 8px 12px; text-align: left; color: #666; font-weight: 600;">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {squad_rows}
                    </tbody>
                </table>
            </div>

            <!-- RECOMMENDATIONS -->
            <div style="background: white; padding: 24px; 
                        border: 1px solid #e0e0e0; border-top: 3px solid #3498db;">
                <h2 style="color: #2c3e50; margin: 0 0 20px 0; font-size: 16px;">
                    🤖 Agent Recommendations
                </h2>
                <div style="font-size: 14px; line-height: 1.7; color: #333;">
                    {rec_html}
                </div>
            </div>

            <!-- FOOTER -->
            <div style="background: #2c3e50; border-radius: 0 0 16px 16px; 
                        padding: 20px; text-align: center;">
                <p style="color: #a0aec0; margin: 0; font-size: 12px;">
                    Generated by FPL AI Advisor — Agentic AI Project
                </p>
                <p style="color: #718096; margin: 4px 0 0 0; font-size: 11px;">
                    Powered by Claude (Anthropic) + FPL API
                </p>
            </div>

        </div>
    </body>
    </html>
    """
    return html


def format_email_subject(team_data: dict) -> str:
    gw = team_data['current_gameweek']
    return f"⚽ FPL AI Advisor — GW{gw} Transfer Recommendations"
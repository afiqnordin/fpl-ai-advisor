# chart_generator.py
# Generates matplotlib charts as base64 PNG strings
# for embedding directly in HTML emails.
# No files saved to disk — everything stays in memory.

import io
import base64
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend — required for server/automation
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap


# ── COLOUR PALETTE ─────────────────────────────────────
COLOURS = {
    "green":      "#27ae60",
    "amber":      "#f39c12",
    "red":        "#e74c3c",
    "blue":       "#2980b9",
    "dark":       "#2c3e50",
    "light_grey": "#f8f9fa",
    "mid_grey":   "#dee2e6",
    "blank":      "#95a5a6",
    "text":       "#2c3e50",
}

DIFFICULTY_COLOURS = {
    0: "#95a5a6",   # blank — grey
    1: "#00c853",   # very easy — bright green
    2: "#69c779",   # easy — green
    3: "#f39c12",   # medium — amber
    4: "#e67e22",   # hard — orange
    5: "#e74c3c",   # very hard — red
}


def _fig_to_base64(fig) -> str:
    """Convert a matplotlib figure to base64 string for HTML embedding."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def generate_fixture_heatmap(squad_players: list,
                              fixtures_by_team: dict,
                              current_gw: int) -> str:
    """
    Generates a fixture difficulty heatmap for the starting XI.

    Rows    = your 11 starting players
    Columns = next 6 gameweeks
    Colours = green (easy) → red (hard), grey = blank

    Returns base64 PNG string.
    """
    # Only show starting XI (multiplier > 0)
    starters = [p for p in squad_players if p['multiplier'] > 0]

    # Order by position: GK, DEF, MID, FWD
    position_order = {"GK": 0, "DEF": 1, "MID": 2, "FWD": 3}
    starters.sort(key=lambda x: position_order.get(x['position'], 4))

    gws = [current_gw + i for i in range(0, 3)]
    player_names = [f"{p['name']} ({p['position']})" for p in starters]

    # Build difficulty matrix
    matrix = []
    annotations = []

    for player in starters:
        team = player['team']
        team_fixtures = fixtures_by_team.get(team, [])
        fixtures_by_gw = {f['gameweek']: f for f in team_fixtures}

        row = []
        ann_row = []
        for gw in gws:
            if gw in fixtures_by_gw:
                diff = fixtures_by_gw[gw]['difficulty']
                venue = "H" if fixtures_by_gw[gw]['venue'] == "Home" else "A"
                opp = fixtures_by_gw[gw]['opponent'][:3].upper()
                row.append(diff)
                ann_row.append(f"{opp}\n{venue}")
            else:
                row.append(0)  # blank
                ann_row.append("BL")
        matrix.append(row)
        annotations.append(ann_row)

    # Create figure
    n_players = len(starters)
    n_gws = len(gws)
    fig, ax = plt.subplots(figsize=(n_gws * 1.4, n_players * 0.65))
    fig.patch.set_facecolor('white')

    # Draw cells manually for full colour control
    for row_idx, (row, ann_row) in enumerate(zip(matrix, annotations)):
        for col_idx, (diff, ann) in enumerate(zip(row, ann_row)):
            colour = DIFFICULTY_COLOURS.get(diff, DIFFICULTY_COLOURS[3])
            rect = mpatches.FancyBboxPatch(
                (col_idx + 0.05, row_idx + 0.05),
                0.9, 0.9,
                boxstyle="round,pad=0.05",
                facecolor=colour,
                edgecolor='white',
                linewidth=2
            )
            ax.add_patch(rect)

            # Text colour — white on dark backgrounds
            text_colour = 'white' if diff in [4, 5] or diff == 0 else '#1a1a1a'
            ax.text(
                col_idx + 0.5, row_idx + 0.5, ann,
                ha='center', va='center',
                fontsize=7.5, fontweight='bold',
                color=text_colour, linespacing=1.3
            )

    # Axes formatting
    ax.set_xlim(0, n_gws)
    ax.set_ylim(0, n_players)
    ax.set_xticks([i + 0.5 for i in range(n_gws)])
    ax.set_xticklabels([f"GW{gw}" for gw in gws],
                       fontsize=9, fontweight='bold', color=COLOURS['dark'])
    ax.set_yticks([i + 0.5 for i in range(n_players)])
    ax.set_yticklabels(player_names, fontsize=9, color=COLOURS['dark'])
    ax.xaxis.set_ticks_position('top')
    ax.xaxis.set_label_position('top')
    ax.tick_params(length=0)

    for spine in ax.spines.values():
        spine.set_visible(False)

    # Legend
    legend_items = [
        mpatches.Patch(color=DIFFICULTY_COLOURS[1], label='Easy (1)'),
        mpatches.Patch(color=DIFFICULTY_COLOURS[2], label='Moderate (2)'),
        mpatches.Patch(color=DIFFICULTY_COLOURS[3], label='Medium (3)'),
        mpatches.Patch(color=DIFFICULTY_COLOURS[4], label='Hard (4)'),
        mpatches.Patch(color=DIFFICULTY_COLOURS[5], label='Very Hard (5)'),
        mpatches.Patch(color=DIFFICULTY_COLOURS[0], label='Blank'),
    ]
    ax.legend(
        handles=legend_items,
        loc='lower center',
        bbox_to_anchor=(0.5, -0.12),
        ncol=6, fontsize=7.5,
        frameon=False
    )

    ax.set_title('Fixture Difficulty — Next 6 Gameweeks',
                 fontsize=11, fontweight='bold',
                 color=COLOURS['dark'], pad=15)

    plt.tight_layout()
    img_bytes = fig_to_bytes(fig)
    plt.close(fig)
    return img_bytes


def generate_player_comparison_chart(player_out: dict,
                                      player_in: dict) -> str:
    """
    Generates a side-by-side bar chart comparing two players
    across 5 key Moneyball metrics.

    player_out / player_in must have:
        name, metrics (dict with xg_per90, xa_per90,
        points_per_game, fixture_score, moneyball_score)

    Returns base64 PNG string.
    """
    metrics_config = [
        ("xG per 90",        "xg_per90",        1.0),
        ("xA per 90",        "xa_per90",         0.5),
        ("Points per Game",  "points_per_game",  12.0),
        ("Fixture Ease",     "fixture_score",    1.0),
        ("Moneyball Score",  "moneyball_score",  100.0),
    ]

    labels = [m[0] for m in metrics_config]
    keys   = [m[1] for m in metrics_config]
    maxes  = [m[2] for m in metrics_config]

    def get_val(player, key):
        if key == "moneyball_score":
            return float(player.get("moneyball_score", 0))
        return float(player.get("metrics", {}).get(key, 0))

    out_vals  = [get_val(player_out, k) for k in keys]
    in_vals   = [get_val(player_in,  k) for k in keys]

    # Normalise to 0-1 for fair bar length
    out_norm = [v / m if m > 0 else 0 for v, m in zip(out_vals, maxes)]
    in_norm  = [v / m if m > 0 else 0 for v, m in zip(in_vals,  maxes)]

    n = len(labels)
    y = np.arange(n)
    bar_h = 0.35

    fig, ax = plt.subplots(figsize=(8, 3.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    bars_out = ax.barh(y + bar_h/2, out_norm, bar_h,
                       color=COLOURS['red'], alpha=0.85,
                       label=player_out['name'])
    bars_in  = ax.barh(y - bar_h/2, in_norm,  bar_h,
                       color=COLOURS['green'], alpha=0.85,
                       label=player_in['name'])

    # Value labels on bars
    for bar, val in zip(bars_out, out_vals):
        w = bar.get_width()
        ax.text(w + 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}' if val < 10 else f'{val:.0f}',
                va='center', fontsize=8, color=COLOURS['dark'])

    for bar, val in zip(bars_in, in_vals):
        w = bar.get_width()
        ax.text(w + 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}' if val < 10 else f'{val:.0f}',
                va='center', fontsize=8, color=COLOURS['dark'])

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9, color=COLOURS['dark'])
    ax.set_xlim(0, 1.25)
    ax.set_xticks([])
    ax.legend(fontsize=9, loc='lower right', frameon=False)
    ax.set_title(
        f'{player_out["name"]} (OUT)  vs  {player_in["name"]} (IN)',
        fontsize=10, fontweight='bold', color=COLOURS['dark'], pad=10
    )

    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.axvline(0, color=COLOURS['mid_grey'], linewidth=0.5)
    plt.tight_layout()
    img_bytes = fig_to_bytes(fig)
    plt.close(fig)
    return img_bytes


def generate_score_badge(score: float, player_name: str) -> str:
    """
    Generates a circular score gauge for a player.
    Like a speedometer — green zone 70+, amber 50-70, red below 50.

    Returns base64 PNG string.
    """
    fig, ax = plt.subplots(figsize=(2.5, 2.5),
                           subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('white')

    # Background arc
    theta = np.linspace(0, np.pi, 100)
    ax.plot(theta, [1] * 100, color=COLOURS['mid_grey'],
            linewidth=12, solid_capstyle='round')

    # Score arc
    score_pct = min(score / 100, 1.0)
    score_theta = np.linspace(0, np.pi * score_pct, 100)
    if score >= 70:
        score_colour = COLOURS['green']
    elif score >= 50:
        score_colour = COLOURS['amber']
    else:
        score_colour = COLOURS['red']

    ax.plot(score_theta, [1] * 100, color=score_colour,
            linewidth=12, solid_capstyle='round')

    # Score text
    ax.text(0, 0.05, f'{score:.0f}', ha='center', va='center',
            fontsize=22, fontweight='bold', color=COLOURS['dark'],
            transform=ax.transData)
    ax.text(0, -0.35, '/100', ha='center', va='center',
            fontsize=10, color='#888',
            transform=ax.transData)
    ax.text(0, -0.65, player_name, ha='center', va='center',
            fontsize=8, color=COLOURS['dark'],
            fontweight='bold', transform=ax.transData)

    ax.set_ylim(0, 1.3)
    ax.set_theta_zero_location('W')
    ax.set_theta_direction(1)
    ax.set_thetamin(0)
    ax.set_thetamax(180)
    ax.set_rticks([])
    ax.set_xticks([])
    ax.spines['polar'].set_visible(False)
    ax.set_facecolor('white')

    plt.tight_layout()
    img_bytes = fig_to_bytes(fig)
    plt.close(fig)
    return img_bytes


def fig_to_bytes(fig) -> bytes:
    """Returns raw PNG bytes for CID email attachment."""
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return buf.read()


"""Draws the dashboard wireframe (WBS 4.1.1) as a PNG. Uses no data."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.patches import FancyBboxPatch       # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "deliverables" / "iteration2" / "4.1.1_dashboard_layout.png"

FILL = {"nav": "#EEF1F4", "visitors": "#E3EEF7", "trips": "#F7E8F1", "info": "#F4F4F2"}
EDGE = "#6b6b6b"

# x, y (top), width, height, title, subtitle, kind
BLOCKS = [
    (0.0, 0.0, 2.2, 15.6, "Sidebar: filters", "Year\n\nMonth range\n\nVisitor origin\n(Residente: trips\nview only)\n\nVisitor type", "nav"),
    (2.4, 0.0, 9.6, 1.1, "Header + \"How to read this\"", "Title · current selection · the limits", "nav"),
    (2.4, 1.3, 9.6, 2.5, "Q3 · KPI tiles + stacked bars", "Visitors (monthly average) · share by origin · tourist share", "visitors"),
    (2.4, 4.0, 9.6, 1.9, "Q2 · Monthly evolution by origin", "Line chart, one colour per origin", "visitors"),
    (2.4, 6.1, 4.7, 2.0, "Q5 · Year comparison", "Equivalent months only", "visitors"),
    (7.3, 6.1, 4.7, 2.0, "Q5 · Change per neighbourhood", "Map, diverging scale", "visitors"),
    (2.4, 8.3, 9.6, 1.5, "Q4 · Weekday chart", "Mean per day, by origin", "visitors"),
    (2.4, 10.0, 5.8, 2.3, "Q1 · Neighbourhood map", "Unique visitors, mean per month", "visitors"),
    (8.4, 10.0, 3.6, 2.3, "Q1 · Top-10 table", "Share of ranking · Gini", "visitors"),
    (2.4, 12.5, 5.8, 2.1, "Q6 · Visitor share of trips (map)", "\"Trips, not people\"", "trips"),
    (8.4, 12.5, 3.6, 2.1, "Q6 · Top-10 table", "Share of trips", "trips"),
    (2.4, 14.8, 9.6, 0.8, "Data & limits (expander) · Footer", "The 6 rules · NDA note · threshold 15", "info"),
]


def main():
    fig, ax = plt.subplots(figsize=(10, 12.5))
    for x, y, w, h, title, subtitle, kind in BLOCKS:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", facecolor=FILL[kind], edgecolor=EDGE, linewidth=1))
        ax.text(x + 0.14, y + 0.14, title, fontsize=10.5, fontweight="bold", va="top", color="#1f1f1f")
        ax.text(x + 0.14, y + 0.52, subtitle, fontsize=9, va="top", color="#4a4a4a")
    ax.set_xlim(-0.1, 12.1)
    ax.set_ylim(15.75, -0.75)
    ax.text(0, -0.25, "CONVIVE preliminary dashboard: layout (blue = unique visitors, pink = trips; never combined)",
            fontsize=11.5, fontweight="bold", color="#1f1f1f")
    ax.set_axis_off()
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, facecolor="white")
    print(OUT)


if __name__ == "__main__":
    main()

"""
Draw the README figures as SVG (light and dark versions).

The numbers below are aggregate results from cypher/06_figures.cypher
on the 25-participant Study 2 pilot. No participant-level data is used.
Counts below 5 are suppressed (None) before they reach this file.

Usage:
    python figures/make_figures.py
"""

from pathlib import Path


OUT = Path(__file__).parent

# Mean score per wave (Chart 1), n = 25 at every wave.
MEANS = {
    "DASS Depression": [3.7, 3.0, 1.7],
    "DASS Anxiety": [4.0, 3.4, 1.7],
    "DASS Stress": [3.4, 2.8, 1.4],
    "PCL-5": [7.2, 5.7, 2.8],
}

# Participants whose score decreased (Chart 2). None = fewer than 5.
DECREASED = {
    "DASS Depression": [6, 5],
    "DASS Anxiety": [None, 7],
    "DASS Stress": [None, 5],
    "PCL-5": [5, 8],
}

THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "primary": "#0b0b0b",
        "secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "baseline": "#c3c2b7",
        "series": ["#2a78d6", "#eb6834"],
    },
    "dark": {
        "surface": "#1a1a19",
        "primary": "#f0efec",
        "secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "baseline": "#383835",
        "series": ["#3987e5", "#d95926"],
    },
}

FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def text(x, y, value, fill, size=12, anchor="start", weight=400):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{value}</text>'
    )


def hline(x1, x2, y, stroke):
    return (
        f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{y:.1f}" y2="{y:.1f}" '
        f'stroke="{stroke}" stroke-width="1"/>'
    )


def svg(width, height, theme, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{label}" font-family="{FONT}">'
        f'<rect width="{width}" height="{height}" rx="8" '
        f'fill="{theme["surface"]}"/>' + "".join(body) + "</svg>\n"
    )


def fmt(value):
    return f"{value:.1f}"


# ============================================================
# CHART 1: mean score per wave, small multiples
# ============================================================

def mean_scores_chart(t):
    width, height = 880, 560
    body = [
        text(24, 36, "Mean score by wave, Study 2 pilot (n = 25)",
             t["primary"], 16, weight=600),
        text(24, 58, "Higher scores mean more symptoms. PCL-5 has its own "
             "scale.", t["secondary"], 13),
    ]

    panel_w, panel_h = 416, 220
    for index, (measure, values) in enumerate(MEANS.items()):
        col, row = index % 2, index // 2
        px = 24 + col * (panel_w + 0)
        py = 84 + row * (panel_h + 16)

        top = 8 if measure == "PCL-5" else 5
        step = 2 if measure == "PCL-5" else 1

        left, right = px + 36, px + panel_w - 40
        plot_top, plot_bottom = py + 44, py + panel_h - 32

        def y_of(value):
            return plot_bottom - (value / top) * (plot_bottom - plot_top)

        xs = [left + 30 + i * ((right - left - 60) / 2) for i in range(3)]

        body.append(text(px, py + 18, measure, t["primary"], 14, weight=600))

        for tick in range(0, top + 1, step):
            y = y_of(tick)
            body.append(hline(left, right, y,
                              t["baseline"] if tick == 0 else t["grid"]))
            body.append(text(left - 8, y + 4, tick, t["muted"], 11, "end"))

        for i, x in enumerate(xs):
            body.append(text(x, plot_bottom + 20, f"Wave {i + 1}",
                             t["secondary"], 12, "middle"))

        points = " ".join(f"{x:.1f},{y_of(v):.1f}" for x, v in zip(xs, values))
        body.append(
            f'<polyline points="{points}" fill="none" '
            f'stroke="{t["series"][0]}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

        for i, (x, value) in enumerate(zip(xs, values)):
            y = y_of(value)
            body.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" '
                f'fill="{t["series"][0]}" stroke="{t["surface"]}" '
                f'stroke-width="2"><title>{measure}, wave {i + 1}: '
                f'mean {fmt(value)}</title></circle>'
            )
            if i in (0, 2):
                body.append(text(x, y - 12, fmt(value), t["primary"], 12,
                                 "middle", 600))

    return svg(width, height, t, body,
               "Mean DASS depression, anxiety, stress and PCL-5 scores fell "
               "from wave 1 to wave 3 in the 25-participant pilot")


# ============================================================
# CHART 2: participants whose score decreased, grouped columns
# ============================================================

def bar_path(x, top, width, base, r=4):
    return (
        f"M{x:.1f},{base:.1f} L{x:.1f},{top + r:.1f} "
        f"Q{x:.1f},{top:.1f} {x + r:.1f},{top:.1f} "
        f"L{x + width - r:.1f},{top:.1f} "
        f"Q{x + width:.1f},{top:.1f} {x + width:.1f},{top + r:.1f} "
        f"L{x + width:.1f},{base:.1f} Z"
    )


def decreased_chart(t):
    width, height = 880, 420
    transitions = ["Wave 1 to 2", "Wave 2 to 3"]
    body = [
        text(24, 36, "Participants whose score decreased between waves "
             "(of 25)", t["primary"], 16, weight=600),
        text(24, 58, "Study 2 pilot. Counts below 5 are suppressed and "
             "shown as “&lt;5”.", t["secondary"], 13),
    ]

    legend_x = 24
    for i, label in enumerate(transitions):
        body.append(
            f'<rect x="{legend_x}" y="76" width="12" height="12" rx="2" '
            f'fill="{t["series"][i]}"/>'
        )
        body.append(text(legend_x + 18, 86, label, t["secondary"], 12))
        legend_x += 110

    left, right = 64, 856
    plot_top, base = 116, 360
    top = 10

    def y_of(value):
        return base - (value / top) * (base - plot_top)

    for tick in range(0, top + 1, 2):
        y = y_of(tick)
        body.append(hline(left, right, y,
                          t["baseline"] if tick == 0 else t["grid"]))
        body.append(text(left - 8, y + 4, tick, t["muted"], 11, "end"))

    band = (right - left) / len(DECREASED)
    bar_w, gap = 24, 2

    for g, (measure, values) in enumerate(DECREASED.items()):
        centre = left + band * (g + 0.5)
        body.append(text(centre, base + 22, measure, t["secondary"], 12,
                         "middle"))

        for i, value in enumerate(values):
            x = centre - bar_w - gap / 2 + i * (bar_w + gap)
            mid = x + bar_w / 2

            if value is None:
                body.append(text(mid, base - 6, "&lt;5", t["muted"], 11,
                                 "middle"))
                continue

            y = y_of(value)
            body.append(
                f'<path d="{bar_path(x, y, bar_w, base)}" '
                f'fill="{t["series"][i]}"><title>{measure}, '
                f'{transitions[i].lower()}: {value} decreased</title></path>'
            )
            body.append(text(mid, y - 6, value, t["primary"], 12, "middle",
                             600))

    return svg(width, height, t, body,
               "Number of pilot participants whose DASS and PCL-5 scores "
               "decreased between consecutive waves")


def main():
    for mode, theme in THEMES.items():
        (OUT / f"mean_scores_by_wave_{mode}.svg").write_text(
            mean_scores_chart(theme), encoding="utf-8")
        (OUT / f"scores_decreased_{mode}.svg").write_text(
            decreased_chart(theme), encoding="utf-8")

    print("Figures written to", OUT)


if __name__ == "__main__":
    main()

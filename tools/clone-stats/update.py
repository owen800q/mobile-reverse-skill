#!/usr/bin/env python3
"""Keep a running clone history for this repo and render it as an SVG chart.

GitHub's traffic API only returns the last 14 days of clones, so each run merges
that window into history.json (newest value wins for a day, since today's count
is still growing) and redraws clones.svg from the full history.

Usage:
  GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo python3 update.py
  python3 update.py --render-only     # redraw from history.json, no API call

Stdlib only, so the workflow needs no pip install.
"""

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
HISTORY = HERE / "history.json"
CHART = HERE / "clones.svg"
WINDOW_DAYS = 90  # how many days the chart shows; totals still cover all history


def fetch(repo: str, token: str) -> list:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/traffic/clones?per=day",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)["clones"]


def load() -> dict:
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return {}


def merge(history: dict, clones: list) -> dict:
    for c in clones:
        day = c["timestamp"][:10]
        history[day] = {"count": c["count"], "uniques": c["uniques"]}
    return dict(sorted(history.items()))


def series(history: dict) -> list:
    """Every day from the first to the latest recorded one, zero-filled.

    Stops at GitHub's latest reported day rather than today: traffic data lags,
    so padding to today would draw a misleading flat tail.
    """
    if not history:
        return []
    start = dt.date.fromisoformat(next(iter(history)))
    end = dt.date.fromisoformat(max(history))
    out, d = [], start
    while d <= end:
        rec = history.get(d.isoformat(), {"count": 0, "uniques": 0})
        out.append((d, rec["count"], rec["uniques"]))
        d += dt.timedelta(days=1)
    return out


def render(history: dict) -> str:
    days = series(history)
    # running total: each point is every clone recorded up to that day
    running, acc = [], 0
    for d, c, _ in days:
        acc += c
        running.append((d, acc, c))
    total = acc
    shown = running[-WINDOW_DAYS:]
    latest = shown[-1] if shown else None
    last_week = sum(c for _, _, c in running[-7:])

    W, H = 820, 280
    left, right, top, bottom = 56, 28, 64, 36
    pw, ph = W - left - right, H - top - bottom
    peak = max([t for _, t, _ in shown] + [1])
    # round the y-axis up to a tidy number
    step = max(1, 10 ** (len(str(peak)) - 1))
    ymax = ((peak + step - 1) // step) * step
    n = len(shown)

    def x(i):
        return left + (i / (n - 1) * pw if n > 1 else pw / 2)

    def y(v):
        return top + ph - v / ymax * ph

    parts = []
    for i in range(5):
        v = ymax * i / 4
        yy = y(v)
        parts.append(f'<line class="grid" x1="{left}" x2="{W - right}" y1="{yy:.1f}" y2="{yy:.1f}"/>')
        parts.append(f'<text class="axis" x="{left - 8}" y="{yy + 4:.1f}" text-anchor="end">{v:,.0f}</text>')

    if shown:
        pts = [f"{x(i):.1f},{y(t):.1f}" for i, (_, t, _) in enumerate(shown)]
        base = f"{x(n - 1):.1f},{y(0):.1f} {x(0):.1f},{y(0):.1f}"
        parts.append(f'<polygon class="area" points="{" ".join(pts)} {base}"/>')
        parts.append(f'<polyline class="line" points="{" ".join(pts)}"/>')
        for i, (d, t, c) in enumerate(shown):
            parts.append(
                f'<circle class="dot" cx="{x(i):.1f}" cy="{y(t):.1f}" r="{3 if i == n - 1 else 2}">'
                f"<title>{d.isoformat()}: {t:,} total (+{c:,})</title></circle>"
            )
        parts.append(
            f'<text class="end" x="{x(n - 1) - 6:.1f}" y="{y(shown[-1][1]) - 8:.1f}" text-anchor="end">{total:,}</text>'
        )

    # x labels: first, last, and a few in between
    if shown:
        idxs = sorted({0, n - 1, *range(0, n, max(1, n // 5))})
        for i in idxs:
            if i != n - 1 and n - 1 - i < max(1, n // 10):
                continue  # skip a label that would collide with the last one
            parts.append(
                f'<text class="axis" x="{x(i):.1f}" y="{H - bottom + 18}" text-anchor="middle">'
                f'{shown[i][0].strftime("%b %d")}</text>'
            )

    latest_txt = f"+{latest[2]:,} on {latest[0].strftime('%b %d')}" if latest else "no data yet"
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    body = "\n  ".join(parts) if shown else (
        f'<text class="axis" x="{W / 2}" y="{H / 2}" text-anchor="middle">No clone data yet</text>'
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Total repository clones over time">
  <style>
    svg {{ --fg:#1f2328; --muted:#656d76; --grid:#d8dee4; --bar:#2f81f7; --bg:#ffffff; }}
    @media (prefers-color-scheme: dark) {{
      svg {{ --fg:#e6edf3; --muted:#8d96a0; --grid:#30363d; --bar:#4493f8; --bg:#0d1117; }}
    }}
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; fill: var(--fg); }}
    .bg {{ fill: var(--bg); }}
    .title {{ font-size: 16px; font-weight: 600; }}
    .sub, .axis {{ font-size: 11px; fill: var(--muted); }}
    .grid {{ stroke: var(--grid); stroke-width: 1; }}
    .area {{ fill: var(--bar); fill-opacity: 0.15; }}
    .line {{ fill: none; stroke: var(--bar); stroke-width: 2; stroke-linejoin: round; }}
    .dot {{ fill: var(--bar); }}
    .end {{ font-size: 12px; font-weight: 600; fill: var(--bar); }}
  </style>
  <rect class="bg" width="{W}" height="{H}" rx="6"/>
  <text class="title" x="{left}" y="26">{total:,} total clones</text>
  <text class="sub" x="{left}" y="44">{latest_txt} · +{last_week:,} in the last 7 days · updated {updated}</text>
  {body}
</svg>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--render-only", action="store_true")
    args = ap.parse_args()

    history = load()
    if not args.render_only:
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPOSITORY")
        if not token or not repo:
            print("GITHUB_TOKEN and GITHUB_REPOSITORY are required", file=sys.stderr)
            return 2
        history = merge(history, fetch(repo, token))
        HISTORY.write_text(json.dumps(history, indent=2) + "\n")

    CHART.write_text(render(history))
    print(f"{len(history)} day(s) recorded, chart -> {CHART.relative_to(HERE.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

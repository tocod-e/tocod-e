"""Render the last 31 days of GitHub contributions as an SVG area chart.

Replaces the hosted github-readme-activity-graph service, which is often
unavailable. Runs in GitHub Actions with GITHUB_TOKEN; stdlib only.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "tocod-e")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT", "assets/activity-graph.svg")
DAYS = 31

W, H = 1200, 420
PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 70, 60
BG, LINE, POINT, TEXT, GRID = "#0d1117", "#1a8cff", "#ffffff", "#c9d1d9", "#21262d"


def fetch_counts():
    end = dt.datetime.now(dt.timezone.utc).replace(hour=23, minute=59, second=59, microsecond=0)
    start = (end - dt.timedelta(days=DAYS - 1)).replace(hour=0, minute=0, second=0)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { weeks { contributionDays { date contributionCount } } }
        }
      }
    }"""
    body = json.dumps({"query": query, "variables": {
        "login": USER, "from": start.isoformat(), "to": end.isoformat()}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    return [(d["date"], d["contributionCount"]) for d in days][-DAYS:]


def render(points):
    pw, ph = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    peak = max([c for _, c in points] + [4])
    top = peak + (-peak % 4)  # round up to a multiple of 4 for even gridlines
    step = pw / max(len(points) - 1, 1)
    xy = [(PAD_L + i * step, PAD_T + ph - c / top * ph) for i, (_, c) in enumerate(points)]

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="Segoe UI, Ubuntu, sans-serif">',
           '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
           f'<stop offset="0" stop-color="{LINE}" stop-opacity="0.45"/>'
           f'<stop offset="1" stop-color="{LINE}" stop-opacity="0.02"/></linearGradient></defs>',
           f'<rect width="{W}" height="{H}" rx="8" fill="{BG}"/>',
           f'<text x="{W / 2}" y="40" fill="{LINE}" font-size="22" font-weight="600" '
           f'text-anchor="middle">{USER}\'s Contribution Graph</text>']
    for i in range(5):
        v = top * i // 4
        y = PAD_T + ph - v / top * ph
        out.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" stroke="{GRID}"/>')
        out.append(f'<text x="{PAD_L - 12}" y="{y + 4:.1f}" fill="{TEXT}" font-size="12" text-anchor="end">{v}</text>')
    for i, (date, _) in enumerate(points):
        if i % 2 == 0:
            out.append(f'<text x="{xy[i][0]:.1f}" y="{H - PAD_B + 22}" fill="{TEXT}" font-size="12" '
                       f'text-anchor="middle">{int(date[8:])}</text>')
    out.append(f'<text x="{W / 2}" y="{H - 12}" fill="{TEXT}" font-size="13" text-anchor="middle">Days</text>')
    out.append(f'<text x="18" y="{PAD_T + ph / 2}" fill="{TEXT}" font-size="13" text-anchor="middle" '
               f'transform="rotate(-90 18 {PAD_T + ph / 2})">Contributions</text>')

    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in xy)
    base = PAD_T + ph
    out.append(f'<polygon points="{xy[0][0]:.1f},{base} {line} {xy[-1][0]:.1f},{base}" fill="url(#g)"/>')
    out.append(f'<polyline points="{line}" fill="none" stroke="{LINE}" stroke-width="3" stroke-linejoin="round"/>')
    for (x, y), (date, c) in zip(xy, points):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{POINT}"><title>{date}: {c}</title></circle>')
    out.append("</svg>")
    return "\n".join(out)


if __name__ == "__main__":
    if TOKEN:
        pts = fetch_counts()
    else:  # placeholder until the workflow runs
        today = dt.date.today()
        pts = [((today - dt.timedelta(days=DAYS - 1 - i)).isoformat(), 0) for i in range(DAYS)]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(render(pts))
    print(f"wrote {OUT} ({sum(c for _, c in pts)} contributions)")

#!/usr/bin/env python3
"""Builds stats.svg for the profile README. Run daily by .github/workflows/stats.yml."""
import datetime as dt, json, os, sys, urllib.request

USER = os.environ.get("GH_USER", "Mkhurana3")
OUT = os.environ.get("STATS_OUT", "stats.svg")
TEAL = ["#161b22", "#0f3d3a", "#14706a", "#22b8a8", "#5eead4"]
PINK, BLUE, MUTED, TEXT = "#f472b6", "#58a6ff", "#8b949e", "#e6edf3"


def fetch_days():
    q = """query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{
      weeks{contributionDays{date contributionCount}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"u": USER}}).encode(),
        headers={"Authorization": "bearer " + os.environ["GITHUB_TOKEN"], "Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def fetch_days_html():
    """Fallback: read the public contribution calendar page."""
    import re
    html = urllib.request.urlopen(f"https://github.com/users/{USER}/contributions", timeout=30).read().decode()
    tips = {m[0]: m[1] for m in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)</tool-tip>', html)}
    days = []
    for tag in re.findall(r"<td\b[^>]*data-date=[^>]*>", html):
        date = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag).group(1)
        cid = (re.search(r'\bid="([^"]+)"', tag) or [None, ""])[1]
        m = re.match(r"\s*(\d+) contribution", tips.get(cid, ""))
        days.append((date, int(m.group(1)) if m else 0))
    if not days:
        raise RuntimeError("no calendar data")
    return sorted(days)


def streaks(days):
    cur = best = run = 0
    best_rng = cur_start = None
    start = None
    for date, n in days:
        if n:
            run += 1
            start = start or date
            if run >= best:
                best, best_rng = run, (start, date)
        else:
            run, start = 0, None
    # current streak: count back from today (today may still be 0)
    seq = days[:-1] if days and days[-1][1] == 0 else days
    for date, n in reversed(seq):
        if not n:
            break
        cur += 1
        cur_start = date
    return cur, cur_start, best, best_rng


def fmt(d):
    return dt.date.fromisoformat(d).strftime("%b %-d") if d else "—"


def build(days):
    total = sum(n for _, n in days)
    active = sum(1 for _, n in days if n)
    cur, cur_start, best, best_rng = streaks(days)
    peak = max(days, key=lambda d: d[1]) if days else ("", 0)
    W, H = 1200, 640
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         'font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
         '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#070b16"/>'
         '<stop offset="1" stop-color="#0e1630"/></linearGradient>'
         '<linearGradient id="area" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f472b6" stop-opacity=".45"/>'
         '<stop offset="1" stop-color="#f472b6" stop-opacity="0"/></linearGradient>'
         '<filter id="glow"><feGaussianBlur stdDeviation="2.5" result="b"/><feMerge><feMergeNode in="b"/>'
         '<feMergeNode in="SourceGraphic"/></feMerge></filter></defs>',
         f'<rect width="{W}" height="{H}" rx="16" fill="url(#bg)" stroke="#30363d"/>']
    mono = 'font-family="Menlo,Consolas,monospace"'
    s.append(f'<text x="36" y="46" {mono} font-size="13" letter-spacing="2" fill="{MUTED}">GITHUB ACTIVITY · LAST 12 MONTHS</text>')
    s.append(f'<text x="{W-36}" y="46" text-anchor="end" {mono} font-size="12" fill="{MUTED}">@{USER} · updated {dt.date.today():%d %b %Y}</text>')

    # KPI tiles
    tiles = [(total, "contributions", "last 12 months", TEAL[4]),
             (cur, "day streak", f"since {fmt(cur_start)}" if cur else "start one today", PINK),
             (best, "longest streak", f"{fmt(best_rng[0])} – {fmt(best_rng[1])}" if best_rng else "—", BLUE),
             (active, "active days", f"peak {peak[1]} on {fmt(peak[0])}" if peak[1] else "—", "#fbbf24")]
    for i, (num, label, sub, col) in enumerate(tiles):
        x = 36 + i * 286
        s.append(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" begin="{i*0.15:.2f}s" dur=".6s" fill="freeze"/>'
                 f'<rect x="{x}" y="70" width="270" height="112" rx="12" fill="#0d1117" stroke="#30363d"/>'
                 f'<rect x="{x}" y="70" width="4" height="112" rx="2" fill="{col}"/>'
                 f'<text x="{x+24}" y="128" font-size="44" font-weight="800" fill="{col}" filter="url(#glow)">{num}</text>'
                 f'<text x="{x+24}" y="152" font-size="15" font-weight="600" fill="{TEXT}">{label}</text>'
                 f'<text x="{x+24}" y="171" {mono} font-size="11" fill="{MUTED}">{sub}</text></g>')

    # heatmap
    first = dt.date.fromisoformat(days[0][0])
    pad = (first.weekday() + 1) % 7  # Sunday-first rows
    cell, gap, y0 = 15, 4, 236
    ncols = (len(days) + pad + 6) // 7
    x0 = (W - (ncols * (cell + gap) - gap)) // 2 + 14
    hi = max([n for _, n in days] + [1])
    last_month = None
    for i, (date, n) in enumerate(days):
        k = i + pad
        col, row = divmod(k, 7)
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        d = dt.date.fromisoformat(date)
        if row == 0 or i == 0:
            if d.month != last_month and col < 52:
                s.append(f'<text x="{x}" y="{y0-10}" font-size="11" fill="{MUTED}">{d:%b}</text>')
                last_month = d.month
        lvl = 0 if not n else min(4, 1 + int(3 * n / hi))
        extra = ''
        if i == len(days) - 1:
            extra = f' stroke="{PINK}" stroke-width="2"'
        s.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{TEAL[lvl]}"{extra} opacity="0">'
                 f'<title>{n} on {d:%d %b %Y}</title>'
                 f'<animate attributeName="opacity" from="0" to="1" begin="{0.4 + col*0.025:.3f}s" dur=".3s" fill="freeze"/></rect>')
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        s.append(f'<text x="{x0-10}" y="{y0 + r*(cell+gap) + 12}" text-anchor="end" font-size="11" fill="{MUTED}">{lab}</text>')
    lx = W - 36 - 5 * (cell + 2) - 70
    s.append(f'<text x="{lx}" y="{y0 + 7*(cell+gap) + 18}" font-size="11" fill="{MUTED}">less</text>')
    for j in range(5):
        s.append(f'<rect x="{lx + 30 + j*(cell+2)}" y="{y0 + 7*(cell+gap) + 7}" width="{cell}" height="{cell}" rx="3" fill="{TEAL[j]}"/>')
    s.append(f'<text x="{lx + 36 + 5*(cell+2)}" y="{y0 + 7*(cell+gap) + 18}" font-size="11" fill="{MUTED}">more</text>')

    # weekly trend (area chart)
    weeks = [sum(n for _, n in days[i:i+7]) for i in range(0, len(days), 7)]
    cx, cy, cw, ch = 36, 452, 700, 140
    s.append(f'<rect x="{cx}" y="{cy-30}" width="{cw}" height="{ch+50}" rx="12" fill="#0d1117" stroke="#30363d"/>')
    s.append(f'<text x="{cx+20}" y="{cy-8}" {mono} font-size="12" letter-spacing="1" fill="{MUTED}">WEEKLY CONTRIBUTIONS</text>')
    wm = max(weeks + [1])
    px = [cx + 20 + i * (cw - 40) / max(len(weeks) - 1, 1) for i in range(len(weeks))]
    py = [cy + ch - 10 - (w / wm) * (ch - 30) for w in weeks]
    line = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}" for i, (x, y) in enumerate(zip(px, py)))
    s.append(f'<path d="{line} L{px[-1]:.1f} {cy+ch-10} L{px[0]:.1f} {cy+ch-10} Z" fill="url(#area)" opacity="0">'
             '<animate attributeName="opacity" from="0" to="1" begin="1.6s" dur="1s" fill="freeze"/></path>')
    s.append(f'<path d="{line}" fill="none" stroke="{PINK}" stroke-width="2.5" stroke-linejoin="round" pathLength="100" '
             'stroke-dasharray="100" stroke-dashoffset="100" filter="url(#glow)">'
             '<animate attributeName="stroke-dashoffset" from="100" to="0" begin=".8s" dur="1.8s" fill="freeze"/></path>')
    s.append(f'<circle cx="{px[-1]:.1f}" cy="{py[-1]:.1f}" r="5" fill="{PINK}"><animate attributeName="r" values="4;7;4" dur="1.6s" repeatCount="indefinite"/></circle>')

    # weekday bars
    by_wd = [0] * 7
    for date, n in days:
        by_wd[(dt.date.fromisoformat(date).weekday() + 1) % 7] += n
    bx, bw = 764, 400
    s.append(f'<rect x="{bx}" y="{cy-30}" width="{bw}" height="{ch+50}" rx="12" fill="#0d1117" stroke="#30363d"/>')
    s.append(f'<text x="{bx+20}" y="{cy-8}" {mono} font-size="12" letter-spacing="1" fill="{MUTED}">BY WEEKDAY</text>')
    bm = max(by_wd + [1])
    top = by_wd.index(bm) if any(by_wd) else -1
    for j, (lab, v) in enumerate(zip("SMTWTFS", by_wd)):
        x = bx + 30 + j * 52
        h = 6 + (v / bm) * (ch - 50)
        col = PINK if j == top else TEAL[3]
        s.append(f'<rect x="{x}" y="{cy+ch-22-h:.1f}" width="34" height="{h:.1f}" rx="5" fill="{col}" opacity=".9">'
                 f'<animate attributeName="height" from="0" to="{h:.1f}" begin="{1+j*0.08:.2f}s" dur=".6s" fill="freeze"/>'
                 f'<animate attributeName="y" from="{cy+ch-22}" to="{cy+ch-22-h:.1f}" begin="{1+j*0.08:.2f}s" dur=".6s" fill="freeze"/></rect>')
        s.append(f'<text x="{x+17}" y="{cy+ch-4}" text-anchor="middle" font-size="12" fill="{MUTED}">{lab}</text>')
    s.append("</svg>")
    return "".join(s)


if __name__ == "__main__":
    if len(sys.argv) > 1:  # local test: python3 stats.py fixture.json
        days = json.load(open(sys.argv[1]))
    else:
        try:
            days = fetch_days()
        except Exception as e:
            print("GraphQL failed, using calendar page:", e)
            days = fetch_days_html()
    open(OUT, "w").write(build(days))
    print(f"wrote {OUT}: {sum(n for _, n in days)} contributions")

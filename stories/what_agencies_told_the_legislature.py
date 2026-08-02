"""Story: what Oregon agencies told the Legislature about their own performance —
and where the reported history later moved.

Source: oregon-kpm's extracted series (50,061 rows from 785 Annual Performance
Progress Reports). Two findings: the share of measures meeting their own target per
year, and the 1,700 places where overlapping five-year reporting windows disagree
about the same historical number — the restatement detector the corpus was built
around, working as designed.
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

SLUG = "what-agencies-told-the-legislature"
NUM = re.compile(r"-?[\d,]+\.?\d*")


def num(s):
    m = NUM.search(str(s) or "")
    return float(m.group().replace(",", "")) if m else None


def build() -> tuple[str, str, str]:
    d = json.loads(fetch(f"{RAW}/oregon-kpm/main/_meta/series.json",
                         "oregon-kpm extracted measure series"))
    rows = d["rows"]

    # Latest report wins per (agency, measure, submeasure, year): restatements mean the
    # same historical year appears in up to five reports, and the line must not count
    # one datapoint five times.
    latest = {}
    for r in rows:
        key = (r["agency"], r["measure_key"], r.get("submeasure"), r["year"])
        if key not in latest or r["reporting_year"] > latest[key]["reporting_year"]:
            latest[key] = r

    per_year = defaultdict(lambda: [0, 0])   # year -> [met, judged]
    n_no_dir = n_no_num = 0
    for r in latest.values():
        a, t = num(r.get("actual")), num(r.get("target"))
        if a is None or t is None:
            n_no_num += 1
            continue
        dcp = (r.get("data_collection_period") or "").lower()
        up, down = "upward trend" in dcp, "downward trend" in dcp
        if not (up or down):
            n_no_dir += 1
            continue
        y = r["year"]
        if not (y.isdigit() and 2012 <= int(y) <= 2025):
            continue
        per_year[y][1] += 1
        if (up and a >= t) or (down and a <= t):
            per_year[y][0] += 1

    years = sorted(per_year)
    W, H, PL, PB, PR = 880, 300, 44, 34, 30
    xw = (W - PL - PR) / (len(years) - 1)
    def X(i): return PL + i * xw
    def Y(p): return 16 + (H - PB - 16) * (1 - p)
    pts = [(X(i), Y(per_year[y][0] / per_year[y][1])) for i, y in enumerate(years)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    grid = "".join(
        f'<line x1="{PL}" y1="{Y(p):.1f}" x2="{W-PR}" y2="{Y(p):.1f}" stroke="var(--grid)"/>'
        f'<text x="{PL-8}" y="{Y(p)+4:.1f}" text-anchor="end">{p:.0%}</text>'
        for p in (0, .25, .5, .75, 1))
    xl = "".join(f'<text x="{X(i):.1f}" y="{H-10}" text-anchor="middle">{y}</text>'
                 for i, y in enumerate(years))
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="var(--s1)" '
                   f'stroke="var(--surface)" stroke-width="2" data-year="{years[i]}" '
                   f'data-met="{per_year[years[i]][0]}" data-n="{per_year[years[i]][1]}"/>'
                   for i, (x, y) in enumerate(pts))
    last = per_year[years[-1]]
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Share of measures meeting '
           f'their own target, by year">{grid}'
           f'<polyline points="{line}" fill="none" stroke="var(--s1)" stroke-width="2" '
           f'stroke-linejoin="round"/>{dots}{xl}'
           f'<text class="val" x="{W-PR-2}" y="{pts[-1][1]-10:.1f}" text-anchor="end">'
           f'{last[0]/last[1]:.0%} of {last[1]}</text></svg>')

    # Restatements: same (agency, measure, submeasure, year), different numeric actual
    # in different reports.
    groups = defaultdict(dict)
    for r in rows:
        key = (r["agency"], r["measure_key"], r.get("submeasure"), r["year"])
        a = num(r.get("actual"))
        if a is not None:
            groups[key][r["reporting_year"]] = (a, r.get("actual"))
    restated = {k: v for k, v in groups.items()
                if len({a for a, _ in v.values()}) > 1}
    exemplars = sorted(
        restated.items(),
        key=lambda kv: -(max(a for a, _ in kv[1].values())
                         - min(a for a, _ in kv[1].values())))[:12]
    tr = []
    for (ag, mk, sub, y), reps in exemplars:
        seq = " → ".join(f"{raw} <small>({ry})</small>"
                         for ry, (_, raw) in sorted(reps.items()))
        tr.append(f"<tr><td>{html.escape(ag)}</td>"
                  f"<td>{html.escape((sub or mk)[:70])}</td>"
                  f"<td class='num'>{y}</td><td>{seq}</td></tr>")
    table = ('<table><thead><tr><th>agency</th><th>measure</th><th class="num">year'
             '</th><th>the same year, as reported in successive reports</th></tr>'
             f'</thead><tbody>{"".join(tr)}</tbody></table>')

    script = """
var tip = document.getElementById('tip');
document.querySelectorAll('svg [data-year]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent = '';
    var v = document.createElement('strong');
    v.textContent = el.dataset.met + ' of ' + el.dataset.n + ' ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode(
      'directional measures met their own target in ' + el.dataset.year));
    tip.style.display='block';
    tip.style.left = Math.min(ev.clientX+14, innerWidth-320)+'px';
    tip.style.top = (ev.clientY+14)+'px';
  });
  el.addEventListener('pointerleave', function(){ tip.style.display='none'; });
});
"""
    n_latest = len(latest)
    judged = sum(v[1] for v in per_year.values())
    lede = (f"Every year, Oregon agencies report their Key Performance Measures to the "
            f"Legislature: a target, an actual, and which direction counts as better. "
            f"Across {judged:,} measure-years where all three are machine-readable, "
            f"roughly half met their own target — and the reported history itself is "
            f"not fixed: <b>{len(restated):,} measure-years changed value between "
            f"successive reports</b>, which the overlapping five-year reporting windows "
            f"make detectable rather than invisible.")

    caveats = (
        f"<p><b>Coverage is stated, not assumed.</b> Of {n_latest:,} deduplicated "
        f"measure-years, {n_no_num:,} lack a machine-readable number on one side and "
        f"{n_no_dir:,} state no direction ('upward/downward trend = positive result') — "
        f"both are excluded from the line and counted here. Meeting a self-set target "
        f"is not the same as performing well: agencies set their own targets, and the "
        f"green/yellow/red assessment the state itself publishes is deliberately NOT "
        f"reproduced here because it does not survive text extraction — recomputing it "
        f"would be our arithmetic presented as the agency's judgment. <b>A restatement "
        f"is not an error</b>: methodologies change and data gets corrected; what "
        f"matters is that the platform shows the movement instead of silently keeping "
        f"one version. The corpus's own restatement count (1,700) uses a broader definition that includes non-numeric changes; this page counts only measure-years whose NUMERIC actual differs between reports — the stricter cut. Extraction quality figures ship with the corpus "
        f"(213 unparsed blocks; 5,774 rows without a collection period).</p>")

    body = (f'<div class="panel">{svg}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Twelve of the '
            f'{len(restated):,} restatements — the same year, re-reported</h2>{table}</div>')

    page = viz.chart_page(
        title=f"About half of Oregon's performance measures meet their own targets — "
              f"and {len(restated):,} reported numbers later moved",
        eyebrow="oregon-stories · from the oregon-kpm corpus",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"~half of directional KPM measure-years met their own target; "
             f"{len(restated):,} reported numbers moved between reports")
    return SLUG, claim, page

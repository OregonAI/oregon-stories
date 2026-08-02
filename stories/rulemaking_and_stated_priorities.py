"""Story: rulemaking activity in the Governor's four stated priority areas, against
the corpus-wide baseline.

Source: ERF's governor_priorities.json — a CURATED mapping of OAR chapters to the
administration's stated priority areas, with per-year rulemaking counts and the
corpus baseline. The file was built to be visualized and carries its own framing
caveats; every one renders here. Framing rule (operator, standing): offices, never
parties; description, never cause.
"""
from __future__ import annotations

import html
import json

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "rulemaking-and-stated-priorities"
YEARS = list(range(2015, 2027))


def build() -> tuple[str, str, str]:
    d = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/governor_priorities.json",
                         "ERF governor-priorities dataset (curated mapping)"))
    baseline = d["baseline_recent_rate"]
    panels = []
    for i, area in enumerate(d["areas"], 1):
        yrs = {int(k): v for k, v in (area.get("years") or {}).items()}
        vals = [yrs.get(y, 0) for y in YEARS]
        vmax = max(vals) or 1
        W, H, PB = 400, 150, 26
        bw = (W - 20) / len(YEARS)
        bars = "".join(
            f'<rect x="{10 + j*bw + 1:.1f}" y="{16 + (H-PB-16)*(1 - v/vmax):.1f}" '
            f'width="{bw-2:.1f}" height="{(H-PB-16)*v/vmax:.1f}" rx="2" '
            f'fill="var(--s1)" data-area="{html.escape(area["name"])}" '
            f'data-year="{YEARS[j]}" data-n="{v}"/>'
            for j, v in enumerate(vals))
        xticks = "".join(f'<text x="{10 + (j+0.5)*bw:.0f}" y="{H-8}" '
                         f'text-anchor="middle" font-size="10">{str(y)[2:]}</text>'
                         for j, y in enumerate(YEARS) if y % 2 == 1)
        rate = area.get("recent_2yr", 0) / (area.get("n_dated") or 1)
        caveat = (f'<p style="margin:6px 0 0;font-size:12px;color:var(--muted)">'
                  f'{html.escape(area["caveat"])}</p>') if area.get("caveat") else ""
        panels.append(
            f'<div class="panel" style="display:inline-block;width:calc(50% - 12px);'
            f'min-width:330px;vertical-align:top">'
            f'<h2 style="font-size:14.5px;margin:0">{html.escape(area["name"])}</h2>'
            f'<p style="margin:2px 0 4px;font-size:12.5px;color:var(--ink2)">'
            f'{area["n_rules"]:,} rules in the mapped chapters · recent-2yr rate '
            f'<b>{rate:.0%}</b> vs {baseline:.0%} corpus-wide</p>'
            f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Rules amended per year, '
            f'{html.escape(area["name"])}">{bars}{xticks}</svg>{caveat}</div>')

    script = """
var tip=document.getElementById('tip');
document.querySelectorAll('svg [data-year]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent='';
    var v=document.createElement('strong');
    v.textContent=el.dataset.n+' rules ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode('amended in '+el.dataset.year+' — '+el.dataset.area));
    tip.style.display='block';
    tip.style.left=Math.min(ev.clientX+14,innerWidth-320)+'px';
    tip.style.top=(ev.clientY+14)+'px';
  });
  el.addEventListener('pointerleave',function(){tip.style.display='none';});
});
"""
    lede = (f"The Governor's office states four priority areas; this maps each to the "
            f"OAR chapters most plausibly implementing it and asks one factual "
            f"question: is rulemaking in those chapters more recent than the corpus "
            f"baseline ({baseline:.0%} of all {d['total_oar_rules']:,} rules amended "
            f"in the last two years)? Bars are rules amended per year, 2015 onward; "
            f"each panel states its own mapped-rule denominator.")

    caveats = (
        f"<p>{html.escape(d['note'])}</p><p>{html.escape(d['viz_note'])}</p>"
        f"<p><b>Framing:</b> this page describes rule volume against stated priorities "
        f"of the office — it names no parties, compares no administrations, and draws "
        f"no causal conclusions. {d['mapped_rules']:,} of {d['total_oar_rules']:,} "
        f"rules are in mapped chapters; the rest are simply out of scope of the "
        f"mapping, not evidence of anything.</p>")

    page = viz.chart_page(
        title="Rulemaking in the Governor's four stated priority areas, measured "
              "against the baseline",
        eyebrow="oregon-stories · from the executive-regulatory-frameworks corpus "
                "(curated mapping)",
        lede_html=lede,
        body_html=f'<div>{"".join(panels)}</div>',
        caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = ("Rulemaking recency in the four stated priority areas vs the "
             f"{baseline:.0%} corpus baseline — curated mapping, caveats on page")
    return SLUG, claim, page

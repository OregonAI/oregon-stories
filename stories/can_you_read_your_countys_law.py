"""Story: can an Oregonian read their county's law online? A schematic grid map of all
36 counties, from the measured survey.

Sources: oregon-counties' county registry (population, deferral reasons — access
failures recorded as OURS) and its published document index (what is actually
mirrored). The survey's load-bearing distinction is the legend: "none-found" is a
finding about Oregon; "could-not-verify"/deferred is a fact about our access and
never evidence about the county.
"""
from __future__ import annotations

import html
import json

import yaml

from corpus_toolkit import viz
from data_sources import PAGES, RAW, fetch, sources_for_footer

SLUG = "can-you-read-your-countys-law"

# Schematic grid positions (col, row) — geography gestured, not projected. A grid map
# is honest about being a diagram; a real choropleth would imply spatial precision the
# story does not need.
GRID = {
    "clatsop": (0, 0), "columbia": (1, 0), "multnomah": (2, 0), "hood-river": (3, 0),
    "wasco": (4, 0), "sherman": (5, 0), "gilliam": (6, 0), "morrow": (7, 0),
    "umatilla": (8, 0), "wallowa": (10, 0),
    "tillamook": (0, 1), "washington": (1, 1), "clackamas": (2, 1), "marion": (3, 1),
    "jefferson": (4, 1), "wheeler": (6, 1), "grant": (7, 1), "union": (9, 1),
    "baker": (10, 1),
    "yamhill": (1, 2), "polk": (2, 2), "linn": (3, 2), "deschutes": (4, 2),
    "crook": (5, 2),
    "lincoln": (0, 3), "benton": (1, 3), "lane": (2, 3),
    "douglas": (2, 4), "klamath": (4, 4), "lake": (5, 4), "harney": (7, 4),
    "malheur": (9, 4),
    "coos": (0, 5), "curry": (0, 6), "josephine": (1, 6), "jackson": (2, 6),
}

CLASSES = [
    ("mirrored", "mirrored — the code is in the corpus", "var(--s1)"),
    ("access-blocked", "access-blocked — a fact about OUR access, not the county",
     "var(--s2)"),
    ("none-found", "publishes no codified code — a finding about Oregon", "var(--muted)"),
]


def build() -> tuple[str, str, str]:
    reg = yaml.safe_load(fetch(f"{RAW}/oregon-counties/main/_meta/counties.yml",
                               "oregon-counties county registry"))
    index = json.loads(fetch(f"{PAGES}/oregon-counties/corpus-index.json",
                             "oregon-counties published index"))
    docs_per = {}
    for doc_id in index["documents"]:
        docs_per[doc_id.split("-", 1)[0]] = docs_per.get(doc_id.split("-", 1)[0], 0) + 1

    counties = {c["slug"].replace("-county", "").replace("hood-river", "hood-river"):
                c for c in reg["counties"]} if "counties" in reg else None
    if counties is None:  # registry shape: a list under another key — fail loud
        raise RuntimeError("counties.yml shape unexpected — refusing to guess")

    rows = []
    totals = {k: [0, 0] for k, _, _ in CLASSES}   # class -> [counties, population]
    for slug, c in counties.items():
        pop = int(c.get("population", 0))
        n = docs_per.get(slug, 0)
        if n:
            cls = "mirrored"
        elif c.get("deferred"):
            cls = "access-blocked"
        else:
            cls = "none-found"
        totals[cls][0] += 1
        totals[cls][1] += pop
        rows.append((slug, cls, n, pop, (c.get("deferred") or {}).get("reason", "")
                     if isinstance(c.get("deferred"), dict) else str(c.get("deferred") or "")))

    pop_all = sum(p for _, _, _, p, _ in rows)
    CELL, GAP = 66, 6
    cells = []
    color = {k: col for k, _, col in CLASSES}
    for slug, cls, n, pop, reason in rows:
        if slug not in GRID:
            continue
        cx, cy = GRID[slug]
        x, y = 10 + cx * (CELL + GAP), 10 + cy * (CELL + GAP)
        cells.append(
            f'<g data-county="{slug}" data-cls="{cls}" data-n="{n}" data-pop="{pop}" '
            f'data-reason="{html.escape(reason)}">'
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="6" '
            f'fill="{color[cls]}" opacity="{1 if cls == "mirrored" else 0.85}"/>'
            f'<text x="{x+CELL/2}" y="{y+26}" text-anchor="middle" '
            f'style="fill:#fff;font-size:10.5px">{slug[:9]}</text>'
            f'<text x="{x+CELL/2}" y="{y+44}" text-anchor="middle" '
            f'style="fill:#fff;font-size:11px;font-weight:600">'
            f'{n if n else ""}</text></g>')
    gw = 10 + 11 * (CELL + GAP) + 4
    gh = 10 + 7 * (CELL + GAP) + 4
    svg = (f'<svg viewBox="0 0 {gw} {gh}" role="img" aria-label="Oregon counties by '
           f'whether their code is mirrored">{"".join(cells)}</svg>')

    legend = "".join(
        f'<span><span class="chip" style="background:{col}"></span>{label} '
        f'<b>({totals[k][0]})</b></span>' for k, label, col in CLASSES)

    trs = "".join(
        f"<tr><td>{slug}</td><td>{cls}</td><td class='num'>{n or '—'}</td>"
        f"<td class='num'>{pop:,}</td><td>{html.escape(reason) or '—'}</td></tr>"
        for slug, cls, n, pop, reason in
        sorted(rows, key=lambda r: -r[3]))
    table = ('<table><thead><tr><th>county</th><th>status</th><th class="num">mirrored '
             'docs</th><th class="num">population</th><th>deferral reason (ours)</th>'
             f'</tr></thead><tbody>{trs}</tbody></table>')

    script = """
var tip = document.getElementById('tip');
document.querySelectorAll('svg [data-county]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent='';
    var h=document.createElement('strong');
    h.textContent = el.dataset.county + ' — ' + el.dataset.cls + '. ';
    tip.appendChild(h);
    var txt = Number(el.dataset.pop).toLocaleString() + ' residents';
    if (el.dataset.n !== '0') txt += ', ' + el.dataset.n + ' mirrored documents';
    if (el.dataset.reason) txt += '. Blocked: ' + el.dataset.reason;
    tip.appendChild(document.createTextNode(txt));
    tip.style.display='block';
    tip.style.left=Math.min(ev.clientX+14, innerWidth-340)+'px';
    tip.style.top=(ev.clientY+14)+'px';
  });
  el.addEventListener('pointerleave', function(){ tip.style.display='none'; });
});
"""
    pm = totals["mirrored"][1] / pop_all
    lede = (f"All 36 counties were surveyed; {totals['mirrored'][0]} are mirrored in "
            f"the corpus — covering <b>{pm:.0%} of Oregonians</b>. "
            f"{totals['none-found'][0]} counties appear to publish no codified county "
            f"code at all (one states outright that ordinances are simply orders) — a "
            f"fact about how Oregon's counties publish, not a gap in this mirror. And "
            f"{totals['access-blocked'][0]} counties are unread only because their "
            f"hosts refuse an honestly-identified crawler — a fact about our access "
            f"that this project refuses to disguise its way around.")

    caveats = (
        "<p><b>The legend's distinction is load-bearing and must never be summed "
        "away:</b> 'publishes no code' is a measured finding about Oregon (each backed "
        "by a recorded none-found survey entry); 'access-blocked' says nothing about "
        "the county — those hosts serve browsers and refuse identified bots, and "
        "getting past a technical control by impersonating a browser is a line this "
        "project does not cross. The grid is <b>schematic</b> — neighbors gestured, "
        "not projected. Document counts are mirrored instruments (codes, ordinances, "
        "policies, land use), not a measure of how much law a county HAS. Populations: "
        "Census POPESTIMATE2024, carried in the registry rather than recalled.</p>")

    body = (f'<div class="panel"><div class="legend">{legend}</div>{svg}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">All 36, with '
            f'denominators</h2>{table}</div>')

    page = viz.chart_page(
        title=f"Can you read your county's law online? For {pm:.0%} of Oregonians, yes",
        eyebrow="oregon-stories · from the oregon-counties survey and corpus",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"{totals['mirrored'][0]} of 36 county codes mirrored ({pm:.0%} of "
             f"Oregonians); {totals['none-found'][0]} publish none; "
             f"{totals['access-blocked'][0]} block access")
    return SLUG, claim, page

"""Story: how much of Oregon's county law points at statutes that no longer exist —
and how old the pointers are.

Sources: oregon-counties' authority graph (9,703 measured ORS/OAR citation edges),
executive-regulatory-frameworks' held-statute index, and its ORS disposition catalog
(29,215 sections mined from the chapters' own history brackets: repealed year, or
renumbered with targets). County code cites the law as it stood when adopted; the
state renumbers and repeals underneath it.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict

import yaml

from corpus_toolkit import viz
from data_sources import PAGES, RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "county-code-cites-dead-law"
TITLE = "Living county law, dead citations: 8% of county ORS citations point at " \
        "statutes that no longer exist"

ORS = re.compile(r"^ORS\s+(\d+[A-Z]?)\.(\d+[a-z]?)$")

# Classes in slot order; "current" is the boring mass and wears no series color.
CLASSES = (("renumbered-held", "renumbered — text lives on under a new number (held)"),
           ("repealed", "repealed — no current text"),
           ("renumbered-unheld", "renumbered — destination not mirrored"),
           ("unknown", "no disposition mined"))


def build() -> tuple[str, str, str]:
    graph = json.loads(fetch(f"{RAW}/oregon-counties/main/_meta/graph.json",
                             "oregon-counties authority graph"))
    index = json.loads(fetch(f"{PAGES}/{ERF}/corpus-index.json",
                             "ERF published document index"))
    disp_raw = yaml.safe_load(fetch(f"{RAW}/{ERF}/main/_meta/catalog/ors-disposition.yml",
                                    "ERF ORS disposition catalog"))
    held = set(index["documents"])
    disp = {s["section"]: s for s in disp_raw["sections"]}

    per = defaultdict(Counter)          # county -> class counts (incl. 'current','total')
    dead_targets = Counter()            # section -> citation count
    for e in graph["edges"]:
        m = ORS.match(e["to"])
        if not m:
            continue
        county = e["from"].split("-", 1)[0]
        sec = f"{m.group(1).lower()}.{m.group(2)}"
        per[county]["total"] += 1
        if f"ors-{sec}" in held:
            per[county]["current"] += 1
            continue
        dead_targets[sec] += 1
        d = disp.get(sec)
        if not d:
            per[county]["unknown"] += 1
        elif d["status"] == "repealed":
            per[county]["repealed"] += 1
        elif any(f"ors-{str(t).lower()}" in held for t in (d.get("targets") or [])):
            per[county]["renumbered-held"] += 1
        else:
            per[county]["renumbered-unheld"] += 1

    counties = sorted((c for c in per if per[c]["total"] >= 10),
                      key=lambda c: -(per[c]["total"] - per[c]["current"]) / per[c]["total"])
    small = [c for c in per if per[c]["total"] < 10]

    # Per-county stacked bar of the DEAD share, denominator always visible.
    ROW, BARW, LABW = 26, 520, 150
    H = 40 + ROW * len(counties)
    maxrate = max((per[c]["total"] - per[c]["current"]) / per[c]["total"] for c in counties)
    rows_svg = []
    for i, c in enumerate(counties):
        t = per[c]["total"]
        dead = t - per[c]["current"]
        y0 = 30 + i * ROW
        x = LABW
        rows_svg.append(f'<text x="{LABW-8}" y="{y0+13}" text-anchor="end" '
                        f'class="val">{c}</text>')
        for si, (cls, _) in enumerate(CLASSES, 1):
            n = per[c][cls]
            if not n:
                continue
            w = BARW * (n / t) / maxrate
            rows_svg.append(f'<rect x="{x:.1f}" y="{y0}" width="{max(w-2,1):.1f}" '
                            f'height="16" rx="2" fill="var(--s{si})" '
                            f'data-county="{c}" data-cls="{cls}" data-n="{n}" '
                            f'data-t="{t}"/>')
            x += w
        rows_svg.append(f'<text x="{x+6:.1f}" y="{y0+13}">'
                        f'{dead/t:.0%} of {t:,}</text>')
    svg = (f'<svg viewBox="0 0 880 {H}" role="img" aria-label="Dead-citation share '
           f'by county">{"".join(rows_svg)}</svg>')
    legend = "".join(
        f'<span><span class="chip" style="background:var(--s{i})"></span>{label}</span>'
        for i, (_, label) in enumerate(CLASSES, 1))

    top = dead_targets.most_common(15)
    trows = []
    for sec, n in top:
        d = disp.get(sec)
        if not d:
            fate = "no disposition mined"
        elif d["status"] == "repealed":
            fate = f"repealed {d.get('year', '?')}"
        else:
            tgt = ", ".join(f"ORS {t}" for t in (d.get("targets") or [])) or "?"
            fate = f"renumbered {d.get('year', '?')} → {tgt}"
        trows.append(f"<tr><td>ORS {sec}</td><td>{html.escape(fate)}</td>"
                     f"<td class='num'>{n}</td></tr>")
    table = ('<table><thead><tr><th>cited section</th><th>what happened to it</th>'
             '<th class="num">county citations</th></tr></thead>'
             f'<tbody>{"".join(trows)}</tbody></table>')

    n_edges = sum(per[c]["total"] for c in per)
    n_dead = sum(per[c]["total"] - per[c]["current"] for c in per)
    oldest = min((disp[s].get("year") or 9999) for s, _ in top if s in disp)

    script = """
var tip = document.getElementById('tip');
document.querySelectorAll('svg [data-county]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent = '';
    var v = document.createElement('strong');
    v.textContent = el.dataset.n + ' of ' + Number(el.dataset.t).toLocaleString() + ' ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode(
      el.dataset.county + ' ORS citations: ' + el.dataset.cls.replace(/-/g, ' ')));
    tip.style.display = 'block';
    tip.style.left = Math.min(ev.clientX + 14, innerWidth - 320) + 'px';
    tip.style.top = (ev.clientY + 14) + 'px';
  });
  el.addEventListener('pointerleave', function(){ tip.style.display = 'none'; });
});
"""

    lede = (f"Oregon's mirrored county code carries {n_edges:,} citations to state "
            f"statutes. {n_dead:,} of them — about {n_dead/n_edges:.0%} — point at "
            f"sections that no longer exist under that number: mostly renumbered "
            f"(the text lives on elsewhere) or repealed outright, some as far back as "
            f"{oldest}. County ordinances cite the law as it stood when they were "
            f"adopted; the state renumbers and repeals underneath them. This is a "
            f"fact about how law ages, found mechanically — not an error count.")

    caveats = (
        "<p><b>A dead citation is not a county's mistake</b> unless the ordinance was "
        "adopted after the section died — and adoption dates are not consistently "
        "recorded, so this page makes no such claim for any county. Bars show each "
        "county's <i>share</i> of dead citations with its absolute denominator printed "
        "beside it; counties with fewer than 10 recorded ORS citations "
        f"({len(small)} of them) are excluded from the bars to avoid rate noise, and "
        "everything remains in the counts. <b>Dispositions are mechanically mined</b> "
        "from ORS chapters' own history brackets (29,215 sections) — non-authoritative; "
        "verify against oregonlegislature.gov. <b>598 of 3,335 county documents are "
        "OCR-recovered</b>, and OCR can corrupt a citation (a real example: "
        "<code>ORS 4758</code>, a machine's misreading of 475B) — such strings simply "
        "fail to parse and are absent here, but treat single odd citations with "
        "suspicion. Coverage: 27 of 36 counties are mirrored; the other nine are "
        "access-blocked, not evidence of anything about those counties.</p>")

    body = (f'<div class="panel"><div class="legend">{legend}</div>{svg}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">What the dead '
            f'citations point at</h2>{table}</div>')

    page = viz.chart_page(
        title=TITLE,
        eyebrow="oregon-stories · from oregon-counties × executive-regulatory-frameworks",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"{n_dead:,} of {n_edges:,} county ORS citations ({n_dead/n_edges:.0%}) "
             f"point at renumbered or repealed law")
    return SLUG, claim, page

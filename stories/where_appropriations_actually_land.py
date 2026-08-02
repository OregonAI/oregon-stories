"""Story: what happens when you try to follow every appropriation Oregon writes —
the honest classification of 740 extracted appropriation documents.

Source: oregon-budget's published index and its generated unresolved-agencies report.
The story is the classification itself: which appropriations join to spending, which
bills genuinely name no recipient (blank templates), which only amend prior session
laws, and which cannot join for stated reasons. Deliberately NOT a dollars-flow
diagram: the budget corpus's own core rule is that an appropriation and an agency's
total spending must never be presented as though one accounts for the other.
"""
from __future__ import annotations

import html
import json
import re

from corpus_toolkit import viz
from data_sources import PAGES, RAW, fetch, sources_for_footer

SLUG = "where-appropriations-actually-land"


def build() -> tuple[str, str, str]:
    index = json.loads(fetch(f"{PAGES}/oregon-budget/corpus-index.json",
                             "oregon-budget published index"))
    report = fetch(f"{RAW}/oregon-budget/main/_meta/unresolved-agencies.md",
                   "oregon-budget unresolved-agencies report (generated)").decode()

    docs = index["documents"]
    n_bills = sum(1 for k in docs if k.startswith("appropriations-"))
    n_joins = sum(1 for k in docs if k.startswith("join-"))
    n_exp = sum(1 for k in docs if k.startswith("expenditures-"))

    def bucket(header_re):
        m = re.search(header_re + r".*?\*\*(\d+) appropriations?\*\*", report, re.S)
        return int(m.group(1)) if m else 0

    blank = bucket(r"## 1\. The BILL leaves the recipient blank")
    failed = bucket(r"## 1b\. Extraction genuinely failed")
    modifies = bucket(r"## 1c\. The bill only MODIFIES")
    multi = bucket(r"## 1d\. Multi-recipient")
    nocode = bucket(r"## 3\. In the registry, but no budget code")
    absent = bucket(r"## 4\. No registry counterpart")
    in_window = blank + failed + modifies + multi + nocode + absent
    # joined-in-window from the report's own headline
    m = re.search(r"\*\*(\d+) appropriations\*\* across", report)
    unjoined = int(m.group(1)) if m else in_window

    classes = [
        ("joined to spending", n_joins, "var(--s1)",
         "an entity-and-period link to the agency's recorded spending — never a claim "
         "that the spending accounts for the appropriation"),
        ("bill names no recipient (blank template)", blank, "var(--s2)",
         "the 5000-series budget shells: 'appropriated to &#95;&#95;&#95;&#95;&#95;&#95;' — no agency exists "
         "in the text to join"),
        ("only modifies prior session laws", modifies, "var(--s3)",
         "the recipient lives in the amended chapter, not this bill"),
        ("multi-recipient itemization", multi, "var(--s4)",
         "several recipients in one list; a single join would misattribute"),
        ("no separate spending line / no registry counterpart", nocode + absent,
         "var(--s5)",
         "bodies funded through parents, or outside the executive rulemaking scheme "
         "(Emergency Board, legislative offices)"),
        ("extraction genuinely failed", failed, "var(--s8)",
         "the parser's honest residual"),
    ]
    total = sum(n for _, n, _, _ in classes)

    W, BARH = 860, 44
    x = 0
    segs, leg = [], []
    for name, n, col, _ in classes:
        if not n:
            continue
        w = W * n / total
        segs.append(f'<rect x="{x:.1f}" y="0" width="{max(w-2,1):.1f}" height="{BARH}" '
                    f'rx="3" fill="{col}" data-name="{html.escape(name)}" data-n="{n}" '
                    f'data-t="{total}"/>')
        x += w
    svg = (f'<svg viewBox="0 0 {W} {BARH}" role="img" '
           f'aria-label="Appropriation documents by classification">{"".join(segs)}</svg>')
    leg = "".join(f'<span><span class="chip" style="background:{col}"></span>'
                  f'{name} <b>({n})</b></span>'
                  for name, n, col, _ in classes if n)

    rows = "".join(f"<tr><td><span class='chip' style='background:{col}'></span>"
                   f"{name}</td><td class='num'>{n}</td><td>{why}</td></tr>"
                   for name, n, col, why in classes)
    table = ('<table><thead><tr><th>classification</th><th class="num">count</th>'
             f'<th>what it means</th></tr></thead><tbody>{rows}</tbody></table>')

    script = """
var tip=document.getElementById('tip');
document.querySelectorAll('svg [data-name]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent='';
    var v=document.createElement('strong');
    v.textContent=el.dataset.n+' of '+el.dataset.t+' ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode(el.dataset.name));
    tip.style.display='block';
    tip.style.left=Math.min(ev.clientX+14,innerWidth-320)+'px';
    tip.style.top=(ev.clientY+14)+'px';
  });
  el.addEventListener('pointerleave',function(){tip.style.display='none';});
});
"""
    lede = (f"The corpus extracted {n_bills} appropriation documents from Oregon's "
            f"budget bills and tried to follow each one to the agency's recorded "
            f"spending ({n_exp} agency-year mirrors, FY2019–FY2025). {n_joins} joins "
            f"exist — and every non-join is a stated decision, not a silent gap. The "
            f"most surprising class: <b>{blank} appropriations whose bills genuinely "
            f"name nobody</b> — introduced budget templates reading "
            f"“appropriated to &#95;&#95;&#95;&#95;&#95;&#95;”, a fact about how Oregon drafts bills.")

    caveats = (
        "<p><b>This is deliberately not a money-flow diagram.</b> The budget corpus's "
        "own rule: an appropriation goes to an agency for a purpose; the expenditure "
        "data records that agency's TOTAL spending from every source — presenting the "
        "two as though one accounts for the other would fabricate a fiscal claim, so "
        "joins are entity-and-period links only, and so is this page. Counts come from "
        "the corpus's generated unresolved report and published index at build time; "
        "appropriations outside the FY2019–25 expenditure window are classified in the "
        "corpus but have nothing to join to yet. Every figure in every underlying "
        "document is marked human_reviewed: false until a person checks it.</p>")

    body = (f'<div class="panel">{svg}<div class="legend">{leg}</div></div>'
            f'<div class="panel">{table}</div>')

    page = viz.chart_page(
        title=f"{n_joins} of Oregon's appropriations join to spending — and every "
              f"one that doesn't says why",
        eyebrow="oregon-stories · from the oregon-budget corpus",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"{n_joins} appropriation→spending joins; {blank} bills name nobody; "
             f"every non-join carries a stated reason")
    return SLUG, claim, page

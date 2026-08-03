"""Story: how few payees absorb each Oregon agency's recorded spending —
the top-20 payee share, agency by agency.

Source: oregon-budget's generated vendor-concentration export
(_meta/vendor-concentration.json): per agency x fiscal year over the committed
Parquet mirror, the share of total recorded expense going to the agency's 20
largest payee strings. The export's central caveat is this page's central caveat,
placed on the chart itself and not just in the caveats block: vendor strings are
NOT de-duplicated upstream, so every share is a FLOOR — real concentration is
higher, never lower. Agencies with 20 or fewer payees necessarily show 100% and
are greyed in the strip and excluded from the table by a stated threshold.
"""
from __future__ import annotations

import html
import json
import math
import statistics

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

SLUG = "vendor-concentration"

MIN_PAYEES_FOR_TABLE = 100

# Direct-label a few large, widely recognized agencies, with short display
# names (labels only; tables keep the export's verbatim names). Transportation
# is deliberately not labeled: its share sits within a few pixels of
# Education's and the labels would collide.
LABEL_AGENCIES = {"EDUCATION, DEPT OF": "Dept of Education",
                  "OREGON HEALTH AUTHORITY": "Health Authority"}


def _money(n: float) -> str:
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            s = f"{n / div:.1f}".removesuffix(".0")
            return f"${s}{suf}"
    return f"${n:,.0f}"


def build() -> tuple[str, str, str]:
    d = json.loads(fetch(f"{RAW}/oregon-budget/main/_meta/vendor-concentration.json",
                         "oregon-budget vendor-concentration export (generated)"))
    rows = d["rows"]
    note = d["note"]
    fy_lo = min(r["fiscal_year"] for r in rows)
    fy_hi = max(r["fiscal_year"] for r in rows)
    latest = [r for r in rows if r["fiscal_year"] == fy_hi]
    n_ag = len(latest)

    shares = sorted(r["top20_share"] for r in latest)
    med = statistics.median(shares)
    small = [r for r in latest if r["n_payees"] <= 20]     # necessarily 100%
    low = min(latest, key=lambda r: r["top20_share"])

    # ============== chart 1: dot strip / beeswarm, latest FY ==============
    W, H, PL, PR = 880, 430, 54, 16
    CY, R, STEP = 205, 5, 12          # strip centerline, dot radius, stack pitch

    def X(s): return PL + (W - PL - PR) * s

    placed: list[tuple[float, float]] = []

    def place(px: float) -> float:
        for k in range(0, 40):
            for kk in ((0,) if k == 0 else (k, -k)):
                py = CY + kk * STEP
                if all((px - qx) ** 2 + (py - qy) ** 2 >= STEP ** 2
                       for qx, qy in placed):
                    placed.append((px, py))
                    return py
        placed.append((px, CY))
        return CY

    dots, label_marks = [], []
    for r in sorted(latest, key=lambda r: r["top20_share"]):
        px = X(r["top20_share"])
        py = place(px)
        grey = r["n_payees"] <= 20
        fill = "var(--muted)" if grey else "var(--s1)"
        dots.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{R}" fill="{fill}" '
            f'stroke="var(--surface)" stroke-width="2" '
            f'data-h="{r["top20_share"]:.1%} " '
            f'data-b="of {html.escape(r["agency_name"])} recorded FY{fy_hi} '
            f'spending went to its top 20 payee strings '
            f'({r["n_payees"]:,} payees, {_money(r["total_expense"])} total)"/>')
        if r["agency_name"] in LABEL_AGENCIES or r is low:
            label_marks.append((px, py, r))

    # direct labels: the low extreme + named big agencies, staggered on two tiers
    # above the strip, with hairline leaders down to the dot.
    labels = []
    for i, (px, py, r) in enumerate(sorted(label_marks, key=lambda t: t[0])):
        name = LABEL_AGENCIES.get(r["agency_name"],
                                  r["agency_name"].title().strip())
        if r is low:
            name = f"lowest: {name}" if r["agency_name"] in LABEL_AGENCIES \
                else f"lowest: {name.split(',')[0]}"
        ly = 22 if i % 2 == 0 else 44
        labels.append(
            f'<line x1="{px:.1f}" y1="{ly+6}" x2="{px:.1f}" y2="{py-R-3:.1f}" '
            f'stroke="var(--axis)"/>'
            f'<text class="val" x="{px:.1f}" y="{ly:.1f}" text-anchor="middle">'
            f'{html.escape(name)} ({r["top20_share"]:.0%})</text>')

    mx = X(med)
    median_mark = (
        f'<line x1="{mx:.1f}" y1="64" x2="{mx:.1f}" y2="{H-40}" '
        f'stroke="var(--ink2)" stroke-width="1"/>'
        f'<text class="val" x="{mx:.1f}" y="58" text-anchor="middle">'
        f'median {med:.0%}</text>')
    xticks = "".join(
        f'<line x1="{X(t):.1f}" y1="{H-36}" x2="{X(t):.1f}" y2="{H-32}" '
        f'stroke="var(--axis)"/>'
        f'<text x="{X(t):.1f}" y="{H-18}" text-anchor="middle">{t:.0%}</text>'
        for t in (0, .2, .4, .6, .8, 1))
    base = f'<line x1="{PL}" y1="{H-36}" x2="{W-PR}" y2="{H-36}" stroke="var(--axis)"/>'
    svg1 = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Top-20 payee share '
            f'of recorded spending, one dot per agency, FY{fy_hi}">'
            f'{base}{xticks}{"".join(dots)}{median_mark}{"".join(labels)}</svg>')
    legend1 = (
        f'<div class="legend">'
        f'<span><span class="chip" style="background:var(--s1)"></span>'
        f'agency with more than 20 payees</span>'
        f'<span><span class="chip" style="background:var(--muted)"></span>'
        f'20 or fewer payees ({len(small)} agencies) — the top-20 share is '
        f'necessarily 100%, so the dot is greyed and the agency is excluded '
        f'from the table below</span></div>')
    chart_note = (
        '<p style="color:var(--ink2);font-size:13px;margin:8px 0 0;max-width:78ch">'
        '<b>Every share on this chart is a floor.</b> Payee strings are not '
        'de-duplicated upstream — the same vendor can appear under several '
        'spellings — so real concentration is higher, never lower.</p>')

    # ========= chart 2: share vs agency size (log-x scatter) =========
    H2, PT2, PB2 = 300, 16, 40
    lo_d = math.floor(math.log10(min(r["total_expense"] for r in latest)))
    hi_d = math.ceil(math.log10(max(r["total_expense"] for r in latest)))

    def X2(e): return PL + (W - PL - PR) * (math.log10(e) - lo_d) / (hi_d - lo_d)

    def Y2(s): return PT2 + (H2 - PT2 - PB2) * (1 - s)
    grid2 = "".join(
        f'<line x1="{PL}" y1="{Y2(p):.1f}" x2="{W-PR}" y2="{Y2(p):.1f}" '
        f'stroke="var(--grid)"/>'
        f'<text x="{PL-8}" y="{Y2(p)+4:.1f}" text-anchor="end">{p:.0%}</text>'
        for p in (0, .25, .5, .75, 1))
    xlab2 = "".join(
        f'<text x="{X2(10**u):.1f}" y="{H2-16}" text-anchor="middle">'
        f'{_money(10**u)}</text>'
        for u in range(lo_d, hi_d + 1))
    pts2 = "".join(
        f'<circle cx="{X2(r["total_expense"]):.1f}" cy="{Y2(r["top20_share"]):.1f}" '
        f'r="4.5" fill="{"var(--muted)" if r["n_payees"] <= 20 else "var(--s1)"}" '
        f'stroke="var(--surface)" stroke-width="2" '
        f'data-h="{html.escape(r["agency_name"])} " '
        f'data-b="FY{r["fiscal_year"]}: top-20 payee share {r["top20_share"]:.1%} '
        f'across {r["n_payees"]:,} payees; {_money(r["total_expense"])} recorded '
        f'expense"/>'
        for r in latest)
    svg2 = (f'<svg viewBox="0 0 {W} {H2}" role="img" aria-label="Top-20 payee '
            f'share versus total recorded expense, FY{fy_hi}">'
            f'{grid2}{pts2}{xlab2}</svg>')

    # ============== table: most concentrated at scale ==============
    eligible = sorted((r for r in latest if r["n_payees"] >= MIN_PAYEES_FOR_TABLE),
                      key=lambda r: -r["top20_share"])[:8]
    tr = "".join(
        f"<tr><td>{html.escape(r['agency_name'])}</td>"
        f"<td class='num'>{r['top20_share']:.1%}</td>"
        f"<td class='num'>{r['n_payees']:,}</td>"
        f"<td class='num'>${r['total_expense']:,.0f}</td></tr>"
        for r in eligible)
    table = (
        '<table><thead><tr><th>agency (as recorded)</th>'
        '<th class="num">top-20 payee share</th><th class="num">payees</th>'
        f'<th class="num">FY{fy_hi} recorded expense</th></tr></thead>'
        f'<tbody>{tr}</tbody></table>')

    script = """
var tip=document.getElementById('tip');
document.querySelectorAll('[data-h]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent='';
    var v=document.createElement('strong');
    v.textContent=el.dataset.h;
    tip.appendChild(v);
    tip.appendChild(document.createTextNode(el.dataset.b));
    tip.style.display='block';
    tip.style.left=Math.min(ev.clientX+14,innerWidth-320)+'px';
    tip.style.top=(ev.clientY+14)+'px';
  });
  el.addEventListener('pointerleave',function(){tip.style.display='none';});
});
"""

    lede = (
        f"For each of {n_ag} Oregon agencies in FY{fy_hi}, the corpus asked one "
        f"question of the recorded expenditure mirror: what share of the agency's "
        f"total recorded spending went to its 20 largest payee strings? The "
        f"median answer is <b>{med:.0%}</b> — and every one of these figures is a "
        f"<b>floor</b>, because payee strings are not de-duplicated upstream. The "
        f"spread runs from {low['top20_share']:.0%} "
        f"({html.escape(low['agency_name'])}, {low['n_payees']:,} payees) to the "
        f"{len(small)} small agencies whose 20-or-fewer payees make 100% an "
        f"arithmetic certainty rather than a finding.")

    caveats = (
        f"<p><b>The export's own note, carried verbatim:</b> "
        f"{html.escape(note)}</p>"
        f"<p><b>How to read the numbers.</b> 'Payees' are distinct payee "
        f"<i>strings</i> in the state's expenditure records, not de-duplicated "
        f"vendors — one vendor under three spellings counts three times, which "
        f"can only push a top-20 share <i>down</i>; that is why every share is a "
        f"floor. An agency with 20 or fewer payee strings shows 100% by "
        f"construction; the most-concentrated table therefore admits only "
        f"agencies with at least {MIN_PAYEES_FOR_TABLE} payees, a threshold "
        f"chosen here and stated here. Recorded expense is the agency's total "
        f"spending from every source and implies nothing about appropriations. "
        f"Coverage: {d['n_rows']} agency-year rows, FY{fy_lo}–FY{fy_hi}; the "
        f"charts show FY{fy_hi} only. Concentration is a shape, not a verdict — "
        f"a pass-through or grant-making agency is concentrated by design.</p>")

    body = (
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Top-20 '
        f'payee share of recorded spending — one dot per agency, FY{fy_hi}</h2>'
        f'{svg1}{legend1}{chart_note}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">'
        f'Concentration vs scale — share against total recorded expense '
        f'(log scale), FY{fy_hi}</h2>{svg2}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Most '
        f'concentrated at scale — the eight highest top-20 shares among agencies '
        f'with at least {MIN_PAYEES_FOR_TABLE} payees, FY{fy_hi}</h2>{table}</div>')

    page = viz.chart_page(
        title=f"An Oregon agency's 20 largest payees absorb a median {med:.0%} "
              f"of its recorded spending — and that is a floor",
        eyebrow="oregon-stories · from the oregon-budget corpus",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"top-20 payees absorb a median {med:.0%} of an agency's recorded "
             f"spending (FY{fy_hi}) — a floor, not an estimate")
    return SLUG, claim, page

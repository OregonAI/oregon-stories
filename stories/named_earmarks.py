"""Story: the line items — where Oregon's budget bills name a specific recipient
and a specific amount, row by row.

Source: oregon-budget's generated line-items export (_meta/line-items.json): every
row of every bill's 'Line items' table, with the bill's extraction_status riding
along. Nothing else on the platform shows this layer today. The export's own rule
is this page's rule: NEVER sum across extraction statuses — the overlap between
items and stated totals differs per status, so any cross-status figure shown here
is labeled nominal and broken out per status beside it. Every parse is machine
work (human_reviewed: false on all rows); the verbatim source line rides with each
row, and MISMATCH rows exist because the arithmetic check works.
"""
from __future__ import annotations

import html
import json
import math
import statistics
from collections import Counter, defaultdict

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

SLUG = "named-earmarks"

BILL_URL = "https://github.com/OregonAI/oregon-budget/blob/main/bills/{}.md"

# Decade-boundary labels for the log-scale amount axis: 10^0 .. 10^10.
POW_LABELS = ["$1", "$10", "$100", "$1K", "$10K", "$100K",
              "$1M", "$10M", "$100M", "$1B", "$10B"]


def _money(n: float) -> str:
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= div:
            s = f"{n / div:.1f}".removesuffix(".0")
            return f"${s}{suf}"
    return f"${n:,.0f}"


def build() -> tuple[str, str, str]:
    d = json.loads(fetch(f"{RAW}/oregon-budget/main/_meta/line-items.json",
                         "oregon-budget line-items export (generated)"))
    items = d["items"]
    n_items = d["n_items"]
    n_bills = d["n_bills_with_items"]
    note = d["note"]

    # ---- per-session counts (counts are safe to aggregate; sums are not) ----
    per_session = Counter(r["session"] for r in items)
    sessions = sorted(per_session)          # "2017r1" < "2021r1" < "2021s2": chronological
    n_sessions = len(sessions)
    first_s, last_s = sessions[0], sessions[-1]

    # ---- amounts ----
    amounts = [r["amount_usd"] for r in items if r["amount_usd"] is not None]
    n_null = n_items - len(amounts)
    median_amt = statistics.median(amounts)
    nominal_sum = sum(amounts)

    # ---- per-status breakdown (the only legitimate frame for sums) ----
    per_status = defaultdict(lambda: [0, 0])     # status -> [count, machine-parsed sum]
    for r in items:
        s = per_status[r["extraction_status"]]
        s[0] += 1
        if r["amount_usd"] is not None:
            s[1] += r["amount_usd"]
    status_order = ["reconciled", "partly-reconciled",
                    "items-without-stated-total", "MISMATCH"]
    status_order += [s for s in sorted(per_status) if s not in status_order]
    status_gloss = {
        "reconciled": "parsed items sum to the bill's stated total",
        "partly-reconciled": "some, not all, items reconcile to a stated total",
        "items-without-stated-total": "the bill states no total to check against",
        "MISMATCH": "parsed items disagree with the stated total — the arithmetic "
                    "check firing out loud instead of failing silently",
    }

    # ================= chart 1: line items per session (bar) =================
    W, H, PL, PR, PT, PB = 880, 300, 54, 16, 20, 40
    ymax = math.ceil(max(per_session.values()) / 100) * 100
    band = (W - PL - PR) / n_sessions
    bw = min(24.0, band * 0.6)

    def Y1(v): return PT + (H - PT - PB) * (1 - v / ymax)
    grid1 = "".join(
        f'<line x1="{PL}" y1="{Y1(v):.1f}" x2="{W-PR}" y2="{Y1(v):.1f}" '
        f'stroke="var(--grid)"/>'
        f'<text x="{PL-8}" y="{Y1(v)+4:.1f}" text-anchor="end">{v:,}</text>'
        for v in range(0, ymax + 1, 100))
    bars1, xlab1, caps1 = [], [], []
    max_session = max(sessions, key=lambda s: per_session[s])
    for i, s in enumerate(sessions):
        v = per_session[s]
        cx = PL + band * (i + 0.5)
        bars1.append(
            f'<rect x="{cx-bw/2:.1f}" y="{Y1(v):.1f}" width="{bw:.1f}" '
            f'height="{Y1(0)-Y1(v):.1f}" rx="3" fill="var(--s1)" '
            f'data-h="{v:,} line items" data-b="named in {html.escape(s)} '
            f'budget bills"/>')
        xlab1.append(f'<text x="{cx:.1f}" y="{H-16}" text-anchor="middle">'
                     f'{html.escape(s)}</text>')
        if s in (first_s, max_session):     # selective direct labels: first + peak
            caps1.append(f'<text class="val" x="{cx:.1f}" y="{Y1(v)-6:.1f}" '
                         f'text-anchor="middle">{v:,}</text>')
    svg1 = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Named line items '
            f'per legislative session">{grid1}{"".join(bars1)}{"".join(caps1)}'
            f'{"".join(xlab1)}</svg>')

    # ============ chart 2: amount distribution on a log-10 axis =============
    H2, PT2, PB2 = 260, 24, 40
    decades = Counter(int(math.floor(math.log10(a))) for a in amounts if a > 0)
    n_zero_or_neg = sum(1 for a in amounts if a <= 0)
    LO, HI = 0, 10                      # $1 .. $10B boundaries

    def X2(u): return PL + (W - PL - PR) * (u - LO) / (HI - LO)
    ymax2 = math.ceil(max(decades.values()) / 200) * 200

    def Y2(v): return PT2 + (H2 - PT2 - PB2) * (1 - v / ymax2)
    grid2 = "".join(
        f'<line x1="{PL}" y1="{Y2(v):.1f}" x2="{W-PR}" y2="{Y2(v):.1f}" '
        f'stroke="var(--grid)"/>'
        f'<text x="{PL-8}" y="{Y2(v)+4:.1f}" text-anchor="end">{v:,}</text>'
        for v in range(0, ymax2 + 1, 200))
    bars2 = "".join(
        f'<rect x="{X2(dec)+1.5:.1f}" y="{Y2(c):.1f}" '
        f'width="{X2(dec+1)-X2(dec)-3:.1f}" height="{Y2(0)-Y2(c):.1f}" rx="3" '
        f'fill="var(--s1)" data-h="{c:,} line items" '
        f'data-b="with parsed amounts of {POW_LABELS[dec]} to just under '
        f'{POW_LABELS[dec+1]}"/>'
        for dec, c in sorted(decades.items()))
    xlab2 = "".join(
        f'<text x="{X2(u):.1f}" y="{H2-16}" text-anchor="middle">{POW_LABELS[u]}</text>'
        for u in range(LO, HI + 1))
    mx = X2(math.log10(median_amt))
    median_mark = (
        f'<line x1="{mx:.1f}" y1="{PT2-6}" x2="{mx:.1f}" y2="{H2-PB2}" '
        f'stroke="var(--ink2)" stroke-width="1"/>'
        f'<text class="val" x="{mx+6:.1f}" y="{PT2+4}">median '
        f'{_money(median_amt)}</text>')
    svg2 = (f'<svg viewBox="0 0 {W} {H2}" role="img" aria-label="Distribution of '
            f'line-item amounts on a log scale">{grid2}{bars2}{median_mark}'
            f'{xlab2}</svg>')

    # ================= per-status breakdown panel =================
    st_rows = "".join(
        f"<tr><td>{html.escape(s)}</td>"
        f"<td class='num'>{per_status[s][0]:,}</td>"
        f"<td class='num'>${per_status[s][1]:,}</td>"
        f"<td>{html.escape(status_gloss.get(s, ''))}</td></tr>"
        for s in status_order if s in per_status)
    st_table = (
        '<table><thead><tr><th>extraction status</th><th class="num">items</th>'
        '<th class="num">machine-parsed amounts</th><th>what the status means</th>'
        f'</tr></thead><tbody>{st_rows}</tbody></table>')

    # ================= sample of the largest =================
    top = sorted((r for r in items if r["amount_usd"] is not None),
                 key=lambda r: -r["amount_usd"])[:12]
    tr = []
    for r in top:
        bill = r["bill_id"]
        short = bill.rsplit("-", 1)[-1]
        purpose = r["purpose"] or ""
        clamped = purpose if len(purpose) <= 90 else purpose[:90] + "…"
        tr.append(
            f"<tr><td class='num'>{html.escape(r['session'])}</td>"
            f"<td>{html.escape(r['appropriated_to'])}</td>"
            f"<td class='num'>${r['amount_usd']:,}</td>"
            f"<td>{html.escape(clamped)}</td>"
            f"<td><a href='{html.escape(BILL_URL.format(bill))}'>"
            f"{html.escape(short)}</a></td></tr>")
    top_table = (
        '<table><thead><tr><th class="num">session</th><th>appropriated to</th>'
        '<th class="num">amount</th><th>purpose, verbatim from the bill</th>'
        f'<th>bill</th></tr></thead><tbody>{"".join(tr)}</tbody></table>')

    script = """
var tip=document.getElementById('tip');
document.querySelectorAll('[data-h]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent='';
    var v=document.createElement('strong');
    v.textContent=el.dataset.h+' ';
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
        f"When an Oregon budget bill says “$6,000,000 to the City of Eugene for "
        f"water and sewer infrastructure improvements along Crow Road”, that is a "
        f"line item: a named recipient and a stated amount, in the bill's own "
        f"words. The corpus extracted <b>{n_items:,} of them across {n_bills} "
        f"bills and {n_sessions} sessions</b> ({html.escape(first_s)} through "
        f"{html.escape(last_s)}) — from {per_session[first_s]} items in "
        f"{html.escape(first_s)} to {per_session[max_session]} in "
        f"{html.escape(max_session)}. Machine-parsed amounts total "
        f"{_money(nominal_sum)} — a <b>nominal sum across extraction statuses, "
        f"shown separately below</b>, because the export's own rule is that "
        f"cross-status sums double-count. Every parse is machine work "
        f"(<b>human_reviewed: false on all {n_items:,} rows</b>); the verbatim "
        f"source line rides with each row.")

    caveats = (
        f"<p><b>The export's own note, carried verbatim:</b> "
        f"{html.escape(note)}</p>"
        f"<p><b>What this page did and did not do.</b> Counts per session are "
        f"counts, never dollar aggregations. The {_money(nominal_sum)} headline "
        f"is the nominal sum of machine-parsed amounts across statuses, with the "
        f"per-status count/sum breakdown in its own panel — quote those, not the "
        f"headline. Recipient names live inside the free-text purpose field; this "
        f"page deliberately does <b>not</b> extract entities from it (that would "
        f"risk fabricating recipients), so the largest-items table shows the "
        f"purpose verbatim and links each row to its source bill. {n_null} row(s) "
        f"carry no machine-parsable amount and are absent from the distribution "
        f"and the nominal sum"
        + (f"; {n_zero_or_neg} parsed amount(s) at or below $0 are outside the "
           f"log-scale chart" if n_zero_or_neg else "")
        + ". Session coverage reflects what the corpus has extracted, not "
          "necessarily every session the Legislature held.</p>")

    body = (
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Named line '
        f'items per session</h2>{svg1}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">How big is '
        f'a line item? Parsed amounts on a log scale '
        f'({len(amounts):,} of {n_items:,} rows)</h2>{svg2}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Per-status '
        f'breakdown — the only frame in which sums are honest</h2>{st_table}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">A sample of '
        f'the largest — twelve biggest parsed amounts, purpose verbatim</h2>'
        f'{top_table}</div>')

    page = viz.chart_page(
        title=f"{n_items:,} times Oregon's budget bills named a recipient and an "
              f"amount, line by line",
        eyebrow="oregon-stories · from the oregon-budget corpus",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"{n_items:,} legislature-named line items across {n_sessions} "
             f"sessions — {_money(nominal_sum)} nominal, none human-reviewed")
    return SLUG, claim, page

"""Story: rules whose text reads least like the statute they cite as their legal
authority — a screening signal, handed to the human triage queue.

Renders the committed cache data/semantic/authority.json. THE CONFOUND LEADS: a broad
enabling statute ("the board may adopt rules...") naturally reads nothing like the
specific rules it authorizes, and that is normal, lawful, and common — which is why
this page presents a screening DISTRIBUTION and a review queue, and never a finding.
"""
from __future__ import annotations

import json
from pathlib import Path

from corpus_toolkit import viz
from data_sources import FETCHED

SLUG = "far-from-their-authority"
CACHE = Path(__file__).resolve().parent.parent / "data" / "semantic" / "authority.json"
GH = "https://github.com/OregonAI"


def build() -> tuple[str, str, str]:
    d = json.loads(CACHE.read_text())
    FETCHED.append({"label": "committed semantic cache (authority.json; fingerprint inside)",
                    "url": f"{GH}/oregon-stories/blob/main/data/semantic/authority.json",
                    "sha256": d["erf_fingerprint"]})
    q = d["quartiles"]  # p5, p25, p50, p75, p95

    W, H = 700, 70
    def X(v): return (v - 0.3) / 0.7 * W
    box = (f'<svg viewBox="-10 0 {W+80} {H}" role="img" aria-label="Distribution of '
           f'rule-to-authority similarity">'
           f'<line x1="{X(q[0]):.0f}" y1="35" x2="{X(q[4]):.0f}" y2="35" '
           f'stroke="var(--axis)" stroke-width="2"/>'
           f'<rect x="{X(q[1]):.0f}" y="20" width="{X(q[3])-X(q[1]):.0f}" height="30" '
           f'rx="4" fill="var(--s1)" opacity="0.35"/>'
           f'<line x1="{X(q[2]):.0f}" y1="16" x2="{X(q[2]):.0f}" y2="54" '
           f'stroke="var(--s1)" stroke-width="3"/>'
           + "".join(f'<text x="{X(v):.0f}" y="66" text-anchor="middle">{v:.2f}</text>'
                     for v in q)
           + f'<text x="{X(q[2]):.0f}" y="10" text-anchor="middle" class="val">median '
             f'{q[2]:.2f}</text></svg>')

    rows = "".join(
        f'<tr><td><a href="{GH}/executive-regulatory-frameworks/blob/main/rules/'
        f'{r["rule"].split("-")[1]}/{r["rule"].split("-")[2]}/{r["rule"]}.md">'
        f'{r["rule"].removeprefix("oar-")}</a></td>'
        f'<td><a href="{GH}/executive-regulatory-frameworks/blob/main/statutes/'
        f'{r["statute"]}.md">{r["statute"].removeprefix("ors-").upper()}</a></td>'
        f'<td class="num">{r["cos"]:.3f}</td>'
        f'<td class="num">{r.get("n_authorities") or "—"}</td></tr>'
        for r in d["farthest"][:30])
    table = ('<table><thead><tr><th>rule</th><th>its cited authority (ORS)</th>'
             '<th class="num">cosine</th><th class="num">authorities cited</th>'
             '</tr></thead><tbody>' + rows + "</tbody></table>")

    lede = (f"For {d['n_rules_scored']:,} rules, the semantic index scored how much "
            f"the rule's text resembles the statute it cites as its legal authority. "
            f"Most sit comfortably (median {q[2]:.2f}; the closest pairs, like a "
            f"disability-discrimination rule against ORS chapter 659A, reach "
            f"{d['nearest'][-1]['cos']:.2f}). The tail is the interesting part — and "
            f"the confound is stated before the tail is: <b>a broad enabling statute "
            f"naturally reads nothing like the specific rules it authorizes</b>. "
            f"That is lawful and common. So the bottom of this distribution is a "
            f"REVIEW QUEUE, ordered for human attention, not a list of problems.")

    caveats = (
        "<p><b>Low similarity is not wrong authority.</b> The dominant, innocent "
        "explanation — general delegations ('the department may adopt rules…') — "
        "probably accounts for most of the tail, and only reading the pair tells you "
        "which is which. That reading has a home: the conflict-candidate triage "
        "workflow in executive-regulatory-frameworks, where a human verdict is "
        "recorded per pair and carried forward. Scores are cosine over per-document "
        f"mean embeddings ({d['model']}); each rule is scored against the FIRST "
        "statute in its authority line (rules citing many authorities are marked). "
        "Nothing on this page is served by the platform's resolve/authority tools — "
        "it is a screening artifact, cached with its fingerprint.</p>")

    body = (f'<div class="panel"><h2 style="font-size:14px;margin:0 0 4px">How similar '
            f'are rules to their cited authority? (5th/25th/50th/75th/95th '
            f'percentiles)</h2>{box}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">The thirty '
            f'farthest pairs — the front of the review queue</h2>{table}</div>')

    page = viz.chart_page(
        title="Rules farthest in meaning from their cited authority — a screening "
              "queue, not a verdict list",
        eyebrow="oregon-stories · semantic index × authority citations",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=FETCHED, generated=d["generated"])
    return SLUG, (f"{d['n_rules_scored']:,} rule↔authority pairs scored by meaning; "
                  f"the far tail becomes a human review queue"), page

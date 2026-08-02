"""Story: what audit findings are ABOUT, versus what they cite — the platform's two
unique assets (a citation graph and a semantic index) read against each other.

Renders the committed cache data/semantic/bridge.json (built where the embedding
artifacts live, per the topic-map committed-cache precedent; provenance and artifact
fingerprints ride the cache and print in the footer).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from corpus_toolkit import viz
from data_sources import FETCHED

SLUG = "found-by-meaning"
CACHE = Path(__file__).resolve().parent.parent / "data" / "semantic" / "bridge.json"
GH = "https://github.com/OregonAI"


def build() -> tuple[str, str, str]:
    d = json.loads(CACHE.read_text())
    FETCHED.append({"label": "committed semantic cache (bridge.json; fingerprints inside)",
                    "url": f"{GH}/oregon-stories/blob/main/data/semantic/bridge.json",
                    "sha256": d["erf_fingerprint"]})
    reports = d["reports"]
    top5 = [(h, r) for r in reports for h in r["top"][:5]]
    n_ch = sum(1 for h, _ in top5 if h["chapter_cited"])
    pct = n_ch / len(top5)

    # The showcase: reports whose top semantic matches are strong AND uncited.
    show = sorted(
        (r for r in reports if r["n_cited_edges"] >= 3),
        key=lambda r: -sum(h["score"] for h in r["top"][:3]
                           if not h["chapter_cited"]))[:10]
    rows = []
    for r in show:
        hits = "".join(
            f'<div style="font-size:12.5px">'
            f'<a href="{GH}/executive-regulatory-frameworks/blob/main/'
            f'{"rules/" + h["id"].split("-")[1] + "/" + h["id"].split("-")[2] + "/" if h["id"].startswith("oar-") else "statutes/"}'
            f'{h["id"]}.md">{h["id"]}</a> '
            f'<span style="color:var(--muted)">cos {h["score"]:.2f}</span> '
            f'{"· cited" if h["chapter_cited"] else "· <b>not cited</b>"}</div>'
            for h in r["top"][:4])
        rows.append(f'<tr><td><a href="{GH}/oregon-audits/blob/main/reports/'
                    f'{r["report"]}.md">{r["report"]}</a><br>'
                    f'<small>{r["n_cited_edges"]} citation edges</small></td>'
                    f'<td>{hits}</td></tr>')
    table = ('<table><thead><tr><th>audit report</th><th>nearest law by meaning '
             '(top 4)</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")

    W, BARH = 700, 40
    w1 = W * pct
    bar = (f'<svg viewBox="0 0 {W+160} {BARH}" role="img" aria-label="Share of '
           f'semantic matches that are cited">'
           f'<rect x="0" y="8" width="{w1:.0f}" height="22" rx="3" fill="var(--s1)"/>'
           f'<rect x="{w1+2:.0f}" y="8" width="{W-w1-2:.0f}" height="22" rx="3" '
           f'fill="var(--s1)" opacity="0.25"/>'
           f'<text class="val" x="{W+8}" y="24">{pct:.0%} cited</text></svg>')

    lede = (f"For each of {d['n_reports']} audit reports, the semantic index found the "
            f"statutes and rules nearest in MEANING to the report's own text. Only "
            f"<b>{pct:.0%}</b> of those top matches are law the report cites, even at "
            f"chapter level. The rest is the report's semantic neighborhood — "
            f"regulation the audit is functionally about, reachable by meaning when "
            f"citations stop short. Only a platform holding both a citation graph and "
            f"an embedding of the whole rulebook can draw this comparison.")

    caveats = (
        "<p><b>Semantic nearness is not a legal or professional claim.</b> That a rule "
        "reads like a finding does not mean the auditor examined, should have cited, "
        "or overlooked it — auditors cite what their scope requires, and this page is "
        "a DISCOVERY AID for readers navigating from a finding to related regulation, "
        "not a critique of citation practice. Similarity is cosine over per-document "
        f"mean embeddings ({html.escape(d['model'])}); the cache records both corpora's "
        "artifact fingerprints and is rebuilt deliberately, not per-deploy. Matches "
        "are restricted to statutes and rules; 'cited' means the report's citation "
        "edges reach the same chapter.</p>")

    body = (f'<div class="panel"><h2 style="font-size:14px;margin:0 0 4px">Of every '
            f'report\'s five nearest laws by meaning, how many does it cite?</h2>{bar}'
            f'</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Ten reports '
            f'with the strongest uncited semantic neighbors</h2>{table}</div>')

    page = viz.chart_page(
        title=f"Audits reach {pct:.0%} of their own semantic neighborhood by citation "
              f"— meaning finds the rest",
        eyebrow="oregon-stories · semantic index × citation graph",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=FETCHED, generated=d["generated"])
    return SLUG, (f"only {pct:.0%} of audits' nearest-by-meaning law is cited — "
                  f"the semantic index finds what citations don't name"), page

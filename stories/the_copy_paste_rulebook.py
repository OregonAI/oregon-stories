"""Story: the copy-paste economy of Oregon regulation — rules that are near-verbatim
twins of rules in other agencies' chapters.

Renders the committed cache data/semantic/twins.json. The headline family is almost
certainly the Attorney General's model rules of procedure, which agencies adopt
near-verbatim — the mechanism is a feature of Oregon administrative law, and finding
it by embedding is the validation that the method works.
"""
from __future__ import annotations

import json
from pathlib import Path

from corpus_toolkit import viz
from data_sources import FETCHED

SLUG = "the-copy-paste-rulebook"
CACHE = Path(__file__).resolve().parent.parent / "data" / "semantic" / "twins.json"
GH = "https://github.com/OregonAI"


def rule_link(rid: str) -> str:
    _, ch, div, _ = rid.split("-", 3)
    return f"{GH}/executive-regulatory-frameworks/blob/main/rules/{ch}/{div}/{rid}.md"


def build() -> tuple[str, str, str]:
    d = json.loads(CACHE.read_text())
    FETCHED.append({"label": "committed semantic cache (twins.json; fingerprint inside)",
                    "url": f"{GH}/oregon-stories/blob/main/data/semantic/twins.json",
                    "sha256": d["erf_fingerprint"]})
    fams = d["families"]
    cross = [f for f in fams if f["cross_chapter"]]

    rows = []
    for f in cross[:12]:
        members = " · ".join(f'<a href="{rule_link(m)}">{m.removeprefix("oar-")}</a>'
                             for m in f["members"][:8])
        more = f" … +{f['n']-8}" if f["n"] > 8 else ""
        rows.append(f'<tr><td class="num">{f["n"]}</td>'
                    f'<td class="num">{len(f["chapters"])}</td>'
                    f'<td style="font-size:12.5px">{members}{more}</td></tr>')
    table = ('<table><thead><tr><th class="num">rules</th><th class="num">chapters'
             '</th><th>members</th></tr></thead><tbody>' + "".join(rows)
             + "</tbody></table>")

    big = cross[0] if cross else None
    lede = (f"At cosine ≥ {d['threshold']} — near-verbatim territory — "
            f"{d['n_rules_in_families']:,} of Oregon's {d['n_rules']:,} rules sit in "
            f"{d['n_families']} twin families, {d['n_cross_chapter_families']} of them "
            f"spanning more than one agency's chapter. The largest family stretches "
            f"across <b>{len(big['chapters'])} chapters</b> — one procedural text, "
            f"adopted again and again across the government. That is not plagiarism; "
            f"it is how Oregon administrative law is designed to work (agencies adopt "
            f"model rules), and the interesting part is the margins: where one "
            f"agency's copy quietly differs from the family.")

    caveats = (
        "<p><b>Twinship is textual, not legal:</b> two near-identical rules can have "
        "different legal force in their different contexts, and adopting model rules "
        "is standard, sanctioned practice — nothing here implies impropriety. "
        f"Similarity is cosine over per-document mean embeddings ({d['model']}), "
        f"threshold {d['threshold']}; a family is the transitive closure of pairs "
        "above it, so long chains can join texts that differ more end-to-end than "
        "any adjacent pair. Same-chapter families (numbering echoes within one "
        "agency) exist and are counted, but the table shows cross-chapter families — "
        "the ones where text traveled between agencies. The cache records the "
        "artifact fingerprint and rebuild method.</p>")

    body = (f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">The twelve '
            f'widest-travelling texts (cross-chapter families)</h2>{table}</div>')

    page = viz.chart_page(
        title=f"The copy-paste rulebook: {d['n_rules_in_families']:,} rules in "
              f"{d['n_families']} near-verbatim families",
        eyebrow="oregon-stories · semantic index over the whole OAR",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=FETCHED, generated=d["generated"])
    return SLUG, (f"{d['n_rules_in_families']:,} rules form {d['n_families']} "
                  f"near-verbatim families; the widest text spans "
                  f"{len(big['chapters'])} agencies' chapters"), page

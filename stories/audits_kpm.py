"""Story: audits and the agencies' own scorecards, read against each other by
meaning — with the method's validity check published before anything else.

Renders the committed cache data/semantic/audit_kpm.json (built by
tools/build_audit_kpm_cache.py from the two corpora's embedding artifacts;
fingerprints ride the cache and print in the footer). The page leads with the
recovery rate — the semantic index blindly reconstructing an agency join it was
never given — because that number is the reason to trust the neighborhood reading
at all. Everything after it is a candidate surfacer, never a finding.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from corpus_toolkit import viz
from data_sources import FETCHED

SLUG = "audits-and-the-scorecards"
CACHE = Path(__file__).resolve().parent.parent / "data" / "semantic" / "audit_kpm.json"
GH = "https://github.com/OregonAI"


def build() -> tuple[str, str, str]:
    d = json.loads(CACHE.read_text())
    FETCHED.append({"label": "committed semantic cache (audit_kpm.json; fingerprints inside)",
                    "url": f"{GH}/oregon-stories/blob/main/data/semantic/audit_kpm.json",
                    "sha256": d["audits_fingerprint"]})
    rec = d["recovery"]
    rate = rec["rate"]
    chance = 1 / rec["n_kpm_agency_slugs"]
    pairs = d["pairs"]

    # ── the method check, drawn: recovery vs chance ─────────────────────────────
    W = 700
    w_rate, w_chance = W * rate, max(W * chance, 3)
    check = (
        f'<svg viewBox="0 0 {W+170} 92" role="img" aria-label="Same-agency recovery '
        f'rate versus chance">'
        f'<text x="0" y="16" style="font-size:12px;fill:var(--ink2)">nearest KPM report '
        f'belongs to the same agency</text>'
        f'<rect x="0" y="24" width="{w_rate:.0f}" height="20" rx="3" fill="var(--s1)"/>'
        f'<text class="val" x="{w_rate+8:.0f}" y="39">{rate:.0%} of '
        f'{rec["n_audits_slugged"]} audits</text>'
        f'<text x="0" y="68" style="font-size:12px;fill:var(--ink2)">chance, with '
        f'{rec["n_kpm_agency_slugs"]} agencies to pick from</text>'
        f'<rect x="0" y="74" width="{w_chance:.0f}" height="8" rx="2" fill="var(--s1)" '
        f'opacity="0.35"/>'
        f'<text class="val" x="{w_chance+8:.0f}" y="82">{chance:.1%}</text></svg>')

    # ── at-target beside the audit: the join the platform uniquely holds ────────
    judged = [p for p in pairs
              if p["at_target"] and p["at_target"]["judged"] >= 5]
    for p in judged:
        at = p["at_target"]
        p["_share"] = at["met"] / at["judged"]
    judged.sort(key=lambda p: p["_share"])
    show = judged[:12]
    rows = []
    for p in show:
        at = p["at_target"]
        rows.append(
            f'<tr><td><a href="{GH}/oregon-audits/blob/main/reports/'
            f'{p["audit_id"]}.md">{html.escape(p["audit_title"][:70])}</a><br>'
            f'<small>{html.escape(p["audit_type"] or "")} · {p["report_date"][:4]}</small></td>'
            f'<td><a href="{GH}/oregon-kpm/blob/main/reports/{p["kpm_doc"]}.md">'
            f'{html.escape(p["kpm_doc"][:40])}</a><br>'
            f'<small>cos {p["score"]:.2f} · reporting year {p["kpm_reporting_year"]}</small></td>'
            f'<td class="num">{p["_share"]:.0%}<br><small>{at["met"]} of {at["judged"]} '
            f'judged<br>{at["no_direction"]} state no direction</small></td></tr>')
    table = ('<table><thead><tr><th>audit report</th><th>nearest same-agency scorecard '
             '(by meaning)</th><th class="num">measures at target that year</th></tr>'
             '</thead><tbody>' + "".join(rows) + "</tbody></table>")

    lede = (
        f"Two corpora describe the same agencies: the auditors' reports, and the "
        f"agencies' own Annual Performance Progress Reports. Read purely by meaning — "
        f"no metadata, no names — each audit's nearest scorecard belongs to the "
        f"<b>same agency {rate:.0%} of the time</b>, against a {chance:.1%} chance. "
        f"That recovery rate is the method check. What it buys: every audit can be "
        f"laid beside the scorecard it most resembles, and that scorecard's own "
        f"at-target share for the year — the table below shows the twelve pairings "
        f"where the agency's self-reported performance was weakest.")

    caveats = (
        "<p><b>Proximity surfaces candidates, never findings.</b> An audit reading "
        "like a scorecard does not mean the audit was prompted by those measures or "
        "should have addressed them — both are one agency writing about its own "
        "programs, so agency-level overlap is the null hypothesis, not the result; "
        f"the {rate:.0%} is a recovery rate, not accuracy. At-target shares use each "
        "measure's own stated trend direction (measures stating none are counted, "
        "not judged) and targets are agency-set — the same caveats as the KPM story. "
        f"Counted out: {d['excluded']['audits_without_slug']} audits carry no registry "
        f"slug; {len(d['excluded']['audit_agencies_without_kpm'])} audited agencies "
        f"have no KPM reports at all. Similarity is cosine over per-document mean "
        f"embeddings ({html.escape(d['model'])}); the cache records both artifact "
        "fingerprints and is rebuilt deliberately, not per-deploy.</p>")

    body = (
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 4px">The method '
        f'check: can meaning alone find the right agency?</h2>{check}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Audits beside '
        f'the weakest scorecards — {len(judged)} pairs with ≥5 judged measures, '
        f'twelve lowest shown</h2>{table}</div>')

    page = viz.chart_page(
        title=f"By meaning alone, {rate:.0%} of audits land on their own agency's "
              f"scorecard",
        eyebrow="oregon-stories · oregon-audits × oregon-kpm, joined by meaning",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=FETCHED, generated=d["generated"])
    return SLUG, (f"{rate:.0%} of audits land on their own agency's scorecard by "
                  f"meaning alone (chance: {chance:.1%}) — and the scorecards they "
                  f"land on can be read beside them"), page

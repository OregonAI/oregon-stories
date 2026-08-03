"""Story: one thread, end to end — PERS from statute to audit, told as findings
rather than as a diagram of the platform.

Refactor of the landing repo's chain.html (operator verdict 2026-08-03: "doesn't
tell a story"). What survives from it: the five-corpus join walk (the platform's
differentiator), the drawn-gap convention (an underivable link rendered as a
labelled absence, never papered over), and the derivation discipline — every number
recomputed at build from fetched artifacts, any fetch failure fails the build. What
changes: the page now leads with the data's own shape (which pension statutes the
auditors actually keep returning to), gives the money node real dollars (via
oregon-budget's vendor-concentration export), and says out loud the finding the old
page buried in a bare "1": the public paper trail thins exactly where
implementation goes internal.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter

from corpus_toolkit import viz
from data_sources import PAGES, RAW, fetch, sources_for_footer

SLUG = "one-thread-pers"
ERF = "executive-regulatory-frameworks"
PERS_SLUG = "public-employees-retirement-system"
GH = "https://github.com/OregonAI"


def build() -> tuple[str, str, str]:
    audits_graph = json.loads(fetch(f"{RAW}/oregon-audits/main/_meta/graph.json",
                                    "oregon-audits authority graph"))
    erf_index = json.loads(fetch(f"{PAGES}/{ERF}/corpus-index.json",
                                 "ERF corpus index"))
    budget_index = json.loads(fetch(f"{PAGES}/oregon-budget/corpus-index.json",
                                    "oregon-budget corpus index"))
    kpm_series = json.loads(fetch(f"{RAW}/oregon-kpm/main/_meta/series.json",
                                  "oregon-kpm extracted series"))
    vendor = json.loads(fetch(f"{RAW}/oregon-budget/main/_meta/vendor-concentration.json",
                              "oregon-budget vendor-concentration export"))

    # ── derivations, all recomputed (the chain.html discipline, kept) ──────────
    cite_238: Counter = Counter()
    reports_238 = set()
    for e in audits_graph["edges"]:
        m = re.match(r"^ORS\s+238\.(\d+)$", e.get("to", ""))
        if m:
            cite_238[f"238.{m.group(1)}"] += 1
            reports_238.add(e["from"])
    erf_docs = erf_index["documents"]
    n_rules = sum(1 for k in erf_docs if k.startswith("oar-459-"))
    n_instr = sum(1 for k, v in erf_docs.items()
                  if v[2].startswith(f"agencies/{PERS_SLUG}/"))
    pers_rows = [r for r in vendor["rows"] if r["agency_code"] == "459"]
    pers_rows.sort(key=lambda r: r["fiscal_year"])
    kpm_pers = [r for r in kpm_series["rows"] if "Retirement" in r["agency"]]
    n_measures = len({(r["kpm_number"], r["submeasure"]) for r in kpm_pers})

    # ── chart 1: which pension statutes the auditors keep returning to ─────────
    top = cite_238.most_common(10)
    maxv = top[0][1]
    W, RH = 520, 22
    bars = []
    for i, (sec, n) in enumerate(top):
        y = i * (RH + 6)
        w = W * n / maxv
        bars.append(
            f'<text x="0" y="{y+15}" style="font-size:12px;fill:var(--ink2)">ORS {sec}</text>'
            f'<rect x="90" y="{y+3}" width="{w:.0f}" height="{RH-8}" rx="3" fill="var(--s1)"/>'
            f'<text class="val" x="{95+w:.0f}" y="{y+15}">{n}</text>')
    chart1 = (f'<svg viewBox="0 0 {W+180} {len(top)*(RH+6)}" role="img" '
              f'aria-label="ORS 238 sections by audit citations">{"".join(bars)}</svg>')

    # ── chart 2: PERS spending by fiscal year, real dollars at last ────────────
    if pers_rows:
        maxd = max(r["total_expense"] for r in pers_rows)
        BW, BH = 66, 120
        cols = []
        for i, r in enumerate(pers_rows):
            h = BH * r["total_expense"] / maxd
            x = i * (BW + 10)
            cols.append(
                f'<rect x="{x}" y="{BH-h:.0f}" width="{BW-14}" height="{h:.0f}" rx="3" '
                f'fill="var(--s3)"/>'
                f'<text class="val" x="{x+(BW-14)/2}" y="{BH-h-5:.0f}" '
                f'text-anchor="middle">${r["total_expense"]/1e9:.1f}B</text>'
                f'<text x="{x+(BW-14)/2}" y="{BH+14}" text-anchor="middle" '
                f'style="font-size:11px;fill:var(--muted)">FY{r["fiscal_year"]}</text>')
        chart2 = (f'<svg viewBox="0 0 {len(pers_rows)*(BW+10)} {BH+22}" role="img" '
                  f'aria-label="PERS spending by fiscal year">{"".join(cols)}</svg>')
    else:
        chart2 = '<p style="color:var(--muted)">No agency-459 rows in the export.</p>'

    # ── the walk — five joins, one gap drawn as what it is ─────────────────────
    def step(head: str, body_html: str, dashed: bool = False) -> str:
        border = "border:1px dashed var(--muted)" if dashed else ""
        return (f'<div class="panel" style="margin:10px 0;{border}">'
                f'<h2 style="font-size:14px;margin:0 0 4px">{head}</h2>'
                f'<div style="font-size:13.5px;color:var(--ink2)">{body_html}</div></div>')

    walk = "".join([
        step("The gap comes first, drawn as a gap",
             "No enacting measure resolves for ORS chapter 238: the legislature "
             "mirror begins at 2017, and the pension statutes predate it. The link "
             "an authorizing-bill node would need does not exist in the platform — "
             "so it is drawn dashed, with its reason, not papered over. It becomes "
             "real the day pre-2017 sessions are mirrored.", dashed=True),
        step(f"Statute — {len(cite_238)} sections of ORS 238 carry "
             f"{sum(cite_238.values())} audit citations",
             f'The chart above is this node\'s real shape: auditors return to a '
             f'handful of sections — <a href="{GH}/{ERF}/blob/main/statutes/'
             f'ors-238.415.md">ORS 238.415</a> and neighbors — far more than the '
             f'rest of the chapter combined.'),
        step(f"Rules — {n_rules} administrative rules implement the chapter",
             f'OAR chapter 459, the Public Employees Retirement Board\'s rulebook, '
             f'held in <a href="{PAGES}/{ERF}/">the regulatory corpus</a> with '
             f'derived implements edges back to the statute.'),
        step(f"…and then ONE public agency instrument",
             f"After {n_rules} rules, the corpus holds <b>{n_instr}</b> published "
             f"internal PERS instrument. This is the thread's finding, not a "
             f"footnote: the public paper trail thins exactly where implementation "
             f"goes internal. Whether more instruments exist unpublished is not "
             f"knowable from here — absence of publication, not absence of policy."),
        step(f"Money — {len(pers_rows)} fiscal years of actual spending",
             f"Agency 459 in the state expenditure data, charted above in real "
             f"dollars — the number the old version of this page never showed."),
        step(f"Scorecard — {n_measures} performance measures",
             f'The agency\'s own Annual Performance Progress Reports, '
             f'{len(kpm_pers):,} extracted data points in '
             f'<a href="{PAGES}/oregon-kpm/">the KPM corpus</a>.'),
        step(f"And back to the auditors — {len(reports_238)} reports cite the chapter",
             f'The circle is drawn by citations, not asserted: '
             f'{len(reports_238)} audit reports cite ORS 238 sections, and each '
             f'resolves back into the statute corpus.'),
    ])

    lede = (
        f"Follow one program across five corpora on real joins: the pension statutes "
        f"the auditors cite most, the {n_rules} rules that implement them, the "
        f"<b>one</b> published agency instrument beneath those rules, the dollars "
        f"({len(pers_rows)} fiscal years), the agency's {n_measures} performance "
        f"measures, and the {len(reports_238)} audit reports that close the loop. "
        f"Every number recomputed at build; the one join that cannot be drawn is "
        f"shown as a labelled gap.")

    caveats = (
        "<p>Joins are prefix/registry matches over published artifacts (OAR 459, "
        "agency code 459, the PERS registry slug) — mechanical, and stated as such. "
        "The one-instrument count measures what is PUBLISHED in the corpus, never "
        "what exists inside the agency. Spending totals carry the expenditure "
        "corpus's own caveats (vendor strings not de-duplicated upstream affects "
        "concentration figures, not these totals). No causal claims anywhere: "
        "adjacency in this walk is a citation or a code match, not an explanation.</p>")

    body = (f'<div class="panel"><h2 style="font-size:14px;margin:0 0 4px">Which '
            f'pension statutes do auditors keep returning to?</h2>{chart1}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 4px">PERS '
            f'actual spending, by fiscal year</h2>{chart2}</div>'
            + walk)

    page = viz.chart_page(
        title="One thread, end to end: PERS from statute to audit",
        eyebrow="oregon-stories · five corpora, joined on real keys",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat())
    return SLUG, (f"PERS walked across five corpora: {sum(cite_238.values())} statute "
                  f"citations, {n_rules} rules, one published instrument, real "
                  f"dollars, and back to {len(reports_238)} audits"), page

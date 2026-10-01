"""Story: the audit mix, 2020->present — performance audits fell while financial held
flat. Port of oregon-audits#4's own src/build_audit_mix.py (oregon-stories#2): the
chart now renders here on corpus_toolkit.viz, reading the SAME published data artifact
that script reads — the mirrored report front matter under oregon-audits' reports/ —
rather than that corpus's own viz/audit-mix.html page. oregon-audits is data-only
going forward (2026-08-02 consolidation); the manifest entry flips to kind: local.

CHART DISCIPLINE (unchanged from the source script — this is a port, not a redesign):
  * Four charted series in fixed slot order; performance takes slot 1 because it IS the
    story. Three attestation-adjacent types and reports with no recorded type are
    table-only — seven charted lines would be noise, but nothing is hidden from the
    table.
  * Whichever year is the CURRENT calendar year at build time is drawn hollow with a
    dashed lead-in and an explicit annotation, because that year is necessarily
    in-progress — without the distinction the decline would read steeper than it is.
  * No causal language anywhere: the chart says what the mix did, not why.
"""
from __future__ import annotations

import collections
import datetime
import hashlib
import json

import yaml

import data_sources
from corpus_toolkit import viz
from data_sources import fetch, sources_for_footer

AUDITS = "oregon-audits"
GH = f"https://github.com/OregonAI/{AUDITS}"
API_REPORTS = f"https://api.github.com/repos/OregonAI/{AUDITS}/contents/reports"
RAW_REPORTS = f"https://raw.githubusercontent.com/OregonAI/{AUDITS}/main/reports"
SLUG = "audit-mix"

CHARTED = ("performance", "financial", "informational", "information technology")

W, H, PAD_L, PAD_R, PAD_T, PAD_B = 880, 360, 44, 150, 18, 34


def list_report_ids() -> list[str]:
    """The published report corpus's own index — every numbered report under
    reports/*.md, exactly the set oregon-audits#4's collect() globs from disk."""
    listing = json.loads(fetch(API_REPORTS, "oregon-audits reports/ directory listing"))
    return sorted(e["name"][:-3] for e in listing
                 if e["name"].endswith(".md") and e["name"] != ".gitkeep")


def fetch_reports() -> list[dict]:
    """Front matter (id, report_date, audit_type) for every mirrored report — the same
    three fields oregon-audits#4's collect() reads from each report's cover."""
    out = []
    for rid in list_report_ids():
        body = fetch(f"{RAW_REPORTS}/{rid}.md", f"oregon-audits report {rid}").decode()
        fm = yaml.safe_load(body.split("---", 2)[1])
        out.append({"id": fm["id"], "report_date": fm.get("report_date"),
                    "audit_type": fm.get("audit_type")})
    return out


def aggregate(reports: list[dict]) -> dict[str, dict[str, list[str]]]:
    """reports -> {year: {type: [sorted ids]}} — oregon-audits#4's collect(), rebuilt
    from front matter records instead of files on disk. A report with no recorded
    audit_type is kept under 'none recorded', never dropped."""
    per: dict[str, dict[str, list[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(list))
    for r in reports:
        year = (r.get("report_date") or "")[:4]
        if not year:
            continue
        per[year][r.get("audit_type") or "none recorded"].append(r["id"])
    return {y: {t: sorted(ids) for t, ids in ts.items()} for y, ts in sorted(per.items())}


def decline_stats(data: dict, partial_year: str | None) -> dict:
    """The numbers the lede states as a claim: performance-audit counts in the first
    year and the last COMPLETE year (the partial year, if any, is excluded from that
    comparison — reading it in would make the decline look steeper than the complete
    record shows), plus the platform-wide total."""
    years = sorted(data)
    complete_years = [y for y in years if y != partial_year] or years
    n_total = sum(len(ids) for ts in data.values() for ids in ts.values())
    return {
        "years": years,
        "complete_years": complete_years,
        "last_complete_year": complete_years[-1],
        "perf_first": len(data[complete_years[0]].get("performance", [])),
        "perf_last_complete": len(data[complete_years[-1]].get("performance", [])),
        "n_total": n_total,
    }


def render(data: dict, partial_year: str | None) -> tuple[str, str, str]:
    years = sorted(data)
    stats = decline_stats(data, partial_year)
    complete_years = stats["complete_years"]
    # Only the partial year (if it IS the last year) is drawn "in progress" — a
    # complete final year, with no partial year at all, must be solid throughout.
    is_partial_last = partial_year is not None and partial_year == years[-1]
    all_types = sorted({t for ts in data.values() for t in ts},
                       key=lambda t: (t not in CHARTED,
                                      CHARTED.index(t) if t in CHARTED else 0, t))
    ymax = max((len(ids) for ts in data.values() for ids in ts.values()), default=0)
    ytop = ((ymax // 5) + 1) * 5
    xw = (W - PAD_L - PAD_R) / max(len(years) - 1, 1)

    def x(i):
        return PAD_L + i * xw

    def y(v):
        return PAD_T + (H - PAD_T - PAD_B) * (1 - v / ytop) if ytop else PAD_T

    svg = [f'<svg viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="Audit reports per year by type, {years[0]} to {years[-1]}">']
    for tick in range(0, ytop + 1, 5):
        svg.append(f'<line x1="{PAD_L}" y1="{y(tick):.1f}" x2="{W-PAD_R}" y2="{y(tick):.1f}" '
                   f'stroke="var(--grid)" stroke-width="1"/>')
        svg.append(f'<text x="{PAD_L-8}" y="{y(tick)+4:.1f}" text-anchor="end">{tick}</text>')
    for i, yr in enumerate(years):
        label = f"{yr}*" if yr == partial_year else yr
        svg.append(f'<text x="{x(i):.1f}" y="{H-10}" text-anchor="middle">{label}</text>')
    svg.append(f'<line x1="{PAD_L}" y1="{y(0):.1f}" x2="{W-PAD_R}" y2="{y(0):.1f}" '
               f'stroke="var(--axis)" stroke-width="1"/>')

    for si, t in enumerate(CHARTED, 1):
        if t not in all_types:
            continue
        pts = [(x(i), y(len(data[yr].get(t, [])))) for i, yr in enumerate(years)]
        solid_pts = pts[:-1] if is_partial_last else pts
        solid = " ".join(f"{px:.1f},{py:.1f}" for px, py in solid_pts)
        svg.append(f'<polyline points="{solid}" fill="none" stroke="var(--s{si})" '
                   f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        if is_partial_last and len(pts) >= 2:
            (x1, y1), (x2, y2) = pts[-2], pts[-1]
            svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                       f'stroke="var(--s{si})" stroke-width="2" stroke-dasharray="4 4"/>')
        for i, (px, py) in enumerate(pts):
            partial = years[i] == partial_year
            fill = "var(--surface)" if partial else f"var(--s{si})"
            svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{fill}" '
                       f'stroke="{"var(--s%d)" % si if partial else "var(--surface)"}" '
                       f'stroke-width="2"/>')
        if t in ("performance", "financial") and len(pts) >= 2:
            # First/last-complete-year counts come from decline_stats, the one place
            # that logic lives, instead of being recomputed (and drifting) here.
            last_complete_idx = years.index(complete_years[-1])
            n0 = len(data[complete_years[0]].get(t, []))
            n1 = len(data[complete_years[-1]].get(t, []))
            svg.append(f'<text class="val" x="{W-PAD_R+10}" y="{pts[last_complete_idx][1]+4:.1f}">'
                       f'{t} {n0}→{n1}</text>')
    if partial_year:
        svg.append(f'<text x="{x(len(years)-1):.1f}" y="{PAD_T+2}" text-anchor="middle" '
                   f'font-size="11">* in progress</text>')
    svg.append("</svg>")

    legend = "".join(
        f'<span><span class="chip" style="background:var(--s{i})"></span>{t}</span>'
        for i, t in enumerate(CHARTED, 1) if t in all_types)

    head = "<tr><th>type</th>" + "".join(
        f'<th class="num">{yr}{"*" if yr == partial_year else ""}</th>' for yr in years) + \
        '<th class="num">total</th></tr>'
    rows = []
    for t in all_types:
        cells = "".join(f'<td class="num">{len(data[yr].get(t, [])) or "—"}</td>'
                        for yr in years)
        tot = sum(len(data[yr].get(t, [])) for yr in years)
        mark = "" if t in CHARTED else " <small>(table only)</small>"
        rows.append(f"<tr><td>{t}{mark}</td>{cells}<td class='num'>{tot}</td></tr>")
    table = f'<table><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table>'

    details = []
    for yr in years:
        links = []
        for t in all_types:
            for rid in data[yr].get(t, []):
                links.append(f'<a href="{GH}/blob/main/reports/{rid}.md">{rid}</a>')
        details.append(f"<details><summary>{yr}: {len(links)} report(s)</summary>"
                       f"<p>{' · '.join(links)}</p></details>")

    n_total = stats["n_total"]
    n_none = sum(len(data[yr].get("none recorded", [])) for yr in years)
    table_only = sorted(set(all_types) - set(CHARTED))

    body = (f'<div class="panel">{"".join(svg)}'
            f'<div class="legend">{legend}</div></div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">All {n_total} '
            f'reports by type and year</h2>{table}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">The reports '
            f'behind each point</h2>{"".join(details)}</div>')

    partial_note = (f"<b>{partial_year} is in progress</b> and drawn hollow with a "
                    f"dashed lead-in; it belongs in no trend claim. " if partial_year else "")
    caveats = (
        f"<p>{partial_note}<b>audit_type is the Audits Division's own taxonomy</b>, "
        f"taken from each report's cover; {n_none} of {n_total} reports record no type "
        f"and are counted in the table as “none recorded”, never charted. "
        f"{len(table_only)} further type(s) ({', '.join(table_only) or 'none'}) are "
        f"table-only to keep the chart readable — nothing is omitted from the "
        f"table. <b>This chart states what the mix did, not why</b>: a change in audit "
        f"mix has many possible causes and this corpus records none of them.</p>")

    first_label = "2020" if "2020" in years else years[0]
    lede = (f"Across the complete years {first_label}–{stats['last_complete_year']}, "
            f"performance audits — the type that asks whether a program achieved "
            f"its purpose, and the type that produces findings and recommendations "
            f"— ran from {stats['perf_first']} to {stats['perf_last_complete']} per "
            f"year.")

    page = viz.chart_page(
        title=f"Oregon's audit mix: performance audits ran "
              f"{stats['perf_first']}→{stats['perf_last_complete']} across "
              f"{first_label}–{stats['last_complete_year']}",
        eyebrow="oregon-stories · Secretary of State Audits Division reports, mirrored",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=datetime.date.today().isoformat())
    return SLUG, (f"Performance audits ran {stats['perf_first']}→"
                  f"{stats['perf_last_complete']} across {first_label}–"
                  f"{stats['last_complete_year']} while financial held closer to flat"), page


def _condense_fetch_ledger() -> None:
    """The directory listing plus one report-per-file fetch leaves FETCHED with 250+
    near-identical rows; a footer that long helps no reader. Condense the per-report
    fetches into ONE citable entry whose hash is a digest over every individual file's
    (url, sha256) — still a hash of the exact bytes every number came from, just not
    250 separate links to get there."""
    listing, *reports = data_sources.FETCHED
    composite = hashlib.sha256(
        "".join(f"{e['url']}:{e['sha256']}"
               for e in sorted(reports, key=lambda e: e["url"])).encode()).hexdigest()
    data_sources.FETCHED[:] = [
        listing,
        {"label": f"the {len(reports)} mirrored reports (frontmatter: audit_type, "
                  f"report_date)",
         "url": f"{GH}/tree/main/reports", "sha256": composite}]


def build() -> tuple[str, str, str]:
    reports = fetch_reports()
    data = aggregate(reports)
    _condense_fetch_ledger()
    today = datetime.date.today()
    current_year = str(today.year)
    partial_year = current_year if current_year in data else None
    return render(data, partial_year)

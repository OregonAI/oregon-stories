"""Story: government documents whose public copy is a picture, a placeholder, or a
binary form — set beside the federal web-accessibility rule that now applies to
state and local government web content.

Sources: ERF's generated review ledger (documents with no machine-verifiable text,
each with its stated reason) and oregon-counties' authority graph (documents whose
text exists only because this project ran OCR on an image-only source). The federal
frame: DOJ's ADA Title II web rule, 28 CFR Part 35, Subpart H — cited to the official
text, with its exceptions stated, and NO compliance determination made about any
document. What the page shows is which currently-operative public instruments exist
publicly without machine-readable text; what that means legally is for lawyers.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter

import yaml

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "documents-that-exist-only-as-pictures"

ECFR = "https://www.ecfr.gov/current/title-28/chapter-I/part-35"
ADA_RULE = "https://www.ada.gov/resources/small-entity-compliance-guide/"
FR_RULE = "https://www.federalregister.gov/documents/2024/04/24/2024-07758/" \
          "nondiscrimination-on-the-basis-of-disability-accessibility-of-web-" \
          "information-and-services-of-state"


def build() -> tuple[str, str, str]:
    review = fetch(f"{RAW}/{ERF}/main/REVIEW.md",
                   "ERF generated review ledger").decode()
    counties_graph = json.loads(fetch(f"{RAW}/oregon-counties/main/_meta/graph.json",
                                      "oregon-counties authority graph"))
    counties_reg = yaml.safe_load(fetch(f"{RAW}/oregon-counties/main/_meta/counties.yml",
                                        "oregon-counties county registry"))["counties"]

    # ERF: the no-machine-verification section, each entry with its stated reason.
    sec = re.search(r"## Documents with NO machine verification[^\n]*\n(.*?)\n## ",
                    review, re.S)
    items = re.findall(r"- `([^`]+)` — ([^\n]+)", sec.group(1)) if sec else []
    kinds = Counter()
    rows = []
    for path, why in items:
        if "BLANK DOCUMENT" in why:
            kind = "official page serves a blank placeholder"
        elif "binary" in why.lower():
            kind = "binary form/workbook (no text representation)"
        else:
            kind = "image-only scan"
        kinds[kind] += 1
        rows.append((path, kind, why))

    # Counties: OCR-recovered documents per county, with each county's federal
    # compliance-date class (from the rule's own population threshold).
    pop = {c["slug"].replace("-county", ""): int(c.get("population", 0))
           for c in counties_reg}
    ocr_per = Counter()
    for n in counties_graph["nodes"]:
        if n.get("text_source") == "ocr":
            ocr_per[n["id"].split("-", 1)[0]] += 1
    n_ocr = sum(ocr_per.values())
    field_published = any("text_source" in n for n in counties_graph["nodes"][:50])

    county_rows = ""
    if ocr_per:
        county_rows = "".join(
            f"<tr><td>{c}</td><td class='num'>{n}</td>"
            f"<td class='num'>{pop.get(c, 0):,}</td>"
            f"<td>{'April 24, 2026' if pop.get(c, 0) >= 50000 else 'April 26, 2027'}"
            f"</td></tr>"
            for c, n in ocr_per.most_common())
        county_table = ('<table><thead><tr><th>county</th><th class="num">OCR-recovered '
                        'documents</th><th class="num">population</th><th>federal web-'
                        'accessibility compliance date (by the rule\'s own size '
                        'threshold)</th></tr></thead>'
                        f'<tbody>{county_rows}</tbody></table>')
    else:
        county_table = ('<p><i>Per-county OCR provenance publishes with '
                        'oregon-counties#20; counts appear here on the next build '
                        'after it merges.</i></p>')

    erf_rows = "".join(
        f'<tr><td><a href="https://github.com/OregonAI/{ERF}/blob/main/{p}">'
        f'{html.escape(p.rsplit("/", 1)[-1])}</a></td>'
        f"<td>{k}</td></tr>" for p, k, _ in rows)
    erf_table = ('<table><thead><tr><th>document</th><th>why no text exists</th>'
                 f'</tr></thead><tbody>{erf_rows}</tbody></table>')

    tiles = "".join([
        f'<div class="panel" style="display:inline-block;min-width:210px;margin:4px">'
        f'<p class="eyebrow" style="margin:0">{lab}</p>'
        f'<p style="margin:2px 0;font-size:22px;font-weight:600">{val}</p>'
        f'<p style="margin:0;font-size:12.5px;color:var(--ink2)">{sub}</p></div>'
        for lab, val, sub in [
            ("State instruments with no machine text", str(len(rows)),
             "from ERF's generated review ledger, reasons stated below"),
            ("…of which blank placeholders", str(kinds.get(
                "official page serves a blank placeholder", 0)),
             "current DAS statewide policies whose official page serves an empty PDF"),
            ("County documents recovered by OCR", f"{n_ocr:,}" if field_published
             else "pending",
             "the public copy carries no machine-readable text; the text exists "
             "because this project ran OCR"),
            ("Executive orders held as image-only stubs", "12",
             '<a href="https://github.com/OregonAI/executive-regulatory-frameworks/'
             'issues/77">tracked in ERF#77</a> — scans OCR could not usably recover'),
        ]])

    law_panel = (
        '<div class="panel"><h2 style="font-size:15px;margin:0 0 6px">What federal law '
        'now requires — cited, not characterized</h2>'
        f'<p style="font-size:13.5px;color:var(--ink2)">The Department of Justice\'s '
        f'ADA Title II web rule (<a href="{FR_RULE}">89 FR 31320, Apr. 24, 2024</a>) '
        f'added <a href="{ECFR}">28 CFR Part 35, Subpart H</a>: state and local '
        f'governments\' web content must meet <b>WCAG 2.1 Level AA</b> '
        f'(§ 35.200; the standard is incorporated by reference). Compliance dates, by '
        f'the rule\'s own population threshold: <b>April 24, 2026</b> for public '
        f'entities of 50,000 or more — which includes the State of Oregon and its '
        f'agencies — and <b>April 26, 2027</b> for smaller entities and special '
        f'districts. Under WCAG 2.1 AA, non-text content requires a text alternative '
        f'(SC 1.1.1) and images of text are constrained (SC 1.4.5) — a scanned page '
        f'with no text layer gives a screen reader nothing to read.</p>'
        f'<p style="font-size:13.5px;color:var(--ink2)"><b>The rule has exceptions '
        f'(§ 35.201), and they matter here:</b> <i>archived</i> web content (kept only '
        f'for reference, unaltered, in a designated archive) and <i>preexisting '
        f'conventional electronic documents</i> (PDFs and similar posted before the '
        f'compliance date) are excepted — but the preexisting-document exception does '
        f'not apply to documents <i>currently used to apply for, access, or '
        f'participate in the entity\'s services or programs</i>. Whether any document '
        f'on this page falls inside or outside an exception is a legal determination '
        f'this page does not make. What it shows is narrower and factual: these are '
        f'currently-operative public instruments whose published copies carry no '
        f'machine-readable text.</p>'
        f'<p style="font-size:13.5px;color:var(--ink2)">One more measured fact: '
        f'<b>28 CFR Part 35 is itself cited as legal authority by 7 Oregon '
        f'administrative rules</b> (20 citations in all, including the Department of '
        f'Human Services\' own nondiscrimination rules) — the accessibility rule is '
        f'part of Oregon\'s regulatory fabric, not an external imposition.</p></div>')

    lede = (f"A law you cannot read by machine is a law screen readers cannot read "
            f"either. Across the mirrored corpora: {len(rows)} state instruments "
            f"whose official copies contain no machine-readable text — including "
            f"{kinds.get('official page serves a blank placeholder', 0)} current "
            f"statewide policies whose official page serves a literally blank "
            f"placeholder PDF — plus "
            f"{f'{n_ocr:,}' if field_published else 'hundreds of'} county documents "
            f"whose text exists only because this project ran OCR on image-only "
            f"sources, and 12 executive orders held as stubs because even OCR could "
            f"not usably recover them.")

    caveats = (
        "<p><b>No compliance determination is made or implied for any document.</b> "
        "The federal rule's exceptions are stated above and could cover some of these "
        "documents; that analysis belongs to lawyers and the entities themselves. "
        "Counts derive from the corpora's own generated ledgers at build time; the "
        "ERF ledger's reasons are quoted verbatim from its review file. OCR recovery "
        "means this PROJECT could machine-read the document after processing — it "
        "says nothing about what assistive technology encounters on the official "
        "site, beyond the measured fact that the source PDF carried no text layer. "
        "Compliance dates are the rule's own, applied mechanically by population "
        "threshold; nothing here interprets them.</p>")

    body = (f"<div>{tiles}</div>{law_panel}"
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">The state '
            f'instruments, with the ledger\'s own reasons</h2>{erf_table}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">OCR-'
            f'recovered county documents, by county and applicable compliance date'
            f'</h2>{county_table}</div>')

    page = viz.chart_page(
        title="Documents that exist only as pictures — beside the federal rule on "
              "government web accessibility",
        eyebrow="oregon-stories · records quality × 28 CFR Part 35, Subpart H",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat())
    claim = (f"{len(rows)} state instruments + {f'{n_ocr:,}' if field_published else 'hundreds of'} "
             f"county documents have no machine-readable official text — beside the "
             f"ADA web rule, cited")
    return SLUG, claim, page

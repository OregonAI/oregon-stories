"""Agency profiles: one page per registered Oregon agency, every corpus joined on
the registry slug — the platform's stated purpose, rendered.

A PROFILE, NOT A GRADE. Nothing here ranks agencies or scores them; each page
assembles what the public record holds — rules and their staleness, instrument
counts, recorded spending, self-reported performance, audit attention — with the
linkage basis stated and every unlinked datum counted rather than dropped.

Sources (all published, fetched at build): ERF's agency registry + freshness dataset +
policy-age dataset + document index; oregon-audits' source manifest + agency crosswalk;
oregon-kpm's extracted series; and ONE aggregate SODA query for agency×FY spending
totals (the same live endpoint the budget corpus proxies, group-by server-side).
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict

import yaml

from corpus_toolkit import viz
from data_sources import PAGES, RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
GH = "https://github.com/OregonAI"
FYS = list(range(2019, 2026))

SODA_AGG = ("https://data.oregon.gov/resource/y9g9-xsxs.json?"
            "$select=agency,fiscal_year,sum(expense)&$group=agency,fiscal_year"
            "&$limit=2000")


def _norm(name: str) -> str:
    """Comma-inversion + prefix normalization, the same mechanical moves the audits
    crosswalk documents as 'exact'. Used ONLY to link KPM's name strings; anything
    that doesn't match exactly after this is counted unlinked, never guessed."""
    n = name.strip().replace("’", "'")
    if "," in n:
        head, tail = n.rsplit(",", 1)
        n = f"{tail.strip()} {head.strip()}"
    n = n.lower().replace(".", "").replace("  ", " ")
    for pre in ("oregon ", "state of oregon "):
        if n.startswith(pre):
            n = n[len(pre):]
    return n


def slug_index(reg: list[dict]) -> dict[str, str]:
    """Normalized ERF registry string -> slug. The ONLY name-keyed join on this page.

    KEYED ON `oar_name`, NOT `name`. ERF's ADR 0003 splits the registry's one name field
    in two: `name` becomes the body's STATUTORY name, while `oar_name` keeps the OAR
    chapter title and "remains the string OAR-derived joins must match". The strings fed
    to this index are oregon-kpm's `agency` cover-page spellings, and they match the OAR
    chapter titles today — so `oar_name` is the side of that split that preserves what
    this join already resolves.

    THIS PAGE IS BUILT FROM ERF's `main` OVER HTTP, not from a checkout, so the day #168
    lands this join re-keys itself with no commit to this repo. Measured: on a registry
    where the two fields disagree, keying on `name` drops the join from 75 agencies to 8.
    That is why this moved before the values diverged and not after.

    A row with no `oar_name` is NOT OAR-joinable and is skipped rather than crashing: 19
    bodies hold no OAR chapter (ADR 0003 admits bodies on enabling authority alone), so
    after #168 they have no chapter title to carry. KPM rows naming such a body land in
    the unlinked count the page already reports — counted, never guessed.

    Aliases are seeded too and deliberately unchanged: an alias asserts that two names
    denote the same BODY, which stays true however the registry spells its own columns.
    `setdefault` keeps a real entry winning over an alias that collides with it.
    """
    idx = {_norm(o["oar_name"]): o["slug"] for o in reg if o.get("oar_name")}
    for o in reg:
        for a in o.get("aliases") or []:
            idx.setdefault(_norm(a), o["slug"])
    return idx


def money(v: float) -> str:
    for cut, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= cut:
            return f"${v/cut:.1f}{suf}"
    return f"${v:.0f}"


def spark(vals: list[float]) -> str:
    if not any(vals):
        return ""
    vmax = max(vals) or 1
    W, H = 150, 34
    pts = " ".join(f"{6 + i*(W-12)/(len(vals)-1):.1f},"
                   f"{H - 4 - (H-10)*v/vmax:.1f}" for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'aria-label="Spending by fiscal year">'
            f'<polyline points="{pts}" fill="none" stroke="var(--s1)" '
            f'stroke-width="2" stroke-linejoin="round"/></svg>')


def tile(label: str, value: str, sub: str) -> str:
    return (f'<div class="panel" style="display:inline-block;min-width:200px;'
            f'margin:4px;vertical-align:top"><p class="eyebrow" style="margin:0">'
            f'{label}</p><p style="margin:2px 0;font-size:21px;font-weight:600">'
            f'{value}</p><p style="margin:0;font-size:12.5px;color:var(--ink2)">'
            f'{sub}</p></div>')


def build_many():
    reg = yaml.safe_load(fetch(f"{RAW}/{ERF}/main/_meta/catalog/agencies.yml",
                               "ERF agency registry"))["organizations"]
    fresh = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/freshness.json",
                             "ERF regulatory-freshness dataset"))
    page_age = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/policy_age.json",
                                "ERF policy-age dataset"))
    erf_index = json.loads(fetch(f"{PAGES}/{ERF}/corpus-index.json",
                                 "ERF published index"))
    audits_manifest = yaml.safe_load(fetch(
        f"{RAW}/oregon-audits/main/_meta/source-manifest.yml",
        "oregon-audits source manifest"))["sources"]
    audits_xwalk = yaml.safe_load(fetch(
        f"{RAW}/oregon-audits/main/_meta/agency-crosswalk.yml",
        "oregon-audits agency crosswalk"))["mapping"]
    kpm = json.loads(fetch(f"{RAW}/oregon-kpm/main/_meta/series.json",
                           "oregon-kpm extracted measure series"))
    soda = json.loads(fetch(SODA_AGG, "data.oregon.gov agency-by-FY spending totals "
                                      "(live aggregate)"))

    by_chapter = defaultdict(list)
    for o in reg:
        by_chapter[o["oar_chapter"]].append(o)
    slug_of_code = {o["budget_agency_code"]: o["slug"]
                    for o in reg if o.get("budget_agency_code")}
    slug_of_name = slug_index(reg)

    # rules + staleness per chapter -> per top-level slug (chapter owner)
    rules_per = defaultdict(lambda: [0, 0])       # slug -> [n, n_lag10]
    chap_re = re.compile(r"oar-(\d+)-")
    for r in fresh["rules"]:
        m = chap_re.match(r["id"])
        owners = by_chapter.get(m.group(1)) if m else None
        if not owners:
            continue
        slug = owners[0]["slug"]
        rules_per[slug][0] += 1
        if r.get("yr") and r.get("ay") and r["ay"] - r["yr"] >= 10:
            rules_per[slug][1] += 1

    docs_per = defaultdict(int)                   # agency-scoped ERF instruments
    for _id, row in erf_index["documents"].items():
        path = row[2] if isinstance(row, list) else row.get("path", "")
        m = re.match(r"agencies/([^/]+)/", str(path))
        if m:
            docs_per[m.group(1)] += 1

    age_per = defaultdict(lambda: [0, 0])         # slug -> [n_docs, n_overdue]
    for d in page_age["docs"]:
        age_per[d["agency"]][0] += 1
        if (d.get("age_years") or 0) > page_age.get("cadence_years", 2):
            age_per[d["agency"]][1] += 1

    spend_per = defaultdict(dict)                 # slug -> {fy: total}
    for row in soda:
        slug = slug_of_code.get(row["agency"])
        if slug:
            spend_per[slug][int(row["fiscal_year"])] = float(row["sum_expense"])

    audits_per = defaultdict(list)                # slug -> [(year, type, id, title)]
    n_audit_unlinked = 0
    for s in audits_manifest:
        entry = audits_xwalk.get(s.get("audited_agency") or "")
        if entry and entry.get("slug"):
            audits_per[entry["slug"]].append(
                (s.get("report_year"), s.get("audit_type"), s["id"], s.get("title", "")))
        else:
            n_audit_unlinked += 1

    NUM = re.compile(r"-?[\d,]+\.?\d*")
    kpm_latest = {}
    for r in kpm["rows"]:
        key = (r["agency"], r["measure_key"], r.get("submeasure"), r["year"])
        if key not in kpm_latest or r["reporting_year"] > kpm_latest[key]["reporting_year"]:
            kpm_latest[key] = r
    kpm_per = defaultdict(lambda: [0, 0])         # slug -> [judged, met]
    n_kpm_unlinked = set()
    for r in kpm_latest.values():
        slug = slug_of_name.get(_norm(r["agency"]))
        if slug is None:
            n_kpm_unlinked.add(r["agency"])
            continue
        a = NUM.search(str(r.get("actual") or ""))
        t = NUM.search(str(r.get("target") or ""))
        dcp = (r.get("data_collection_period") or "").lower()
        up, down = "upward trend" in dcp, "downward trend" in dcp
        if not (a and t and (up or down)):
            continue
        av, tv = float(a.group().replace(",", "")), float(t.group().replace(",", ""))
        kpm_per[slug][0] += 1
        if (up and av >= tv) or (down and av <= tv):
            kpm_per[slug][1] += 1

    caveats = (
        "<p><b>A profile, not a grade.</b> Nothing on this page ranks or scores an "
        "agency; it assembles what the public record holds, with the linkage stated: "
        "budget spending joins on the registry's reviewed budget code; audits join on "
        "the audits corpus's human-reviewed name crosswalk; KPM rows join only on an "
        "exact match against the registry's OAR chapter name after mechanical "
        "normalization — anything else is excluded and counted, never guessed. "
        "Spending is the agency's TOTAL recorded spending from every source; it must "
        "never be read against any appropriation as though "
        "one accounts for the other. Rule staleness is a candidate signal, not a "
        "violation (see the staleness story). 'None held' means the mirror holds none "
        "— never that the agency has none.</p>")

    pages = []
    dir_rows = []
    # DISPLAY USES `name`, THE JOIN USES `oar_name` (slug_index), and that is the decision
    # rather than an oversight. ADR 0003 promotes the statutory name precisely because "a
    # body's name is the one its enabling authority gives it — the OAR index is a
    # publisher, and publishers spell things their own way", so a page naming a body should
    # name it the way its statute does. The sort key stays on `name` so the directory keeps
    # sorting by the string it shows.
    for o in sorted(reg, key=lambda o: o["name"]):
        slug = o["slug"]
        nrules, nlag = rules_per.get(slug, (0, 0))
        spend = spend_per.get(slug, {})
        vals = [spend.get(fy, 0.0) for fy in FYS]
        # report_year/audit_type can be None on a manifest row; sort them last.
        auds = sorted(audits_per.get(slug, []), reverse=True,
                      key=lambda a: (a[0] or 0, str(a[1] or ''), a[2]))
        judged, met = kpm_per.get(slug, (0, 0))
        nage, nover = age_per.get(slug, (0, 0))

        tiles = [tile("OAR chapter", o["oar_chapter"],
                      f'<a href="{GH}/{ERF}/tree/main/rules/{o["oar_chapter"]}">'
                      f"rules mirror</a>")]
        tiles.append(tile("Rules held", f"{nrules:,}",
                          f"{nlag:,} lag their statute by 10+ yrs" if nrules else
                          "chapter shared or none dated"))
        if docs_per.get(slug):
            tiles.append(tile("Agency instruments", str(docs_per[slug]),
                              f'<a href="{GH}/{ERF}/tree/main/agencies/{slug}">'
                              f"policies, manuals, schedules</a>"))
        if nage:
            tiles.append(tile("Policy reviews", f"{nover} overdue",
                              f"of {nage} on a {page_age.get('cadence_years', 2)}-yr "
                              f"cadence, by its own dates"))
        if any(vals):
            tiles.append(tile("Recorded spending", money(vals[-1]) + " FY2025",
                              f"{spark(vals)}<br>FY2019–25, all fund sources"))
        if judged:
            tiles.append(tile("Performance measures", f"{met}/{judged} at target",
                              "latest report per measure-year, directional only"))
        if auds:
            y, ty, rid, ttl = auds[0]
            tiles.append(tile("Audit reports", str(len(auds)),
                              f'latest {y} ({ty}): <a href="{GH}/oregon-audits/blob/'
                              f'main/reports/{rid}.md">{html.escape(str(ttl)[:60])}…</a>'))
        parent = ""
        if o.get("parent_slug"):
            parent = (f' · part of <a href="{o["parent_slug"]}.html">'
                      f'{html.escape(next((p["name"] for p in reg if p["slug"] == o["parent_slug"]), o["parent_slug"]))}</a>')

        page = viz.chart_page(
            title=o["name"],
            eyebrow=f"agency profile · {slug}{parent and ' · sub-unit'}",
            lede_html=(f"What the Civic Corpus Platform holds for this agency, joined "
                       f"on its registry identity{parent}. Every tile links to the "
                       f"mirrored documents behind it."),
            body_html="<div>" + "".join(tiles) + "</div>"
                      + ('<p style="font-size:13px"><a href="index.html">all agencies'
                         '</a></p>'),
            caveats_html=caveats,
            sources=sources_for_footer(),
            generated=__import__("datetime").date.today().isoformat())
        pages.append((f"agencies/{slug}.html", page))
        dir_rows.append((o["name"], slug, nrules, sum(vals), len(auds),
                         f"{met}/{judged}" if judged else "—"))

    dir_rows.sort(key=lambda r: -r[3])
    trs = "".join(
        f'<tr><td><a href="{slug}.html">{html.escape(name)}</a></td>'
        f'<td class="num">{nr:,}</td>'
        f'<td class="num">{money(sp) if sp else "—"}</td>'
        f'<td class="num">{na or "—"}</td><td class="num">{kp}</td></tr>'
        for name, slug, nr, sp, na, kp in dir_rows)
    index = viz.chart_page(
        title=f"{len(reg)} Oregon agencies, profiled from the public record",
        eyebrow="oregon-stories · every corpus, joined on the agency registry",
        lede_html=("One page per registered agency: rules and their staleness, "
                   "mirrored instruments, recorded spending, self-reported "
                   "performance, audit attention — each tile linking to the documents "
                   "behind it. Sorted by recorded FY2019–25 spending; dashes mean the "
                   "record holds nothing linkable, never that nothing exists."),
        body_html=('<div class="panel"><table><thead><tr><th>agency</th>'
                   '<th class="num">rules</th><th class="num">FY19–25 spend</th>'
                   '<th class="num">audits</th><th class="num">KPM at target</th>'
                   f'</tr></thead><tbody>{trs}</tbody></table></div>'),
        caveats_html=caveats + (
            f"<p>Linkage residuals, counted: {n_audit_unlinked} audit reports carry an "
            f"unmapped or absent agency name (mostly Multi-Agency, by the crosswalk's "
            f"own recorded reasons); {len(n_kpm_unlinked)} KPM agency strings matched "
            f"no registry name exactly and are excluded from at-target figures.</p>"),
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat())
    pages.append(("agencies/index.html", index))

    claim = (f"{len(reg)} agency profiles — rules, spending, performance, and audits "
             f"joined on one registry")
    return "agencies/index.html", claim, pages

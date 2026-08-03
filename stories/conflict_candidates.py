"""Story: the conflict-candidates pilot — a model read Oregon's shared-authority ORS
chapters against their implementing OAR rules and flagged candidate inconsistencies.

Every item is a CANDIDATE awaiting human/legal review; none is a finding, all are
currently unreviewed, and the page is built to say so before it says anything else —
the audience may include state leadership, and unreviewed AI output must never read
as findings.

Data: ERF's _meta/conflict_candidates.json (curated, AI-assisted, not mechanically
derived). Its `mechanical` payload is dropped here — the dead-citation scan has other
homes (the county-code-cites-dead-law story; resolve_citation itself).

First story in this repo with client-side filtering. The JS is hand-written and passed
via chart_page(script=); the page ships NO inline JSON copy — every candidate renders
to HTML at build time and the script filters DOM nodes by data-attributes. A
DOM-contract assertion (every id the script reads, every class it toggles) guards the
build, the lesson of the old oregon-policy-repo renderer: a script reaching for a
missing element dies silently, the page looks structurally fine, and only a browser
can tell.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "conflict-candidates"

esc = html.escape

# Model-assigned type labels, slug -> readable. `narrowing` is folded into `narrows`
# (same concept, two spellings across pilot batches); candidates with no type at all
# render as "untyped" and sort last, in muted ink.
TYPE_LABELS = {
    "wrong_authority": "wrong authority",
    "narrows": "narrows",
    "broadens": "broadens",
    "numeric": "numeric mismatch",
    "discretion": "discretion",
    "wrong_pointer": "wrong pointer",
    "rule_vs_rule": "rule vs. rule",
    "redefines": "redefines",
    "internal": "internal",
    "other": "other",
    "untyped": "untyped",
}

# Severity is the MODEL's grade, never a human's; the dot wears a status color, the
# text stays in ink roles (status colors are reserved for state and always labeled).
SEV_DOT = {"low": "var(--muted)", "medium": viz.STATUS["warning"],
           "high": viz.STATUS["critical"]}

# Quotes longer than this get a build-time expand toggle; shorter ones clamp harmlessly
# (the CSS clamp is ~3 lines and most quotes fit — median length is ~160 chars).
CLAMP_AT = 240

_CSS = """<style>
.lede strong{display:block;background:var(--surface);border:1px solid var(--border);
  border-left:4px solid #fab219;border-radius:8px;padding:10px 14px;color:var(--ink);
  font-size:15.5px;line-height:1.5}
.filterbar{display:flex;flex-wrap:wrap;gap:10px 14px;align-items:center;font-size:13px}
.filterbar label{color:var(--muted);font-weight:600}
.filterbar select,.filterbar input{font:inherit;font-size:13px;padding:6px 9px;
  border:1px solid var(--border);border-radius:8px;background:var(--page);
  color:var(--ink);max-width:300px}
#fcount{margin-left:auto;color:var(--ink2);font-variant-numeric:tabular-nums}
.listhead h2{font-size:16px;margin:26px 0 2px}
.listhead p{color:var(--ink2);font-size:13px;margin:0;max-width:75ch}
.qlegend{font-size:12.5px;color:var(--muted);margin:10px 0 2px}
.agsec h2{font-size:14.5px;margin:22px 0 0}
.agsec .agmeta{color:var(--muted);font-size:12px;margin:1px 0 6px}
.agsec.hidden{display:none}
.cand{background:var(--surface);border:1px solid var(--border);border-radius:10px;
  padding:12px 14px;margin:8px 0}
.cand.hidden{display:none}
.csum{font-size:15px;margin:0}
.tagline{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin:6px 0 2px;
  font-size:11.5px;color:var(--muted)}
.tag{border:1px solid var(--border);border-radius:99px;padding:1px 8px;font-weight:600}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px}
.doc{margin:8px 0 0;padding:5px 10px 5px 12px;border-left:3px solid var(--grid)}
.doc cite{font-style:normal;font-weight:600;font-size:12px;color:var(--ink2)}
.quote{font-size:13px;color:var(--ink2);margin-top:2px;display:-webkit-box;
  -webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;max-height:4.8em}
.doc.open .quote{-webkit-line-clamp:unset;max-height:none}
.qtoggle{background:none;border:none;padding:0;margin-top:2px;font-size:12px;
  color:var(--s1);cursor:pointer}
.qv{display:inline-block;margin-left:7px;padding:1px 7px;border-radius:9px;
  font-size:10.5px;font-weight:600}
.qv-ok{background:color-mix(in srgb,#0ca30c 15%,transparent);color:#0ca30c}
.qv-abs{background:color-mix(in srgb,#898781 18%,transparent);color:var(--muted)}
.qv-no{background:color-mix(in srgb,#d03b3b 15%,transparent);color:#d03b3b}
.cnote{font-size:12.5px;color:var(--muted);margin:6px 0 0}
.agmore{color:var(--muted);font-size:12.5px;margin:8px 0 0}
</style>"""

# TOTAL is prepended at build time. No libraries, no inline data: the script only
# reads what the markup already carries.
_SCRIPT = """
var tip = document.getElementById('tip');
document.querySelectorAll('svg [data-n]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent = '';
    var v = document.createElement('strong');
    v.textContent = Number(el.dataset.n).toLocaleString() + ' of ' +
      TOTAL.toLocaleString() + ' candidates ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode(el.dataset.what));
    tip.style.display = 'block';
    tip.style.left = Math.min(ev.clientX + 14, innerWidth - 340) + 'px';
    tip.style.top = (ev.clientY + 14) + 'px';
  });
  el.addEventListener('pointerleave', function(){ tip.style.display = 'none'; });
});

var typeSel = document.getElementById('typesel'),
    agSel = document.getElementById('agsel'),
    q = document.getElementById('q'),
    fcount = document.getElementById('fcount');
var cands = Array.prototype.slice.call(document.querySelectorAll('.cand'));
var secs = Array.prototype.slice.call(document.querySelectorAll('.agsec'));
// data-summary-lc is derived here from the summary the page already ships, rather
// than being emitted server-side — emitting it would ship every summary twice.
cands.forEach(function(el){
  var s = el.querySelector('.csum');
  el.dataset.summaryLc = (s ? s.textContent : '').toLowerCase();
});

function applyFilter(){
  var t = typeSel.value, a = agSel.value, s = q.value.trim().toLowerCase();
  var shown = 0;
  cands.forEach(function(el){
    // data-agency lists EVERY agency the candidate cites, so filtering by an agency
    // finds it even though the card renders under the first-cited agency's heading.
    var m = (!t || el.dataset.type === t) &&
            (!a || el.dataset.agency.split(' ').indexOf(a) !== -1) &&
            (!s || el.dataset.summaryLc.indexOf(s) !== -1);
    el.classList.toggle('hidden', !m);
    if (m) shown++;
  });
  secs.forEach(function(sec){
    sec.classList.toggle('hidden', !sec.querySelector('.cand:not(.hidden)'));
  });
  fcount.textContent = 'showing ' + shown.toLocaleString() + ' of ' +
    TOTAL.toLocaleString() + ' candidates';
}
typeSel.addEventListener('change', applyFilter);
agSel.addEventListener('change', applyFilter);
q.addEventListener('input', applyFilter);

document.addEventListener('click', function(ev){
  var t = ev.target;
  if (!(t && t.classList && t.classList.contains('qtoggle'))) return;
  var open = t.parentNode.classList.toggle('open');
  t.textContent = open ? 'collapse quote' : 'show full quote';
});
"""


def assert_dom_contract(page: str) -> None:
    """Every id the shipped script reads must exist in the markup, and every class it
    toggles must have a CSS rule behind it — asserted at build time because CI has no
    browser.

    The failure this catches (inherited from the old oregon-policy-repo renderer):
    `getElementById` returns null for a missing id, reading a property off null throws,
    and the script dies at that line taking every later behavior with it — the build
    prints success, the HTML is well-formed, and the page quietly loses its filters.
    Separately, `classList.toggle('hidden')` against a stylesheet with no matching rule
    sets an attribute and changes nothing visible: the count shrinks while every card
    stays on screen."""
    wanted = list(dict.fromkeys(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)",
                                           page)))
    present = set(re.findall(r"\bid=['\"]([^'\"]+)['\"]", page))
    missing = [w for w in wanted if w not in present]
    if missing:
        raise AssertionError(
            f"{SLUG}: script reads id(s) {missing} that the markup never defines — "
            f"getElementById returns null and the script dies there, taking every "
            f"later render with it")
    pairs = (("hidden", ".cand.hidden"), ("hidden", ".agsec.hidden"),
             ("open", ".doc.open"))
    unstyled = [sel for cls, sel in pairs
                if f"classList.toggle('{cls}'" in page and sel not in page]
    if unstyled:
        raise AssertionError(
            f"{SLUG}: script toggles a class with no CSS rule behind it — {unstyled} "
            f"absent from the stylesheet; the filter would report fewer candidates "
            f"while every card stays visible")


def _hbar(rows: list[tuple[str, int, str, str]], labw: int, aria: str) -> str:
    """Horizontal bars, house-style: direct labels left, count at the bar's end,
    thin 15px bars, tooltip payload in data attributes. rows = (label, n, fill, what)."""
    ROW, W = 26, 880
    barw = W - labw - 76
    vmax = max(n for _, n, _, _ in rows)
    parts = []
    for i, (label, n, fill, what) in enumerate(rows):
        y = 10 + i * ROW
        w = max(barw * n / vmax, 1.5)
        parts.append(f'<text x="{labw - 8}" y="{y + 12}" text-anchor="end" '
                     f'class="val">{esc(label)}</text>')
        parts.append(f'<rect x="{labw}" y="{y}" width="{w:.1f}" height="15" rx="2" '
                     f'fill="{fill}" data-n="{n}" data-what="{esc(what)}"/>')
        parts.append(f'<text x="{labw + w + 6:.1f}" y="{y + 12}">{n:,}</text>')
    H = 10 + ROW * len(rows) + 6
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(aria)}">'
            f'{"".join(parts)}</svg>')


def _qv_badge(v) -> str:
    # No per-badge title attribute: the one-line legend above the list explains all
    # three badges once. Repeating a ~130-char title on 2,954 badges cost ~0.4 MB.
    if v is True:
        return '<span class="qv qv-ok">verified in source</span>'
    if v == "absence":
        return '<span class="qv qv-abs">absence claim</span>'
    if v is False:
        return '<span class="qv qv-no">not found in source</span>'
    return ""


def build() -> tuple[str, str, str]:
    data = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/conflict_candidates.json",
                            "ERF conflict-candidates dataset"))
    # The mechanical dead-citation scan does not render here — it has other homes
    # (the county-code-cites-dead-law story; resolve_citation answers renumbered/
    # repealed sections directly). This page's single job is the model candidates.
    data.pop("mechanical", None)

    n_cand = data["n_candidates"]
    n_chapters = data["n_chapters"]
    names = {a["slug"]: a["name"] for a in data["all_agencies"]}
    names["unattributed"] = "No agency attributed"

    # Walk once: fold types, resolve agencies. A candidate citing several agencies'
    # rules RENDERS under the first-cited agency only (and is counted there, in both
    # the agency chart and the section headings) — duplicating the card would inflate
    # the corpus. The filter still finds it under any cited agency via data-agency.
    recs = []                       # (chapter, cand, type_key, slugs, first_slug)
    type_counts: Counter = Counter()
    agency_counts: Counter = Counter()
    by_agency: dict[str, list] = defaultdict(list)
    for ch in data["chapters"]:
        for c in ch["candidates"]:
            t = c.get("type") or "untyped"
            if t == "narrowing":            # two spellings across pilot batches
                t = "narrows"
            slugs = c.get("agency_slugs") or []
            first = slugs[0] if slugs else "unattributed"
            rec = (ch, c, t, slugs, first)
            recs.append(rec)
            type_counts[t] += 1
            agency_counts[first] += 1
            by_agency[first].append(rec)
    n_multi = sum(1 for _, _, _, slugs, _ in recs if len(slugs) > 1)

    # ---- chart A: candidates by model-assigned type (desc, untyped last + muted).
    typed = sorted((t for t in type_counts if t != "untyped"),
                   key=lambda t: (-type_counts[t], t))
    rows_a = [(TYPE_LABELS[t], type_counts[t], "var(--s1)",
               f"labeled “{TYPE_LABELS[t]}” by the model") for t in typed]
    if type_counts.get("untyped"):
        rows_a.append(("untyped", type_counts["untyped"], "var(--muted)",
                       "carrying no type label from the model"))
    svg_types = _hbar(rows_a, 150, "Candidates by model-assigned type")

    # ---- chart B: top-12 agencies by candidate count (first-cited-agency basis).
    ag_ranked = sorted((s for s in agency_counts if s != "unattributed"),
                       key=lambda s: (-agency_counts[s], names[s]))
    rows_b = []
    for s in ag_ranked[:12]:
        name = names[s]
        label = name if len(name) <= 44 else name[:43].rstrip() + "…"
        rows_b.append((label, agency_counts[s], "var(--s1)",
                       f"filed under {name} (first-cited agency)"))
    svg_agencies = _hbar(rows_b, 330, "Top 12 agencies by candidate count")
    n_more_ag = len(ag_ranked) - 12

    # ---- the list, grouped by agency, most candidates first; unattributed last.
    order = sorted((s for s in by_agency if s != "unattributed"),
                   key=lambda s: (-agency_counts[s], names[s]))
    if "unattributed" in by_agency:
        order.append("unattributed")

    sections = []
    for slug in order:
        group = by_agency[slug]
        cards = []
        for ch, c, t, slugs, _ in group:
            tags = []
            if t != "untyped":
                tags.append(f'<span class="tag">{esc(TYPE_LABELS[t])}</span>')
            if c.get("severity"):                      # severity tag ONLY when graded
                sev = c["severity"]
                tags.append(f'<span class="tag"><span class="dot" '
                            f'style="background:{SEV_DOT[sev]}"></span>'
                            f'severity {esc(sev)} (model)</span>')
            if c.get("cites_repealed"):
                tags.append('<span class="tag" title="A cited rule has since been '
                            'repealed — a repealed rule binds nobody">cites repealed '
                            'rule</span>')
            chref = f'ORS {esc(str(ch["ors_chapter"]))}'
            if slug != "unattributed":
                chref += f' · {esc(names[slug])}’s rules'
            tags.append(f'<span class="chref">{chref}</span>')

            docs = []
            for d in c["documents"]:
                quote = d.get("quote") or ""
                cite = esc(d.get("citation") or d.get("id") or "")
                if d.get("not_found"):
                    cite += " — not found in corpus"
                toggle = ('<button class="qtoggle" type="button">show full quote'
                          '</button>' if len(quote) > CLAMP_AT else "")
                docs.append(f'<div class="doc"><cite>{cite}</cite>'
                            f'{_qv_badge(d.get("quote_verified"))}'
                            f'<div class="quote">{esc(quote)}</div>{toggle}</div>')

            note = (f'<div class="cnote">{esc(c["note"])}</div>'
                    if c.get("note") else "")
            cards.append(
                f'<div class="cand" data-type="{esc(t)}" '
                f'data-agency="{esc(" ".join(slugs) or "unattributed")}">'
                f'<p class="csum">{esc(c["summary"])}</p>'
                f'<div class="tagline">{"".join(tags)}</div>'
                f'{"".join(docs)}{note}</div>')

        n = len(group)
        meta = f'{n:,} candidate{"s" if n != 1 else ""}'
        if slug == "unattributed":
            meta += (" · the pilot did not attribute these to a specific "
                     "agency’s rules")
        sections.append(f'<section class="agsec" data-agency="{esc(slug)}">'
                        f'<h2>{esc(names[slug])}</h2>'
                        f'<p class="agmeta">{meta}</p>{"".join(cards)}</section>')

    # ---- filter bar (options mirror the data-type / data-agency values).
    type_opts = ['<option value="">all types</option>']
    for label, cnt, _, _ in rows_a:
        key = next(k for k, v in TYPE_LABELS.items() if v == label)
        type_opts.append(f'<option value="{esc(key)}">{esc(label)} ({cnt})</option>')
    ag_opts = ['<option value="">all agencies</option>']
    for a in sorted(data["all_agencies"], key=lambda a: a["name"]):
        ag_opts.append(f'<option value="{esc(a["slug"])}">{esc(a["name"])}</option>')
    if "unattributed" in by_agency:
        ag_opts.append('<option value="unattributed">no agency attributed</option>')
    filterbar = (
        f'<div class="panel filterbar">'
        f'<label for="typesel">type</label><select id="typesel">{"".join(type_opts)}'
        f'</select>'
        f'<label for="agsel">agency</label><select id="agsel">{"".join(ag_opts)}'
        f'</select>'
        f'<label for="q">search</label>'
        f'<input id="q" type="search" placeholder="search summaries">'
        f'<span id="fcount">showing {n_cand:,} of {n_cand:,} candidates</span></div>')

    listhead = (
        f'<div class="listhead"><h2>All {n_cand:,} candidates, grouped by agency</h2>'
        f'<p>Every card below is model-produced and human-unreviewed — stated '
        f'here once rather than repeated on each card. Each candidate is filed under '
        f'the first agency whose rules it cites ({n_multi} cite more than one '
        f'agency’s rules; the agency filter finds those under any of them).</p>'
        f'</div>'
        f'<p class="qlegend">Quote badges: '
        f'<span class="qv qv-ok">verified in source</span> the exact words are in '
        f'the cited document · <span class="qv qv-abs">absence claim</span> the '
        f'point is what the source omits, so there is nothing to match · '
        f'<span class="qv qv-no">not found in source</span> read the source before '
        f'relying on it.</p>')

    body = (
        _CSS
        + f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Candidates '
          f'by model-assigned type</h2>{svg_types}</div>'
        + f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Where they '
          f'cluster: top 12 agencies by candidate count</h2>{svg_agencies}'
          f'<p class="agmore">…and {n_more_ag} more agencies with at least one '
          f'candidate. Counted by first-cited agency.</p></div>'
        + filterbar + listhead + "".join(sections))

    # The guardrail sentence IS the lede: the first body text under the title, bold,
    # one sentence — counts and legends live elsewhere by design.
    lede = (f'<strong>Every item on this page is a candidate for human and legal '
            f'review, produced by a model reading statutes against their '
            f'implementing rules — none is a confirmed conflict, and all '
            f'{n_cand:,} are currently unreviewed.</strong>')

    sev = data["severity_counts"]
    tri = data["triage_counts"]
    rules_total = sum(ch.get("rules_reviewed") or 0 for ch in data["chapters"])
    n_graded = n_cand - sev.get("ungraded", 0)
    caveats = (
        f"<p><b>Coverage is a pilot, not a sweep.</b> The model read {n_chapters} "
        f"ORS chapters — those in the shared-authority set, where multiple "
        f"agencies implement the same statute — reviewing {rules_total:,} rules; "
        f"{data.get('n_clean_chapters', 0)} chapters came back with no candidates. "
        f"The rest of the ORS is simply unexamined, so absence from this page is not "
        f"evidence of consistency. <b>Quotes were checked against the corpus "
        f"mechanically:</b> of {data['n_docs_verified']:,} quoted passages, "
        f"{data['n_quotes_grounded']:,} were found verbatim in the cited document, "
        f"{data['n_quotes_absence_claim']} assert an omission (nothing to match), and "
        f"{data['n_quotes_ungrounded']} could not be located verbatim — read "
        f"those against the source before relying on them. <b>Severity is mostly "
        f"absent and never human:</b> {sev.get('ungraded', 0):,} of {n_cand:,} "
        f"candidates carry no grade at all, and the {n_graded} that do were graded "
        f"by the model, not a person. <b>Human triage stands at "
        f"{tri.get('unreviewed', 0):,} unreviewed, {tri.get('confirmed', 0)} "
        f"confirmed, {tri.get('dismissed', 0)} dismissed.</b> "
        f"{data.get('n_candidates_citing_repealed', 0)} candidates rest on a rule "
        f"that has since been repealed (tagged on the card) — a repealed rule "
        f"binds nobody. <b>Publishing this page (2026-08-03, an operator decision) "
        f"publishes candidates, not findings</b>: presence here is not evidence that "
        f"a conflict exists, and nothing here is legal advice or legal review.</p>"
        f"<details><summary>Full provenance note and methodology</summary>"
        f"<p>{esc(data.get('note') or '')}</p>"
        f"<p><b>Methodology:</b> {esc(data.get('methodology') or '')}</p>"
        f"<p>Dataset retrieved {esc(data.get('retrieved') or '')}.</p></details>")

    title = (f"Where the rules may not match the statutes: {n_cand:,} candidates "
             f"awaiting human review")
    page = viz.chart_page(
        title=title,
        eyebrow="oregon-stories · from the executive-regulatory-frameworks "
                "corpus · AI-assisted pilot",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(),
        script=f"var TOTAL = {n_cand};" + _SCRIPT)
    assert_dom_contract(page)
    claim = (f"{n_cand:,} candidate statute/rule inconsistencies across "
             f"{n_chapters} ORS chapters — every one awaiting human review, "
             f"none a finding")
    return SLUG, claim, page

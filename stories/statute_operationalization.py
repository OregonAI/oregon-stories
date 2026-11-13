"""Story: statute operationalization — which ORS chapters Oregon's administrative rules
(OAR) implement most, and which agencies do the implementing. Port of ERF's
src/build_statute_fan.py (oregon-stories#2): renders here on corpus_toolkit.viz, reading
ERF's PUBLISHED artifacts (_meta/graph.json for the rule<->statute edges, the agency
registry for who owns an OAR chapter, the ORS catalog for chapter titles) rather than
that corpus's own viz/statute-operationalization.html page, which is not a runtime
dependency.

A port, not a redesign: the same ranked bars (length = implementing links, segmented by
the four largest implementing agencies), the same filter, the same "dormant tail"
toggle for chapters implemented by only 1-2 rules, the same hover detail.

COVERAGE, STATED ON THE PAGE: a chapter that no mapped rule cites is not on this chart
at all, and "no edge in the graph" is a statement about the graph, not about the law.
"""
from __future__ import annotations

import datetime
import html
import json
from collections import Counter, defaultdict

import yaml

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "statute-operationalization"
TOP_AGENCIES = 4      # segments drawn per bar (ERF's own cut)
TAIL_MAX = 2          # "dormant tail" = chapters implemented by this many rules or fewer
UNASSIGNED = "(unassigned)"


def _chapter_of(ors_id: str) -> str:
    """'ors-743a.052' -> '743a' (the ORS chapter, letter suffix kept)."""
    return ors_id.split("-")[1].split(".")[0]


def rank_chapters(edges: list[dict], orgs: list[dict],
                  chapters: list[dict]) -> tuple[list[dict], int]:
    """(rows, total_links). One row per ORS chapter with at least one implementing OAR
    rule, most-implemented first; `top` is the four largest implementing agencies
    (named as the registry's statutory `name`, "Department of" abbreviated as ERF
    does), `agencies` counts them all. A rule whose OAR chapter the registry does not
    carry is counted under "(unassigned)", never dropped."""
    by_oar = {o["oar_chapter"]: o for o in orgs if o.get("oar_chapter")}
    titles = {c["chapter"].lower(): c.get("title", "") for c in chapters}
    total: Counter = Counter()
    by_agency: dict[str, Counter] = defaultdict(Counter)
    for e in edges:
        if e["type"] != "implemented_by" or not e["from"].startswith("ors-") \
                or not e["to"].startswith("oar-"):
            continue
        ch = _chapter_of(e["from"])
        org = by_oar.get(e["to"].split("-")[1])
        agency = (org.get("name") or org["slug"]) if org else UNASSIGNED
        total[ch] += 1
        by_agency[ch][agency] += 1
    rows = []
    for ch, n in total.most_common():
        rows.append({"ch": ch.upper(), "title": titles.get(ch, ""), "n": n,
                     "agencies": len(by_agency[ch]),
                     "top": [{"a": a.replace("Department of ", "Dept. of "), "n": c}
                             for a, c in by_agency[ch].most_common(TOP_AGENCIES)]})
    return rows, sum(total.values())


def link_stats(edges: list[dict]) -> dict:
    """The same edges the bars count, three ways: links (what a bar's length is),
    distinct OAR rules, and distinct (ORS chapter, rule) pairs (what 'rules per
    chapter' would be). The page states all three so the unit is never ambiguous."""
    links, rules, pairs = 0, set(), set()
    for e in edges:
        if e["type"] != "implemented_by" or not e["from"].startswith("ors-") \
                or not e["to"].startswith("oar-"):
            continue
        links += 1
        rules.add(e["to"])
        pairs.add((_chapter_of(e["from"]), e["to"]))
    return {"links": links, "rules": len(rules), "chapter_rule_pairs": len(pairs)}


SCRIPT = """
var D = __DATA__;
var TAIL = __TAIL__;
var tip = document.getElementById('tip');
var list = document.getElementById('list');
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function fmt(n){ return n.toLocaleString(); }
function render(){
  var q = document.getElementById('q').value.toLowerCase().trim();
  var tail = document.getElementById('tail').checked;
  var out = [], shown = 0;
  D.rows.forEach(function(r, ri){
    if (!tail && r.n <= TAIL) return;
    if (q && ('ors ' + r.ch + ' ' + r.title).toLowerCase().indexOf(q) < 0) return;
    shown++;
    var segs = r.top.map(function(t, i){
      return '<div style="height:100%;width:' + (t.n / r.n * 100) + '%;background:var(--s' +
             (i + 1) + ')"></div>'; }).join('');
    out.push('<div class="orow" data-i="' + ri + '">' +
      '<div class="och"><b>ORS ' + esc(r.ch) + '</b><small>' + esc(r.title) + '</small></div>' +
      '<div class="otrack"><div class="obar" style="width:' +
        Math.max(r.n / D.max * 100, 0.6) + '%">' + segs + '</div></div>' +
      '<div class="ocnt">' + fmt(r.n) + '<small>' + r.agencies + ' ' +
        (r.agencies === 1 ? 'agency' : 'agencies') + '</small></div></div>');
  });
  list.innerHTML = out.join('') ||
    '<p style="color:var(--muted)">No chapters match.</p>';
}
list.addEventListener('mousemove', function(ev){
  var el = ev.target.closest('.obar'); if (!el) { tip.style.display = 'none'; return; }
  var r = D.rows[+el.parentNode.parentNode.getAttribute('data-i')];
  var parts = r.top.map(function(t, i){
    return '<div><span style="color:var(--s' + (i + 1) + ')">\\u25a0</span> ' +
           esc(t.a) + ' \\u2014 ' + t.n + '</div>'; }).join('');
  var more = r.agencies > r.top.length ?
    '<div>+' + (r.agencies - r.top.length) + ' more agencies</div>' : '';
  tip.innerHTML = '<b>ORS ' + esc(r.ch) + (r.title ? ' \\u00b7 ' + esc(r.title) : '') +
    '</b><div>' + fmt(r.n) + ' rule-to-section links</div>' + parts + more;
  tip.style.display = 'block';
  tip.style.left = Math.min(ev.clientX + 13, innerWidth - 300) + 'px';
  tip.style.top = Math.min(ev.clientY + 13, innerHeight - 120) + 'px';
});
list.addEventListener('mouseleave', function(){ tip.style.display = 'none'; });
document.getElementById('q').addEventListener('input', render);
document.getElementById('tail').addEventListener('change', render);
render();
"""

CSS = """<style>
.octl{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:0 0 10px}
.octl input[type=search]{padding:7px 10px;border:1px solid var(--border);border-radius:8px;
  background:var(--surface);color:var(--ink);font-size:14px;min-width:240px}
.octl label{font-size:13px;color:var(--muted)}
.orow{display:grid;grid-template-columns:150px 1fr 76px;gap:12px;align-items:center;
  padding:5px 0;border-bottom:1px solid var(--grid)}
.och small,.ocnt small{display:block;font-weight:400;color:var(--muted);font-size:11.5px;
  line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ocnt{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}
.otrack{height:22px;background:var(--grid);border-radius:5px;overflow:hidden}
.obar{height:100%;display:flex}
</style>"""


def render(rows: list[dict], total_links: int, stats: dict | None = None,
           sources: list[dict] | None = None,
           generated: str = "") -> str:
    data = {"rows": rows, "max": rows[0]["n"] if rows else 1}
    script = (SCRIPT.replace("__DATA__", json.dumps(data, ensure_ascii=False,
                                                     separators=(",", ":")).replace("</", "<\\/"))
                    .replace("__TAIL__", str(TAIL_MAX)))
    n_tail = sum(1 for r in rows if r["n"] <= TAIL_MAX)
    body = (CSS +
            '<div class="panel"><div class="octl">'
            '<input type="search" id="q" placeholder="Filter by ORS chapter or title…">'
            f'<label><input type="checkbox" id="tail"> show the dormant tail '
            f'(1\u2013{TAIL_MAX} links; {n_tail} chapters)</label></div>'
            '<div id="list"></div></div>')
    lede = (f"{len(rows):,} ORS chapters are linked from {total_links:,} OAR "
            f"rule-to-section links. Bar length = links into the chapter, segmented by "
            f"the four largest implementing agencies. Non-authoritative.")
    unit = ""
    if stats:
        unit = (f" In the mirror's graph, {stats['links']:,} links run between "
                f"{stats['rules']:,} distinct rules and the chapters they cite "
                f"({stats['chapter_rule_pairs']:,} chapter\u2013rule pairs), so read a "
                f"bar as volume of citation, not as a count of rules.")
    caveats = (
        "<p><b>This counts rule-to-statute links in a mechanically derived graph, not "
        "legal effect.</b> Each OAR rule's cited authority is linked to the ORS chapter "
        "it names. THE UNIT IS A LINK, NOT A RULE: one link per (ORS section, OAR rule) "
        "pair, so a rule citing three sections of one chapter adds three, and a rule "
        "citing several chapters adds to each." + unit + " A chapter that no mapped rule cites does not "
        "appear here at all, and absence from the graph is not evidence that no rule "
        "implements it. “Dormant tail” means only that one or two links "
        "point at the chapter. Agencies are named by the registry's statutory name and "
        "attributed by the rule's OAR chapter; a rule whose OAR chapter is not in the "
        "registry shows as “(unassigned)”. Non-authoritative — verify "
        "against the statutes and rules themselves.</p>")
    return viz.chart_page(
        title="Which Oregon statutes get operationalized",
        eyebrow="oregon-stories · executive-regulatory-frameworks",
        lede_html=html.escape(lede), body_html=body, caveats_html=caveats,
        sources=sources if sources is not None else sources_for_footer(),
        generated=generated or datetime.date.today().isoformat(), script=script)


def build() -> tuple[str, str, str]:
    graph = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/graph.json",
                             "ERF authority graph (rule-to-statute edges)"))
    reg = yaml.safe_load(fetch(f"{RAW}/{ERF}/main/_meta/catalog/agencies.yml",
                               "ERF agency registry"))["organizations"]
    ors = yaml.safe_load(fetch(f"{RAW}/{ERF}/main/_meta/catalog/ors.yml",
                               "ERF ORS chapter catalog (titles)"))["chapters"]
    rows, total = rank_chapters(graph["edges"], reg, ors)
    stats = link_stats(graph["edges"])
    return SLUG, (f"{len(rows):,} ORS chapters are cited by {total:,} rule-to-section "
                  f"links, most heavily ORS {rows[0]['ch']}" if rows else "no links"), \
        render(rows, total, stats)

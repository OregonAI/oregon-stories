"""Story: regulatory freshness — the functional age of Oregon's rule and policy body,
set against how far each lags the last amendment of the statute it implements. Port of
ERF's src/build_freshness.py (oregon-stories#2): renders here on corpus_toolkit.viz,
reading ERF's committed _meta/freshness.json cache (the published data artifact that
script itself reads) rather than that corpus's own viz/regulatory-freshness.html page.

A scatter (rule-filed year vs its authority statute's last-amendment year — the
diagonal is "in sync") carries every datable rule; an agency ranking and a "most worth
reviewing" list surface the pattern a 42k-point cloud can't. FLAG and NOW are read at
build time, not hand-maintained — the lag threshold is the same editorial call ERF's
page makes (10+ years is "worth reviewing", never "stale" or "a violation"), and the
in-progress year moves forward with every rebuild instead of going stale in a constant.
"""
from __future__ import annotations

import datetime
import html
import json
import statistics
from collections import defaultdict

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "regulatory-freshness"
FLAG = 10          # years a rule/policy may lag its authority before it's "worth reviewing"
XMIN = 1955        # scatter axis floor


def gap_years(doc: dict) -> int | None:
    """How many years the statute's last amendment leads the rule's own last filing, or
    None when either side is undatable — never treated as fresh or stale (ERF's rule)."""
    yr, ay = doc.get("yr"), doc.get("ay")
    if yr is None or ay is None:
        return None
    return ay - yr


def agency_table(rules: list[dict], policies: list[dict], flag: int = FLAG,
                 now: int | None = None) -> list[dict]:
    """One row per agency: how many of its rules are datable, how many sit `flag`+
    years behind their authority, and the median age of its datable rules — the
    ranking panel's data, grouped the way ERF's build_freshness.py groups it."""
    now = now or datetime.date.today().year
    ag: dict[str, dict] = defaultdict(lambda: {"nr": 0, "nd": 0, "l10": 0, "ages": [],
                                               "np": 0, "pages": []})
    for r in rules:
        a = ag[r.get("ag") or "(unattributed)"]
        a["nr"] += 1
        if r.get("yr") is not None:
            a["ages"].append(now - r["yr"])
            g = gap_years(r)
            if g is not None:
                a["nd"] += 1
                if g >= flag:
                    a["l10"] += 1
    for p in policies:
        a = ag[p.get("ag") or "(unattributed)"]
        a["np"] += 1
        if p.get("yr") is not None:
            a["pages"].append(now - p["yr"])
    out = []
    for name, a in ag.items():
        out.append({"name": name, "nr": a["nr"], "nd": a["nd"], "l10": a["l10"],
                    "med": round(statistics.median(a["ages"])) if a["ages"] else None,
                    "np": a["np"],
                    "pmed": round(statistics.median(a["pages"])) if a["pages"] else None})
    return out


def top_offenders(rules: list[dict], policies: list[dict], titles: dict[str, str],
                  flag: int = FLAG, limit: int = 120) -> list[dict]:
    """The `limit` rules/policies with the largest statute-vs-rule gap, `flag`+ years
    only — "most worth reviewing", sorted worst first. Never a finding: a flag means a
    rule is worth a human look, not that it is out of compliance (ERF's caveat)."""
    items = []
    for kind, docs in (("rule", rules), ("policy", policies)):
        for d in docs:
            g = gap_years(d)
            if g is not None and g >= flag:
                items.append({"id": d["id"], "kind": kind, "yr": d["yr"], "ay": d["ay"],
                             "sid": d.get("sid"), "gap": g,
                             "title": titles.get(d["id"], ""),
                             "sid_title": titles.get(d.get("sid") or "", "")})
    items.sort(key=lambda o: (-o["gap"], -(o["ay"] or 0)))
    return items[:limit]


def cite(doc_id: str | None) -> str:
    if not doc_id:
        return "—"
    if doc_id.startswith("ors-"):
        return "ORS " + doc_id[4:]
    if doc_id.startswith("oar-"):
        return "OAR " + doc_id[4:].replace("-", " ")
    return doc_id.upper()


def build() -> tuple[str, str, str]:
    fr = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/freshness.json",
                          "ERF regulatory-freshness dataset"))
    rules, policies = fr["rules"], fr["policies"]
    flagged_ids = {o["id"] for o in top_offenders(rules, policies, {}, limit=10**9)}
    needed = set()
    for kind, docs in (("rule", rules), ("policy", policies)):
        for d in docs:
            if d["id"] in flagged_ids:
                needed.add(d["id"])
                if d.get("sid"):
                    needed.add(d["sid"])
    graph = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/graph.json",
                             "ERF authority graph (titles for flagged items only)"))
    titles = {n["id"]: n.get("title", "") for n in graph["nodes"] if n["id"] in needed}

    now = datetime.date.today().year
    ags = agency_table(rules, policies, now=now)
    ranked = sorted([a for a in ags if a["nd"] >= 40],
                    key=lambda a: (a["l10"] / a["nd"]) if a["nd"] else 0, reverse=True)
    offenders = top_offenders(rules, policies, titles, limit=120)

    n_datable = sum(1 for r in rules if gap_years(r) is not None)
    n_flagged = sum(a["l10"] for a in ags)
    pct = round(n_flagged / n_datable * 100) if n_datable else 0

    # Agency plays no part in the drawn scatter (it drives the ranking table instead,
    # already computed server-side) — carrying it per point would roughly double this
    # payload for data the script never reads.
    scatter = {"r": [[r["yr"], r["ay"]] for r in rules if r.get("yr") and r.get("ay")]}

    rank_rows = "".join(
        f'<tr><td>{html.escape(a["name"])}</td>'
        f'<td class="num">{round(a["l10"]/a["nd"]*100) if a["nd"] else 0}%</td>'
        f'<td class="num">{a["nd"]:,}</td>'
        f'<td class="num">{a["med"] if a["med"] is not None else "—"}y</td></tr>'
        for a in ranked[:20])
    rank_table = (f'<table><thead><tr><th>agency</th><th class="num">{FLAG}+ yrs '
                 f'behind</th><th class="num">datable rules</th>'
                 f'<th class="num">median age</th></tr></thead>'
                 f'<tbody>{rank_rows}</tbody></table>')

    def _off_row(o: dict) -> str:
        title = (f'<br><small>{html.escape(o["title"][:90])}</small>' if o["title"] else "")
        kind = ' <small>(policy)</small>' if o["kind"] == "policy" else ""
        sid_title = f' · {html.escape(o["sid_title"][:60])}' if o["sid_title"] else ""
        return (f'<tr><td>+{o["gap"]}y</td><td>{cite(o["id"])}{kind}{title}</td>'
               f'<td>{o["yr"]} → implements {cite(o["sid"])}, amended '
               f'{o["ay"]}{sid_title}</td></tr>')

    off_rows = "".join(_off_row(o) for o in offenders[:40])
    off_table = (f'<table><thead><tr><th>gap</th><th>document</th>'
                f'<th>filed → authority last amended</th></tr></thead>'
                f'<tbody>{off_rows}</tbody></table>')

    script = """
var D = __DATA__;
var cv = document.getElementById('scatter'), ctx = cv.getContext('2d');
function X(yr, w){ return (yr - %(xmin)d) / (%(now)d - %(xmin)d) * w; }
function Y(yr, h){ return h - (yr - %(xmin)d) / (%(now)d - %(xmin)d) * h; }
function gapColor(g){
  if (g >= 20) return 'var(--s4)';
  if (g >= %(flag)d) return 'var(--s2)';
  if (g >= 3) return 'var(--s3)';
  return 'var(--muted)';
}
function draw(){
  var w = cv.clientWidth, h = 260;
  cv.width = w; cv.height = h; ctx.clearRect(0,0,w,h);
  ctx.strokeStyle = 'var(--border)'; ctx.globalAlpha = 0.6;
  ctx.beginPath(); ctx.moveTo(X(%(xmin)d,w), Y(%(xmin)d,h));
  ctx.lineTo(X(%(now)d,w), Y(%(now)d,h)); ctx.stroke(); ctx.globalAlpha = 1;
  for (var i = 0; i < D.r.length; i++){
    var ry = D.r[i][0], ay = D.r[i][1], g = ay - ry;
    ctx.fillStyle = gapColor(g);
    var s = g >= %(flag)d ? 2.6 : 2;
    ctx.fillRect(X(ay,w) - s/2, Y(ry,h) - s/2, s, s);
  }
}
draw(); addEventListener('resize', draw);
""" % {"xmin": XMIN, "now": now, "flag": FLAG}
    script = script.replace("__DATA__", json.dumps(scatter, separators=(",", ":")))

    body = (
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Rule filed vs. '
        f'authority last amended — the diagonal is "in sync"</h2>'
        f'<canvas id="scatter" style="width:100%;height:260px;display:block"></canvas>'
        f'<p class="legend" style="margin:8px 0 0">'
        f'<span><span class="chip" style="background:var(--s4)"></span>20+ yrs behind</span>'
        f'<span><span class="chip" style="background:var(--s2)"></span>{FLAG}–19 yrs behind</span>'
        f'<span><span class="chip" style="background:var(--s3)"></span>3–9 yrs behind</span>'
        f'<span><span class="chip" style="background:var(--muted)"></span>in sync / &lt;3 yrs</span>'
        f'</p></div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Agencies with '
        f'≥40 datable rules, ranked by share {FLAG}+ years behind</h2>{rank_table}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Most worth '
        f'reviewing — largest gap first, top 40 of {len(offenders):,} flagged'
        f'</h2>{off_table}</div>')

    caveats = (
        f'<p><b>A flag means "worth reviewing", never "stale" or "a violation."</b> A '
        f'rule implements a range of statutes; the gap uses the most-recently-amended '
        f'SPECIFIC authority among them (a statute cited by more than 75 rules is '
        f'treated as a broad enabling provision and never the counted authority), so a '
        f'flag can land on a rule even though the amended section was not the part it '
        f'actually relies on. Year is each document\'s own `effective_date` '
        f'(rule/policy) or its last `[YYYY c.N …]` legislative-history bracket '
        f'(statute); a document missing either is excluded from the scatter and the '
        f'ranking’s denominators, counted nowhere as fresh or stale. '
        f'Non-authoritative — verify any flagged document against its own current '
        f'text.</p>')

    lede = (f"{n_datable:,} of Oregon's rules carry a datable filing year against a "
            f"datable authority; {n_flagged:,} of them ({pct}%) sit {FLAG}+ years "
            f"behind the statute they implement — worth a look, not a verdict.")

    page = viz.chart_page(
        title=f"Regulatory freshness: {pct}% of datable Oregon rules sit {FLAG}+ "
              f"years behind their statute",
        eyebrow="oregon-stories · executive-regulatory-frameworks",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=datetime.date.today().isoformat(), script=script)
    return SLUG, (f"{n_flagged:,} rules ({pct}%) sit {FLAG}+ years behind the statute "
                  f"they implement"), page

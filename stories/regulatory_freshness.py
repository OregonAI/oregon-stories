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

KNOWN CUT (flagged for operator sign-off, oregon-stories#2 code review): ERF's
build_freshness.py lets a reader click an agency in the ranking panel to filter the
scatter and the "most worth reviewing" list to just that agency. This port keeps the
ranking table, the full scatter (with decade gridlines, axis labels, the diagonal, the
FLAG threshold line and its shaded region, and a hover tooltip) and the offender list,
but does not wire agency selection between them — ERF's own page carries a per-point
agency index for that, which would roughly double this payload for an interaction the
chart-card layout here has no seam for yet. Nothing is hidden: every flagged document
is still in the table.
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
    # payload for data the script never reads. id/sid ARE carried (short strings) so a
    # hover can name the actual document instead of drawing an unlabeled point.
    datable_rules = [r for r in rules if r.get("yr") and r.get("ay")]
    scatter = {"ry": [r["yr"] for r in datable_rules],
              "ay": [r["ay"] for r in datable_rules],
              "id": [r["id"] for r in datable_rules],
              "sid": [r.get("sid") or "" for r in datable_rules]}

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
var tip = document.getElementById('tip');
function cssv(n){ return getComputedStyle(document.body).getPropertyValue(n).trim(); }
function cite(id){ if (!id) return '\\u2014';
  if (id.indexOf('ors-') === 0) return 'ORS ' + id.slice(4);
  if (id.indexOf('oar-') === 0) return 'OAR ' + id.slice(4).replace(/-/g,' ');
  return id.toUpperCase(); }
var ML = 52, MR = 16, MT = 14, MB = 36;
function X(ay, w){ return ML + (ay - %(xmin)d) / (%(now)d - %(xmin)d) * (w - ML - MR); }
function Y(yr, h){ return h - MB - (yr - %(xmin)d) / (%(now)d - %(xmin)d) * (h - MT - MB); }
function gapColor(g){
  if (g >= 20) return cssv('--s4');
  if (g >= %(flag)d) return cssv('--s2');
  if (g >= 3) return cssv('--s3');
  return cssv('--muted');
}
var DPR = Math.min(2, window.devicePixelRatio || 1), pts = [];
function draw(){
  var w = cv.clientWidth, h = 260;
  cv.width = w * DPR; cv.height = h * DPR; ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, w, h);
  var x0 = ML, x1 = w - MR, y0 = h - MB, y1 = MT;
  // FLAG threshold region: a rule/policy >= FLAG years behind its authority
  ctx.fillStyle = cssv('--s2'); ctx.globalAlpha = 0.07;
  ctx.beginPath();
  ctx.moveTo(X(%(xmin)d + %(flag)d, w), Y(%(xmin)d, h));
  ctx.lineTo(X(%(now)d, w), Y(%(now)d - %(flag)d, h));
  ctx.lineTo(X(%(now)d, w), Y(%(xmin)d, h));
  ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
  // decade gridlines + ticks
  ctx.strokeStyle = cssv('--grid'); ctx.fillStyle = cssv('--muted');
  ctx.font = '11px system-ui'; ctx.lineWidth = 1;
  ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  for (var yr = 1960; yr <= %(now)d; yr += 10){
    var px = X(yr, w);
    ctx.beginPath(); ctx.moveTo(px, y1); ctx.lineTo(px, y0); ctx.stroke();
    ctx.fillText(yr, px, y0 + 6);
  }
  ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
  for (var yr2 = 1960; yr2 <= %(now)d; yr2 += 10){
    var py = Y(yr2, h);
    ctx.beginPath(); ctx.moveTo(x0, py); ctx.lineTo(x1, py); ctx.stroke();
    ctx.fillText(yr2, x0 - 6, py);
  }
  // diagonal (in sync) + FLAG threshold line
  ctx.strokeStyle = cssv('--border'); ctx.globalAlpha = 0.6;
  ctx.beginPath(); ctx.moveTo(X(%(xmin)d, w), Y(%(xmin)d, h));
  ctx.lineTo(X(%(now)d, w), Y(%(now)d, h)); ctx.stroke();
  ctx.globalAlpha = 0.35; ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(X(%(xmin)d + %(flag)d, w), Y(%(xmin)d, h));
  ctx.lineTo(X(%(now)d, w), Y(%(now)d - %(flag)d, h));
  ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
  // axis labels
  ctx.fillStyle = cssv('--muted'); ctx.font = '600 11px system-ui';
  ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
  ctx.fillText('STATUTE last amended \\u2192', (x0 + x1) / 2, h - 4);
  ctx.save(); ctx.translate(12, (y0 + y1) / 2); ctx.rotate(-Math.PI / 2);
  ctx.textBaseline = 'top'; ctx.fillText('RULE last filed \\u2192', 0, 0); ctx.restore();
  // points
  pts = [];
  for (var i = 0; i < D.ry.length; i++){
    var ry = D.ry[i], ay = D.ay[i], g = ay - ry;
    ctx.fillStyle = gapColor(g);
    var s = g >= %(flag)d ? 2.6 : 2;
    var px2 = X(ay, w), py2 = Y(ry, h);
    ctx.fillRect(px2 - s/2, py2 - s/2, s, s);
    pts.push([px2, py2, i]);
  }
}
draw(); addEventListener('resize', draw);
function nearest(mx, my){
  var best = -1, bd = 36;
  for (var j = 0; j < pts.length; j++){
    var dx = pts[j][0] - mx, dy = pts[j][1] - my, d = dx*dx + dy*dy;
    if (d < bd){ bd = d; best = pts[j][2]; }
  }
  return best;
}
cv.addEventListener('mousemove', function(ev){
  var r = cv.getBoundingClientRect(), k = nearest(ev.clientX - r.left, ev.clientY - r.top);
  if (k < 0){ tip.style.display = 'none'; return; }
  var ry = D.ry[k], ay = D.ay[k], g = ay - ry;
  tip.innerHTML = '<b>' + cite(D.id[k]) + '</b> filed ' + ry +
    '<br><i>implements ' + cite(D.sid[k]) + ' \\u2014 last amended ' + ay + '</i>' +
    '<br><i style="color:' + gapColor(g) + '">' +
    (g > 0 ? ('+' + g + ' yrs behind') : (g === 0 ? 'in sync' : ((-g) + ' yrs ahead'))) + '</i>';
  tip.style.display = 'block';
  tip.style.left = Math.min(ev.clientX + 13, innerWidth - 300) + 'px';
  tip.style.top = Math.min(ev.clientY + 13, innerHeight - 90) + 'px';
});
cv.addEventListener('mouseleave', function(){ tip.style.display = 'none'; });
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
        f'reviewing — largest gap first, top 40 of {len(flagged_ids):,} flagged'
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

"""Story: policy age — how long since each ERF-mirrored internal policy, procedure,
standard, or manual was last touched, against a stated 2-year internal review cadence.
Port of ERF's src/build_policy_age.py (oregon-stories#2): renders here on
corpus_toolkit.viz, reading ERF's committed _meta/policy_age.json cache (plus the
agency catalog for display names) rather than that corpus's own
viz/policy-age.html page.

Unlike regulatory-freshness, this clock is ABSOLUTE, not statute-relative: a document
is "due" or "overdue" purely by how long it has sat since its own last filing or
review, which is why age is recomputed here from each doc's `last_touched` date at
OUR build time rather than carried over from whenever ERF's cache happened to be
refreshed — the same document should not read a different age just because this page
rebuilt on a different day than ERF's did.
"""
from __future__ import annotations

import datetime
import html
import json
from collections import defaultdict

import yaml

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "policy-age"
DUE_YEARS = 2        # ERF's stated internal review cadence
OVERDUE_YEARS = 4     # twice the cadence — a firmer "this has been missed" line
KINDS = ("policy", "procedure", "standard", "manual")


def age_years(last_touched: str | None, today: datetime.date) -> float | None:
    """Years since `last_touched` (an ISO date string), or None when the document
    carries no datable touch at all — never defaulted to 0 or dropped silently."""
    if not last_touched:
        return None
    y, m, d = (int(x) for x in last_touched.split("-"))
    return round((today - datetime.date(y, m, d)).days / 365.25, 2)


def agency_table(docs: list[dict], due: float = DUE_YEARS, overdue: float = OVERDUE_YEARS,
                 today: datetime.date | None = None) -> list[dict]:
    """One row per agency: how many of its documents are dated, and how many sit at or
    past the due / overdue thresholds."""
    today = today or datetime.date.today()
    agg: dict[str, dict] = defaultdict(lambda: {"total": 0, "dated": 0, "due": 0,
                                                "overdue": 0, "ages": []})
    for x in docs:
        a = agg[x.get("agency") or "(unattributed)"]
        a["total"] += 1
        age = age_years(x.get("last_touched"), today)
        if age is None:
            continue
        a["dated"] += 1
        a["ages"].append(age)
        if age >= overdue:
            a["overdue"] += 1
        elif age >= due:
            a["due"] += 1
    out = []
    for name, a in agg.items():
        ages = sorted(a["ages"])
        med = ages[len(ages) // 2] if ages else None
        out.append({"agency": name, "total": a["total"], "dated": a["dated"],
                    "due": a["due"], "overdue": a["overdue"], "med": med})
    return out


def most_overdue(docs: list[dict], overdue: float = OVERDUE_YEARS,
                 today: datetime.date | None = None, limit: int = 150) -> list[dict]:
    """The `limit` documents with the largest age, `overdue`+ years only — oldest
    first."""
    today = today or datetime.date.today()
    items = []
    for x in docs:
        age = age_years(x.get("last_touched"), today)
        if age is not None and age >= overdue:
            items.append({**x, "age": age})
    items.sort(key=lambda x: -x["age"])
    return items[:limit]


def build() -> tuple[str, str, str]:
    d = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/policy_age.json",
                         "ERF policy-age dataset"))
    reg = yaml.safe_load(fetch(f"{RAW}/{ERF}/main/_meta/catalog/agencies.yml",
                               "ERF agency registry"))["organizations"]
    names = {o["slug"]: o.get("name", o["slug"]) for o in reg}
    today = datetime.date.today()

    docs = [dict(x, agency=names.get(x.get("agency") or "", x.get("agency") or "")
                 or "(unattributed)")
            for x in d["docs"]]

    ags = agency_table(docs, today=today)
    ranked = sorted([a for a in ags if a["dated"] >= 3],
                    key=lambda a: ((a["due"] + a["overdue"]) / a["dated"]) if a["dated"] else 0,
                    reverse=True)
    overdue_list = most_overdue(docs, today=today)

    n_dated = sum(a["dated"] for a in ags)
    n_due = sum(a["due"] for a in ags)
    n_overdue = sum(a["overdue"] for a in ags)
    pct = round((n_due + n_overdue) / n_dated * 100) if n_dated else 0

    rank_rows = "".join(
        f'<tr><td>{html.escape(a["agency"])}</td>'
        f'<td class="num">{round((a["due"]+a["overdue"])/a["dated"]*100) if a["dated"] else 0}%</td>'
        f'<td class="num">{a["dated"]:,}</td>'
        f'<td class="num">{a["med"] if a["med"] is not None else "—"}y</td></tr>'
        for a in ranked[:20])
    rank_table = (f'<table><thead><tr><th>agency</th><th class="num">due or overdue</th>'
                 f'<th class="num">dated docs</th><th class="num">median age</th></tr>'
                 f'</thead><tbody>{rank_rows}</tbody></table>')

    def _age_dot(age: float) -> str:
        if age >= OVERDUE_YEARS:
            return "var(--s4)"
        if age >= DUE_YEARS:
            return "var(--s3)"
        return "var(--s1)"

    off_rows = "".join(
        f'<tr><td style="color:{_age_dot(o["age"])}">{o["age"]:.1f}y</td>'
        f'<td><a href="{html.escape(o.get("source_url") or "#")}">'
        f'{html.escape(o.get("citation") or o["id"].upper())}</a>'
        f'<br><small>{html.escape(o.get("title", ""))}</small></td>'
        f'<td>{html.escape(o["agency"])}<br><small>{o["doc_type"]}</small></td></tr>'
        for o in overdue_list[:40])
    off_table = (f'<table><thead><tr><th>age</th><th>document</th><th>agency</th></tr>'
                f'</thead><tbody>{off_rows}</tbody></table>')

    # Lean beeswarm payload: age + a doc_type row index + a flat index into `docid` for
    # the tooltip — no titles or citations inline (those render server-side in the
    # table above; the chart only needs to draw and identify a point on hover).
    kind_i = {k: i for i, k in enumerate(KINDS)}
    swarm = [[round(age_years(x["last_touched"], today), 2), kind_i.get(x["doc_type"], 0), i]
            for i, x in enumerate(docs) if x.get("last_touched")]
    docid = [x["id"] for x in docs if x.get("last_touched")]
    cite = [x.get("citation") or x["id"].upper() for x in docs if x.get("last_touched")]

    script = """
var D = __DATA__;
var KINDS = %(kinds)s, DUE = %(due)s, OVERDUE = %(overdue)s;
var cv = document.getElementById('swarm'), ctx = cv.getContext('2d');
var tip = document.getElementById('swarm-tip');
var maxAge = 1; D.pts.forEach(function(p){ if (p[0] > maxAge) maxAge = p[0]; });
maxAge = Math.ceil(maxAge) + 1;
var ML = 64, MR = 12, MT = 10, MB = 28;
function ageColor(a){ return a >= OVERDUE ? 'var(--s4)' : a >= DUE ? 'var(--s3)' : 'var(--s1)'; }
function X(a, w){ return ML + (a / maxAge) * (w - ML - MR); }
function rowY(k, h){ var rows = KINDS.length, rh = (h - MT - MB) / rows; return MT + rh * (k + 0.5); }
function jitter(i, h){ var rows = KINDS.length, rh = (h - MT - MB) / rows, span = rh * 0.6;
  var x = Math.sin(i * 12.9898) * 43758.5453; return ((x - Math.floor(x)) - 0.5) * span; }
var pts = [];
function draw(){
  var w = cv.clientWidth, h = 220; cv.width = w; cv.height = h;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = 'var(--muted)'; ctx.font = '11px system-ui'; ctx.textAlign = 'right';
  KINDS.forEach(function(k, i){ ctx.fillText(k, ML - 8, rowY(i, h) + 4); });
  ctx.textAlign = 'center';
  for (var yr = 0; yr <= maxAge; yr += 2) ctx.fillText(yr + 'y', X(yr, w), h - 8);
  pts = [];
  for (var i = 0; i < D.pts.length; i++){
    var age = D.pts[i][0], k = D.pts[i][1], px = X(age, w), py = rowY(k, h) + jitter(i, h);
    ctx.fillStyle = ageColor(age);
    ctx.fillRect(px - 1.5, py - 1.5, 3, 3);
    pts.push([px, py, i]);
  }
}
draw(); addEventListener('resize', draw);
cv.addEventListener('pointermove', function(ev){
  var r = cv.getBoundingClientRect(), mx = ev.clientX - r.left, my = ev.clientY - r.top;
  var best = -1, bd = 36;
  for (var j = 0; j < pts.length; j++){
    var dx = pts[j][0] - mx, dy = pts[j][1] - my, d = dx*dx + dy*dy;
    if (d < bd){ bd = d; best = pts[j][2]; }
  }
  if (best < 0){ tip.style.display = 'none'; return; }
  var age = D.pts[best][0], kind = KINDS[D.pts[best][1]], idx = D.pts[best][2];
  tip.innerHTML = '<b>' + D.cite[idx] + '</b> &middot; ' + kind +
    '<br>' + age + ' years since last touched';
  tip.style.display = 'block';
  tip.style.left = Math.min(ev.clientX + 12, innerWidth - 260) + 'px';
  tip.style.top = (ev.clientY + 12) + 'px';
});
cv.addEventListener('pointerleave', function(){ tip.style.display = 'none'; });
""" % {"kinds": json.dumps(list(KINDS)), "due": DUE_YEARS, "overdue": OVERDUE_YEARS}
    script = script.replace("__DATA__", json.dumps(
        {"pts": swarm, "cite": cite}, separators=(",", ":")))

    body = (
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Years since '
        f'last touched, by document kind</h2>'
        f'<canvas id="swarm" style="width:100%;height:220px;display:block"></canvas>'
        f'<p class="legend" style="margin:8px 0 0">'
        f'<span><span class="chip" style="background:var(--s1)"></span>current '
        f'(&lt;{DUE_YEARS}y)</span>'
        f'<span><span class="chip" style="background:var(--s3)"></span>due '
        f'({DUE_YEARS}–{OVERDUE_YEARS}y)</span>'
        f'<span><span class="chip" style="background:var(--s4)"></span>overdue '
        f'({OVERDUE_YEARS}y+)</span></p></div>'
        f'<div style="position:relative"><div id="swarm-tip" style="display:none;'
        f'position:fixed;pointer-events:none;background:var(--panel);'
        f'border:1px solid var(--border);border-radius:8px;padding:6px 9px;'
        f'font-size:12.5px;z-index:9;max-width:260px"></div></div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Agencies with '
        f'≥3 dated documents, ranked by share due or overdue</h2>{rank_table}</div>'
        f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Most overdue for '
        f'review — oldest first, top 40 of {len(overdue_list):,}</h2>{off_table}</div>')

    caveats = (
        f'<p><b>This clock is absolute, not statute-relative</b> (unlike the '
        f'regulatory-freshness story): age is time since the document\'s own '
        f'`effective_date` (or `last_reviewed` if later) against the '
        f'{DUE_YEARS}-year internal review cadence ERF\'s own documentation states, '
        f'regardless of whether the law it implements has changed. `last_reviewed` is '
        f'populated for only a small share of these documents, so age mostly reduces '
        f'to the last filing date. A document with neither date is counted as unknown '
        f'— never assumed current or overdue — and is excluded from every '
        f'denominator above. Non-authoritative; verify against each document\'s own '
        f'source_url.</p>')

    lede = (f"{n_dated:,} of ERF's mirrored policies, procedures, standards and "
            f"manuals carry a datable last-touched date; {n_due + n_overdue:,} of them "
            f"({pct}%) are due or overdue for the {DUE_YEARS}-year review ERF's own "
            f"documentation calls for, {n_overdue:,} of those overdue by twice that.")

    page = viz.chart_page(
        title=f"Policy age: {pct}% of ERF's dated internal documents are due or "
              f"overdue for review",
        eyebrow="oregon-stories · executive-regulatory-frameworks",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=today.isoformat(), script=script)
    return SLUG, (f"{n_due + n_overdue:,} documents ({pct}%) are due or overdue for "
                  f"the {DUE_YEARS}-year internal review cadence"), page

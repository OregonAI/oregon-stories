"""Story: the agency shared-statutory-authority graph — two agencies are linked when
their administrative rules implement the same ORS statute chapters, thicker links for
more SPECIALIZED shared domains (ubiquitous statutes like the APA count less). Port of
ERF's src/build_agency_graph.py (oregon-stories#2): the page is self-contained (the
whole point was no server round-trip for the density/ubiquity controls), so it renders
here on corpus_toolkit.viz with the SAME client-side force layout and edge projection,
reading ERF's committed _meta/agency-graph.json cache rather than depending on that
corpus's own viz/agency-authority-graph.html page.

Two pieces exist as Python here even though they RUN client-side: `edge_weight` (the
discount a shared ORS chapter's popularity gets, 1/ln(pop+e) — ERF's own formula,
recomputed in the browser on every density-slider move) is pinned by a test against an
independently worked value, but that test exercises only this Python copy — nothing
ties it to the JS, which is the one that actually runs at render time, so a change to
either side alone would go unnoticed. `top_groups` (the house categorical-palette rule:
at most 8 color slots, a 9th department folds into "other" rather than cycling colors
or inventing a 9th hue) runs server-side for real and its result (plus `slot_index`,
the legend-order slot each kept group's nodes must draw in) is passed into the payload,
so that one genuinely is single-sourced.
"""
from __future__ import annotations

import datetime
import html
import json
import math

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "agency-authority-graph"
COLOR_SLOTS = 8   # the house categorical-palette cap (viz.CATEGORICAL_* has 8 slots)


def edge_weight(pop: int) -> float:
    """1/ln(pop + e) — ERF's discount for a shared ORS chapter cited by `pop` agencies;
    the browser recomputes this exact formula on every density/ubiquity change, so this
    copy exists to be tested against, not to run at render time."""
    return 1 / math.log(pop + math.e)


def top_groups(colored_groups: list[dict], slots: int = COLOR_SLOTS) -> tuple[list[dict], int]:
    """The `slots` largest colored departments (by member count) keep a dedicated
    color; every other colored department folds into "other, grouped" alongside true
    standalone agencies — the house rule against cycling a categorical palette past its
    validated slot count. Returns (kept, number of departments folded)."""
    ordered = sorted(colored_groups, key=lambda g: -g["members"])
    return ordered[:slots], max(0, len(ordered) - slots)


def slot_index(kept_groups: list[dict]) -> dict[str, int]:
    """The 1-based legend slot for each kept group's `slug`, in exactly the order the
    legend lists them (`top_groups`' own order — largest member count first). The
    browser must color a node by this same slot, never by first appearance in the
    agency list, or the graph's colors stop matching the legend."""
    return {g["slug"]: i for i, g in enumerate(kept_groups, 1)}


def build() -> tuple[str, str, str]:
    d = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/agency-graph.json",
                         "ERF agency shared-statutory-authority graph"))
    kept_groups, n_folded = top_groups(d["colored_groups"])
    kept_slugs = {g["slug"] for g in kept_groups}
    kept_slot = slot_index(kept_groups)

    n_agencies = d["counts"]["agencies"]
    n_chapters = d["counts"]["ors_chapters"]
    top3 = sorted(d["colored_groups"], key=lambda g: -g["members"])[:3]
    top3_text = ", ".join(f'{html.escape(g["name"])} ({g["members"]})' for g in top3)

    n_other_agencies = sum(1 for a in d["agencies"] if a["group"] not in kept_slugs)
    legend_rows = "".join(
        f'<span><span class="chip" style="background:var(--s{i})"></span>'
        f'{html.escape(g["name"])} ({g["members"]})</span>'
        for i, g in enumerate(kept_groups, 1))
    if n_other_agencies:
        legend_rows += (f'<span><span class="chip" style="background:var(--muted)">'
                        f'</span>other departments / standalone ({n_other_agencies})'
                        f'</span>')

    # Payload: the published artifact trimmed to what the force layout + tooltip need
    # (drop the long free-text `note`, already stated in the lede/caveats).
    payload = {
        "agencies": [{"slug": a["slug"], "name": a["name"], "rules": a["rules"],
                     "group": a["group"] if a["group"] in kept_slugs else None,
                     "slot": kept_slot.get(a["group"]),
                     "groupName": a["group_name"] if a["group"] in kept_slugs
                                 else "Other / standalone",
                     "gov": a["governance"], "chapters": a["chapters"]}
                    for a in d["agencies"]],
        "chapter_pop": d["chapter_pop"],
        "ubiquity_default": d["ubiquity_default"],
        "n_groups": len(kept_groups),
    }

    script = """
var DATA = __DATA__;
var wrap = document.getElementById('graph-wrap');
var cv = document.getElementById('graph-cv'), ctx = cv.getContext('2d');
var tip = document.getElementById('graph-tip');
function cssv(n){ return getComputedStyle(document.body).getPropertyValue(n).trim(); }

var W = 0, H = 0, DPR = Math.min(2, window.devicePixelRatio || 1);
var view = {x: 0, y: 0, k: 1};
var nodes = [], links = [], hover = null, selected = null, dragNode = null,
    panning = false, last = null, T = 0.9;

function resize(){
  var w = cv.clientWidth, h = cv.clientHeight; if (!w || !h) return;
  W = w; H = h; cv.width = W * DPR; cv.height = H * DPR;
}
new ResizeObserver(resize).observe(cv);

function buildNodes(){
  var cx = W/2, cy = H/2;
  nodes = DATA.agencies.map(function(a, i){
    var ang = i / DATA.agencies.length * Math.PI * 2;
    return {id: a.slug, name: a.name, rules: a.rules, group: a.group, slot: a.slot,
            groupName: a.groupName, gov: a.gov, chapters: a.chapters,
            chSet: new Set(a.chapters),
            x: cx + Math.cos(ang)*220 + (Math.random()-.5)*40,
            y: cy + Math.sin(ang)*220 + (Math.random()-.5)*40,
            vx: 0, vy: 0, r: Math.min(26, 4 + Math.sqrt(a.rules)*1.15)};
  });
}

function weight(pop){ return 1 / Math.log((pop || 1) + Math.E); }

function projectEdges(){
  var includeUbiq = document.getElementById('graph-ubiq').checked;
  var pop = DATA.chapter_pop, UB = DATA.ubiquity_default;
  var all = [], strongest = {};
  for (var i = 0; i < nodes.length; i++){
    for (var j = i+1; j < nodes.length; j++){
      var A = nodes[i], B = nodes[j], w = 0, shared = 0;
      var small = A.chSet.size < B.chSet.size ? A.chSet : B.chSet;
      var big = A.chSet.size < B.chSet.size ? B.chSet : A.chSet;
      small.forEach(function(c){
        if (big.has(c)){
          if (!includeUbiq && (pop[c]||0) >= UB) return;
          w += weight(pop[c]); shared++;
        }
      });
      if (shared > 0){
        var e = {a: A, b: B, w: w, shared: shared};
        all.push(e);
        if (!strongest[A.id] || strongest[A.id].w < w) strongest[A.id] = e;
        if (!strongest[B.id] || strongest[B.id].w < w) strongest[B.id] = e;
      }
    }
  }
  all.sort(function(p, q){ return q.w - p.w; });
  var maxW = all.length ? all[0].w : 1;
  var dens = +document.getElementById('graph-dens').value;
  var cutoff = maxW * Math.pow(1 - dens/100, 1.6);
  var keep = new Set(); Object.keys(strongest).forEach(function(k){ keep.add(strongest[k]); });
  links = all.filter(function(e){ return e.w >= cutoff || keep.has(e); });
  document.getElementById('graph-stat').textContent =
    nodes.length + ' agencies \\u00b7 ' + links.length + ' links shown (of ' + all.length + ')';
}

function relayout(){ buildNodes(); projectEdges(); T = 0.9; }
function reproject(){ projectEdges(); T = Math.max(T, 0.4); }

function step(){
  var rep = 6800, cx = W/2, cy = H/2;
  nodes.forEach(function(n){ n.vx *= 0.86; n.vy *= 0.86; });
  for (var i = 0; i < nodes.length; i++){
    var a = nodes[i];
    for (var j = i+1; j < nodes.length; j++){
      var b = nodes[j];
      var dx = a.x-b.x, dy = a.y-b.y, d2 = dx*dx+dy*dy+0.01, d = Math.sqrt(d2);
      if (d > 360) continue;
      var f = rep/d2, fx = dx/d*f, fy = dy/d*f;
      a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
    }
  }
  links.forEach(function(e){
    var dx = e.b.x-e.a.x, dy = e.b.y-e.a.y, d = Math.hypot(dx,dy)+.01, ideal = 70;
    var f = (d-ideal)*0.015*(0.5+Math.min(e.w,3)), fx = dx/d*f, fy = dy/d*f;
    e.a.vx += fx; e.a.vy += fy; e.b.vx -= fx; e.b.vy -= fy;
  });
  nodes.forEach(function(n){
    n.vx += (cx-n.x)*0.006; n.vy += (cy-n.y)*0.006;
    if (n === dragNode) return;
    n.x += n.vx*T; n.y += n.vy*T;
  });
  if (T > 0.05) T *= 0.992;
}

function toScreen(x, y){ return [(x-view.x)*view.k, (y-view.y)*view.k]; }
function draw(){
  ctx.setTransform(DPR,0,0,DPR,0,0); ctx.clearRect(0,0,W,H);
  var egoSet = null;
  if (selected){ egoSet = new Set([selected.id]);
    links.forEach(function(e){ if (e.a===selected) egoSet.add(e.b.id);
                               if (e.b===selected) egoSet.add(e.a.id); }); }
  ctx.lineCap = 'round';
  links.forEach(function(e){
    var p1 = toScreen(e.a.x,e.a.y), p2 = toScreen(e.b.x,e.b.y);
    var hi = selected && (e.a===selected||e.b===selected);
    var dim = (selected && !hi) || (hover && e.a!==hover && e.b!==hover && !hi);
    ctx.strokeStyle = hi ? cssv('--s4') : cssv('--axis');
    ctx.globalAlpha = hi?0.85 : dim?0.06:0.6;
    ctx.lineWidth = Math.max(.5, Math.min(4, e.w*0.9)) * (hi?1.5:1);
    ctx.beginPath(); ctx.moveTo(p1[0],p1[1]); ctx.lineTo(p2[0],p2[1]); ctx.stroke();
  });
  ctx.globalAlpha = 1;
  nodes.forEach(function(n){
    var p = toScreen(n.x,n.y), r = n.r*Math.sqrt(view.k);
    var faded = (egoSet && !egoSet.has(n.id)) || (hover && hover!==n && !(egoSet&&egoSet.has(n.id)));
    ctx.globalAlpha = faded?0.22:1;
    ctx.beginPath(); ctx.arc(p[0],p[1],r,0,7);
    ctx.fillStyle = n.slot ? cssv('--s' + n.slot) : cssv('--muted');
    ctx.fill();
    ctx.lineWidth = (n===hover||n===selected) ? 2 : 1;
    ctx.strokeStyle = (n===hover||n===selected) ? cssv('--ink') : cssv('--surface');
    ctx.stroke();
  });
  ctx.globalAlpha = 1;
  ctx.fillStyle = cssv('--ink'); ctx.font = '600 11px system-ui'; ctx.textAlign = 'center';
  nodes.forEach(function(n){
    var show = n===hover || n===selected || (egoSet && egoSet.has(n.id)) ||
      (n.rules > 1200 && view.k > 0.7);
    if (!show) return;
    var p = toScreen(n.x,n.y);
    var label = n.name.length > 34 ? n.name.slice(0,32)+'\\u2026' : n.name;
    ctx.globalAlpha = (egoSet && !egoSet.has(n.id)) ? 0.3 : 1;
    ctx.fillText(label, p[0], p[1] - n.r*Math.sqrt(view.k) - 5);
  });
  ctx.globalAlpha = 1;
}

function frame(){ step(); draw(); requestAnimationFrame(frame); }

function nodeAt(mx, my){
  var best = null, bd = 1e9;
  nodes.forEach(function(n){
    var p = toScreen(n.x,n.y), r = n.r*Math.sqrt(view.k)+4;
    var d = Math.hypot(mx-p[0], my-p[1]);
    if (d < r && d < bd){ bd = d; best = n; }
  });
  return best;
}
function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function topPartners(n){
  return links.filter(function(e){ return e.a===n||e.b===n; })
    .sort(function(p,q){ return q.w-p.w; }).slice(0,3)
    .map(function(e){ return esc((e.a===n?e.b:e.a).name); }).join(', ');
}
cv.addEventListener('mousemove', function(ev){
  var r = cv.getBoundingClientRect(), mx = ev.clientX-r.left, my = ev.clientY-r.top;
  if (dragNode){ dragNode.x = mx/view.k+view.x; dragNode.y = my/view.k+view.y;
    dragNode.vx = dragNode.vy = 0; T = Math.max(T,0.3); return; }
  if (panning){ view.x -= (mx-last[0])/view.k; view.y -= (my-last[1])/view.k; last=[mx,my]; return; }
  hover = nodeAt(mx, my);
  cv.style.cursor = hover ? 'pointer' : 'grab';
  if (hover){
    var partners = topPartners(hover);
    tip.innerHTML = '<b>' + esc(hover.name) + '</b><br>' + hover.rules.toLocaleString() +
      ' rules \\u00b7 ' + hover.chapters.length + ' ORS chapters \\u00b7 ' +
      esc(hover.gov.replace(/_/g,' ')) +
      (partners ? '<br><span style="color:var(--muted)">shares most with: ' + partners + '</span>' : '');
    tip.style.display = 'block';
    tip.style.left = Math.min(ev.clientX+14, innerWidth-300) + 'px';
    tip.style.top = Math.min(ev.clientY+14, innerHeight-100) + 'px';
  } else tip.style.display = 'none';
});
cv.addEventListener('mousedown', function(ev){
  var r = cv.getBoundingClientRect(), n = nodeAt(ev.clientX-r.left, ev.clientY-r.top);
  if (n){ dragNode = n; } else { panning = true; last = [ev.clientX-r.left, ev.clientY-r.top]; }
});
addEventListener('mouseup', function(){ dragNode = null; panning = false; });
cv.addEventListener('click', function(ev){
  var r = cv.getBoundingClientRect(), n = nodeAt(ev.clientX-r.left, ev.clientY-r.top);
  selected = (n && n !== selected) ? n : null;
});
cv.addEventListener('wheel', function(ev){
  ev.preventDefault();
  var r = cv.getBoundingClientRect(), mx = ev.clientX-r.left, my = ev.clientY-r.top;
  var wx = mx/view.k+view.x, wy = my/view.k+view.y;
  var f = Math.exp(-ev.deltaY*0.0012); view.k = Math.max(0.25, Math.min(4, view.k*f));
  view.x = wx-mx/view.k; view.y = wy-my/view.k;
}, {passive: false});
document.getElementById('graph-dens').addEventListener('input', reproject);
document.getElementById('graph-ubiq').addEventListener('change', reproject);
document.getElementById('graph-search').addEventListener('input', function(e){
  var q = e.target.value.toLowerCase().trim();
  if (!q){ selected = null; return; }
  var hit = nodes.find(function(n){ return n.name.toLowerCase().indexOf(q) >= 0; });
  if (hit){ selected = hit; view.k = 1.1; view.x = hit.x-W/2/view.k; view.y = hit.y-H/2/view.k; }
});
resize(); relayout(); frame();
if (W > 0) for (var i = 0; i < 220; i++) step();
""".replace("__DATA__", json.dumps(payload, separators=(",", ":")))

    body = (
        f'<div class="panel" id="graph-wrap" style="position:relative;height:560px;'
        f'padding:0;overflow:hidden">'
        f'<canvas id="graph-cv" style="position:absolute;inset:0;width:100%;'
        f'height:100%;cursor:grab"></canvas>'
        f'<div style="position:absolute;top:10px;left:10px;background:var(--surface);'
        f'border:1px solid var(--border);border-radius:10px;padding:10px 12px;'
        f'width:230px;font-size:12.5px">'
        f'<input id="graph-search" placeholder="Find an agency…" '
        f'style="width:100%;padding:5px 7px;border:1px solid var(--border);'
        f'border-radius:6px;background:var(--page);color:var(--ink);font-size:12.5px">'
        f'<label style="display:flex;justify-content:space-between;margin:8px 0 2px;'
        f'color:var(--muted)">Link density</label>'
        f'<input id="graph-dens" type="range" min="0" max="100" value="62" '
        f'style="width:100%">'
        f'<label style="display:flex;align-items:center;gap:6px;margin:6px 0 0">'
        f'<input id="graph-ubiq" type="checkbox"> include ubiquitous statutes (APA, '
        f'public records…)</label>'
        f'<div id="graph-stat" style="color:var(--muted);margin-top:6px"></div></div>'
        f'<div style="position:absolute;bottom:10px;left:10px;background:var(--surface);'
        f'border:1px solid var(--border);border-radius:10px;padding:8px 10px;'
        f'max-width:280px"><p class="legend" style="margin:0">{legend_rows}</p></div>'
        f'<div id="graph-tip" style="display:none;position:fixed;pointer-events:none;'
        f'background:var(--surface);border:1px solid var(--border);border-radius:8px;'
        f'padding:8px 10px;font-size:12.5px;max-width:280px;z-index:9"></div>'
        f'<div style="position:absolute;bottom:10px;right:10px;font-size:11px;'
        f'color:var(--muted);background:var(--surface);border:1px solid var(--border);'
        f'border-radius:8px;padding:5px 9px">drag to pan · scroll to zoom · '
        f'click a node to isolate it · drag a node to pin</div></div>')

    caveats = (
        f'<p>{html.escape(d["note"])}</p>'
        f'<p><b>Color caps at {len(kept_groups)} departments</b> (the house categorical '
        f'palette\'s validated slot count): the {len(kept_groups)} largest colored '
        f'groupings by member count keep a dedicated color; the other {n_folded} '
        f'colored department(s) and every standalone agency share the neutral "other" '
        f'color — a position on the graph, not an erased identity (the tooltip and node '
        f'size are unaffected). Edge weight sums 1/ln(chapter_pop + e) over shared ORS '
        f'chapters, so a chapter nearly every agency implements (the APA, public '
        f'records law) counts for little; the "include ubiquitous statutes" toggle '
        f'turns that discount off.</p>')

    lede = (f"{n_agencies} Oregon agencies, linked whenever their administrative rules "
            f"implement the same ORS statute chapters — {n_chapters} chapters "
            f"across the graph. The three largest colored departments by member "
            f"agencies: {top3_text}.")

    page = viz.chart_page(
        title=f"The agency authority graph: {n_agencies} agencies linked by "
              f"{n_chapters} shared ORS chapters",
        eyebrow="oregon-stories · executive-regulatory-frameworks",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=datetime.date.today().isoformat(), script=script)
    return SLUG, (f"{n_agencies} agencies linked by shared statutory authority across "
                  f"{n_chapters} ORS chapters"), page

"""Story: WHERE the stale law lives — the staleness lag painted onto the semantic map
of the whole rulebook.

Sources: ERF's committed 2D projection of its embedding space (the same UMAP cache
its own topic map renders from) and its freshness dataset. Every rule becomes a dot
placed by MEANING; color carries how far its statute has moved since the rule was
last amended. If stale law clustered nowhere, staleness would be noise; where it
pools, whole domains have been left behind together.
"""
from __future__ import annotations

import json

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "the-map-of-stale-law"

# Sequential single-hue ramp (the house magnitude rule): light -> dark blue by lag.
BUCKETS = ((0, "#c9c8c1"), (1, "#9ec5f4"), (5, "#5598e7"), (10, "#256abf"),
           (20, "#0d366b"))


def build() -> tuple[str, str, str]:
    proj = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/embeddings/projection.2d.json",
                            "ERF committed 2D projection (UMAP cache)"))
    fresh = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/freshness.json",
                             "ERF regulatory-freshness dataset"))
    lag_of = {r["id"]: (r["ay"] - r["yr"]) if r.get("ay") and r.get("yr") else None
              for r in fresh["rules"]}

    # Doc-level point: the rule's first chunk's coordinates.
    seen = set()
    pts = []
    n_unknown = 0
    for i, did in enumerate(proj["ids"]):
        if not did.startswith("oar-") or did in seen:
            continue
        seen.add(did)
        lag = lag_of.get(did)
        if lag is None:
            n_unknown += 1
            continue
        b = 0
        for bi, (lo, _) in enumerate(BUCKETS):
            if lag >= lo:
                b = bi
        pts.append((proj["x"][i], proj["y"][i], b))
    grid = proj.get("grid", 4095)

    payload = {"g": grid, "p": [[x, y, b] for x, y, b in pts],
               "colors": [c for _, c in BUCKETS]}
    script = """
var D = __DATA__;
var cv = document.getElementById('map'), ctx = cv.getContext('2d');
function draw(){
  var s = cv.clientWidth; cv.width = s; cv.height = s;
  ctx.clearRect(0,0,s,s);
  // recessive first, stalest last, so the dark pools sit on top
  for (var pass = 0; pass < D.colors.length; pass++){
    ctx.fillStyle = D.colors[pass];
    ctx.globalAlpha = pass === 0 ? 0.35 : 0.8;
    for (var i = 0; i < D.p.length; i++){
      if (D.p[i][2] !== pass) continue;
      var x = D.p[i][0] / D.g * s, y = D.p[i][1] / D.g * s;
      ctx.fillRect(x, y, 1.6, 1.6);
    }
  }
  ctx.globalAlpha = 1;
}
draw(); addEventListener('resize', draw);
""".replace("__DATA__", json.dumps(payload, separators=(",", ":")))

    counts = [0] * len(BUCKETS)
    for _, _, b in pts:
        counts[b] += 1
    labels = ["statute has not moved since", "1–4 years behind", "5–9 years behind",
              "10–19 years behind", "20+ years behind"]
    legend = "".join(
        f'<span><span class="chip" style="background:{c}"></span>{lab} '
        f'<b>({n:,})</b></span>'
        for (_, c), lab, n in zip(BUCKETS, labels, counts))

    n10 = counts[3] + counts[4]
    lede = (f"Every dot is one of {len(pts):,} administrative rules, placed by what it "
            f"MEANS — the same learned map the corpus's topic explorer uses — and "
            f"shaded by how many years its authorizing statute has moved since the "
            f"rule was last amended. Staleness is not sprinkled evenly: the dark "
            f"pools are whole domains ({n10:,} rules 10+ years behind) that aged "
            f"together, which is exactly what a modernization effort would want a "
            f"map of.")

    caveats = (
        "<p><b>Position is learned, not authoritative:</b> the 2D layout is a UMAP "
        "projection of text embeddings — distances are suggestive, axes mean nothing, "
        "and neighborhoods are the only readable unit. A lag is a candidate signal, "
        "not a violation (the staleness story's caveat applies dot by dot). "
        f"{n_unknown:,} rules lack a datable year on one side and are not drawn — "
        "absence from this map is missing data, never currency. Colors are one "
        "sequential hue by magnitude; the lightest gray marks rules whose statute has "
        "not moved since their last amendment.</p>")

    body = (f'<div class="panel"><div class="legend">{legend}</div>'
            f'<canvas id="map" style="width:100%;aspect-ratio:1;display:block">'
            f'</canvas></div>')

    page = viz.chart_page(
        title="The map of stale law: where Oregon's left-behind rules pool together",
        eyebrow="oregon-stories · the semantic map × the freshness dataset",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    return SLUG, (f"{len(pts):,} rules mapped by meaning, shaded by staleness — "
                  f"the {n10:,} left-behind rules pool in visible domains"), page

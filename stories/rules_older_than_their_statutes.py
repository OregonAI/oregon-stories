"""Story: thousands of Oregon administrative rules are older than the statutes they
implement — the mechanical staleness signal, no model judgment anywhere.

Data: ERF's _meta/freshness.json (built and CI-gated in that repo), one row per OAR
rule: rule id, agency, rule's last-amendment year (yr), its authorizing statute (sid)
and that statute's latest-amendment year (ay). Lag = ay - yr where positive: the
statute moved after the rule last did.
"""
from __future__ import annotations

import html
import json
from collections import Counter

from corpus_toolkit import viz
from data_sources import RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
ERF_BLOB = f"https://github.com/OregonAI/{ERF}/blob/main"

SLUG = "rules-older-than-their-statutes"


def rule_link(rid: str) -> str:
    # oar-101-001-0000 -> rules/101/001/oar-101-001-0000.md
    _, ch, div, _ = rid.split("-", 3)
    return f"{ERF_BLOB}/rules/{ch}/{div}/{rid}.md"


def build() -> tuple[str, str, str]:
    data = json.loads(fetch(f"{RAW}/{ERF}/main/_meta/freshness.json",
                            "ERF regulatory-freshness dataset"))
    rules = data["rules"]
    datable = [r for r in rules if r.get("yr") and r.get("ay")]
    lagged = [dict(r, lag=r["ay"] - r["yr"]) for r in datable if r["ay"] > r["yr"]]
    n10 = sum(1 for r in lagged if r["lag"] >= 10)

    # Histogram of lag years, 1..cap with a folded tail.
    CAP = 40
    hist = Counter(min(r["lag"], CAP) for r in lagged)
    W, H, PL, PB = 880, 300, 44, 40
    bw = (W - PL - 16) / CAP
    vmax = max(hist.values())
    ytop = ((vmax // 200) + 1) * 200
    bars = []
    for lag in range(1, CAP + 1):
        v = hist.get(lag, 0)
        bh = (H - PB - 16) * v / ytop
        x0, y0 = PL + (lag - 1) * bw, H - PB - bh
        # 4px rounded data-end, square baseline; 2px surface gap via width inset
        bars.append(f'<path d="M{x0+1:.1f} {H-PB} v{-max(bh-4,0):.1f} '
                    f'q0 -4 4 -4 h{bw-10:.1f} q4 0 4 4 v{max(bh-4,0):.1f} z" '
                    f'fill="var(--s1)" data-lag="{lag}" data-n="{v}"/>'
                    if bh > 4 else
                    f'<rect x="{x0+1:.1f}" y="{y0:.1f}" width="{bw-2:.1f}" '
                    f'height="{bh:.1f}" fill="var(--s1)" data-lag="{lag}" data-n="{v}"/>')
    ticks = "".join(
        f'<line x1="{PL}" y1="{H-PB-(H-PB-16)*t/ytop:.1f}" x2="{W-16}" '
        f'y2="{H-PB-(H-PB-16)*t/ytop:.1f}" stroke="var(--grid)"/>'
        f'<text x="{PL-8}" y="{H-PB-(H-PB-16)*t/ytop+4:.1f}" text-anchor="end">{t:,}</text>'
        for t in range(0, ytop + 1, 200))
    xlabels = "".join(f'<text x="{PL+(x-0.5)*bw:.1f}" y="{H-14}" text-anchor="middle">'
                      f'{x}{"+" if x == CAP else ""}</text>'
                      for x in (1, 5, 10, 15, 20, 25, 30, 35, CAP))
    shade_x = PL + 9 * bw
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Rules by years of lag '
           f'behind their statute">{ticks}'
           f'<rect x="{shade_x:.1f}" y="14" width="{W-16-shade_x:.1f}" height="{H-PB-14}" '
           f'fill="var(--s1)" opacity="0.07"/>'
           f'<text x="{shade_x+6:.1f}" y="30" class="val">10+ years: {n10:,} rules</text>'
           f'{"".join(bars)}'
           f'<line x1="{PL}" y1="{H-PB}" x2="{W-16}" y2="{H-PB}" stroke="var(--axis)"/>'
           f'{xlabels}'
           f'<text x="{(PL+W)/2:.0f}" y="{H-1}" text-anchor="middle">years the statute '
           f'has moved since the rule was last amended</text></svg>')

    top = sorted(lagged, key=lambda r: -r["lag"])[:20]
    rows = "".join(
        f'<tr><td><a href="{rule_link(r["id"])}">{r["id"].replace("oar-","OAR ")}</a></td>'
        f'<td>{html.escape(str(r.get("ag") or "—"))}</td>'
        f'<td><a href="{ERF_BLOB}/statutes/{r["sid"]}.md">'
        f'{r["sid"].replace("ors-","ORS ")}</a></td>'
        f'<td class="num">{r["yr"]}</td><td class="num">{r["ay"]}</td>'
        f'<td class="num">{r["lag"]}</td></tr>'
        for r in top)
    table = ('<table><thead><tr><th>rule</th><th>agency</th><th>authorizing statute</th>'
             '<th class="num">rule last amended</th><th class="num">statute last moved</th>'
             '<th class="num">lag (yrs)</th></tr></thead>'
             f'<tbody>{rows}</tbody></table>')

    script = """
var tip = document.getElementById('tip');
document.querySelectorAll('svg [data-lag]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent = '';
    var v = document.createElement('strong');
    v.textContent = Number(el.dataset.n).toLocaleString() + ' rules ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode(el.dataset.lag +
      (el.dataset.lag === '40' ? '+' : '') + ' years behind their statute'));
    tip.style.display = 'block';
    tip.style.left = Math.min(ev.clientX + 14, innerWidth - 300) + 'px';
    tip.style.top = (ev.clientY + 14) + 'px';
  });
  el.addEventListener('pointerleave', function(){ tip.style.display = 'none'; });
});
"""

    lede = (f"Of Oregon's {len(rules):,} administrative rules, {len(datable):,} carry "
            f"both their own last-amendment year and their authorizing statute's. For "
            f"{len(lagged):,} of them the statute has moved since the rule was last "
            f"touched — and for <b>{n10:,}</b> the gap is ten years or more. Each is a "
            f"place where the law changed and the rule implementing it did not visibly "
            f"follow: a candidate for attention, found mechanically.")

    caveats = (
        "<p><b>A lag is a candidate, not a violation.</b> A statute amendment does not "
        "necessarily require a rule change — the amendment may not touch the delegated "
        "authority at all, and an unchanged rule can remain exactly right. What the lag "
        "measures is only that nobody has visibly revisited the rule since its statute "
        "moved. <b>Dates come from the documents' own history lines</b>, mirrored in the "
        "executive-regulatory-frameworks corpus; "
        f"{len(rules) - len(datable):,} rules lack a datable year on one side or the "
        "other and are excluded from every figure here. The statute's year is its "
        "latest amendment of any kind, not necessarily one relevant to this rule. "
        "Explore the full dataset interactively on the "
        f'<a href="{"https://oregonai.github.io/" + ERF + "/regulatory-freshness.html"}">'
        "corpus's own freshness dashboard</a>.</p>")

    body = (f'<div class="panel">{svg}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">The twenty '
            f'largest lags</h2>{table}</div>')

    title = (f"{n10:,} Oregon rules are ten or more years behind the "
             f"statutes they implement")
    page = viz.chart_page(
        title=title,
        eyebrow="oregon-stories · from the executive-regulatory-frameworks corpus",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"{n10:,} rules are 10+ years behind their statute — mechanically measured, "
             f"{len(lagged):,} lag at all")
    return SLUG, claim, page

"""Story: the federal law Oregon's rules stand on — cited constantly, held barely.

Source: ERF's generated external-citations catalog (every federal citation in 75,960
scanned documents, with authority claims distinguished from mere mentions) and
federal-reference's published index. The finding is a coverage gap of THIS PLATFORM,
stated as such: Oregon's rules claim federal authority 916 times across 1,271 distinct
federal targets, and the platform's federal corpus currently resolves almost none of
them — the ceiling is cited far more than it is held.
"""
from __future__ import annotations

import html
import json

import yaml

from corpus_toolkit import viz
from data_sources import PAGES, RAW, fetch, sources_for_footer

ERF = "executive-regulatory-frameworks"
SLUG = "the-federal-ceiling"


def build() -> tuple[str, str, str]:
    cat = yaml.safe_load(fetch(f"{RAW}/{ERF}/main/_meta/catalog/external-citations.yml",
                               "ERF external-citations catalog (generated)"))
    fed_index = json.loads(fetch(f"{PAGES}/federal-reference/corpus-index.json",
                                 "federal-reference published index"))
    s = cat["summary"]
    targets = cat["targets"]
    top = sorted(targets, key=lambda t: -t["authority_claims"])[:20]
    vmax = top[0]["authority_claims"]

    ROW = 26
    H = 20 + ROW * len(top)
    bars = []
    for i, t in enumerate(top):
        y = 10 + i * ROW
        w = 560 * t["authority_claims"] / vmax
        held = t.get("resolves")
        bars.append(
            f'<text x="150" y="{y+13}" text-anchor="end" class="val" '
            f'font-size="12">{html.escape(t["citation"])}</text>'
            f'<rect x="158" y="{y}" width="{max(w,2):.1f}" height="16" rx="3" '
            f'fill="var(--s1)" opacity="{1 if held else 0.45}" '
            f'data-cite="{html.escape(t["citation"])}" '
            f'data-claims="{t["authority_claims"]}" data-mentions="{t["mentions"]}" '
            f'data-held="{"yes" if held else "no"}"/>'
            f'<text x="{162+w:.1f}" y="{y+13}" font-size="12">'
            f'{t["authority_claims"]}{" · held" if held else ""}</text>')
    svg = (f'<svg viewBox="0 0 880 {H}" role="img" aria-label="Federal instruments by '
           f'Oregon authority claims">{"".join(bars)}</svg>')

    named = cat.get("named_instruments") or []
    named_rows = "".join(
        f"<tr><td>{html.escape(n['instrument'].upper())}</td>"
        f"<td class='num'>{n['authority_claims']}</td>"
        f"<td class='num'>{n['mentions']}</td>"
        f"<td>{'held' if n.get('resolves') else '—'}</td></tr>"
        for n in sorted(named, key=lambda n: -n["mentions"]))

    tiles = "".join(
        f'<div class="panel" style="display:inline-block;min-width:190px;margin:4px">'
        f'<p class="eyebrow" style="margin:0">{lab}</p>'
        f'<p style="margin:2px 0;font-size:22px;font-weight:600">{val}</p>'
        f'<p style="margin:0;font-size:12.5px;color:var(--ink2)">{sub}</p></div>'
        for lab, val, sub in [
            ("Distinct federal targets cited", f"{s['distinct_targets']:,}",
             f"across {s['documents_scanned']:,} scanned documents"),
            ("Authority claims", f"{s['authority_claims_total']:,}",
             "an Oregon rule naming federal law as its legal basis"),
            ("Mentions besides", f"{s['mentions_total']:,}",
             "references that stop short of claiming authority"),
            ("Targets the platform resolves", str(s["targets_resolving"]),
             f"federal-reference holds {fed_index['n_documents']} documents across "
             f"5 instruments — chosen for audit citations, not rule authority"),
        ])

    script = """
var tip=document.getElementById('tip');
document.querySelectorAll('svg [data-cite]').forEach(function(el){
  el.addEventListener('pointermove', function(ev){
    tip.textContent='';
    var v=document.createElement('strong');
    v.textContent=el.dataset.claims+' authority claims ';
    tip.appendChild(v);
    tip.appendChild(document.createTextNode('(' + el.dataset.mentions +
      ' mentions) — ' + el.dataset.cite +
      (el.dataset.held === 'yes' ? ' — held in federal-reference' :
       ' — not yet held')));
    tip.style.display='block';
    tip.style.left=Math.min(ev.clientX+14,innerWidth-340)+'px';
    tip.style.top=(ev.clientY+14)+'px';
  });
  el.addEventListener('pointerleave',function(){tip.style.display='none';});
});
"""
    lede = (f"Oregon's administrative rules do not stand on state law alone: "
            f"{s['authority_claims_total']} times, a rule names federal law as its "
            f"legal basis — {top[0]['citation']} (special education) alone carries "
            f"{top[0]['authority_claims']} authority claims. The platform's federal "
            f"corpus was built from what the AUDITORS cite, so of what the RULES "
            f"claim as authority, {s['targets_resolving']} target currently resolves. "
            f"That is a measured hole in this platform's own ceiling — drawn here so "
            f"it gets filled deliberately, most-cited first.")

    caveats = (
        "<p><b>This measures the platform's coverage, not Oregon's compliance with "
        "anything.</b> An 'authority claim' is a mechanical read of a rule's own "
        "authority line; a 'mention' is any other citation — the catalog's "
        "distinction, applied unchanged. Solid bars are instruments federal-reference "
        "holds; faded bars are the queue. Named-instrument rows (HIPAA at 377 "
        "mentions, WIOA, FERPA…) count prose references that no CFR-part arithmetic "
        "captures. The 28 CFR 35 row is the ADA Title II rule discussed in the "
        "documents-as-pictures story — 7 authority claims, not yet held; its ingest "
        "is filed as a federal-reference issue.</p>")

    body = (f"<div>{tiles}</div>"
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">The twenty '
            f'most-claimed federal authorities (solid = held in the platform)</h2>'
            f'{svg}</div>'
            f'<div class="panel"><h2 style="font-size:14px;margin:0 0 8px">Named '
            f'instruments, counted by prose reference</h2>'
            f'<table><thead><tr><th>instrument</th><th class="num">authority claims'
            f'</th><th class="num">mentions</th><th>held</th></tr></thead>'
            f'<tbody>{named_rows}</tbody></table></div>')

    page = viz.chart_page(
        title=f"The federal ceiling: {s['authority_claims_total']} authority claims, "
              f"{s['targets_resolving']} resolving",
        eyebrow="oregon-stories · executive-regulatory-frameworks × federal-reference",
        lede_html=lede, body_html=body, caveats_html=caveats,
        sources=sources_for_footer(),
        generated=__import__("datetime").date.today().isoformat(), script=script)
    claim = (f"Oregon rules claim federal authority {s['authority_claims_total']} "
             f"times across {s['distinct_targets']:,} targets; the platform resolves "
             f"{s['targets_resolving']}")
    return SLUG, claim, page

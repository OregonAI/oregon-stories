#!/usr/bin/env python3
"""Build every story into site/ plus the gallery index.

  python3 build.py

A story builder returns (slug, one_line_claim, page_html). Each runs with a FRESH fetch
ledger so its sources footer cites exactly the bytes its own numbers came from. Any
fetch failure raises and the build exits nonzero — a red run instead of a quietly
shrunken gallery; the previously published site stays live on Pages
(OregonAI.github.io#1's rule, applied here from day one).
"""
from __future__ import annotations

import datetime
import html
import importlib
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import data_sources
from corpus_toolkit import viz

SITE = pathlib.Path(__file__).parent / "site"
MANIFEST = pathlib.Path(__file__).parent / "stories.yml"


# Fixed corpus -> chip slot map, in the landing site's corpus order. Slots are the
# toolkit's validated --s1..--s8 series variables, assigned in fixed order and never
# cycled (the dataviz rule); there are exactly eight corpora for eight slots. The
# chip carries identity beside ink-colored text — text never wears a series color.
CORPUS_SLOTS = {
    "executive-regulatory-frameworks": (1, "Regulatory"),
    "oregon-legislature": (2, "Legislature"),
    "oregon-budget": (3, "Budget"),
    "oregon-audits": (4, "Audits"),
    "oregon-kpm": (5, "KPM"),
    "oregon-counties": (6, "Counties"),
    "federal-reference": (7, "Federal"),
    "oregon-collective-bargaining": (8, "Bargaining"),
}
GROUP_TITLES = {
    "across": "Across the platform",
    "executive-regulatory-frameworks": "Executive Regulatory Frameworks",
    "oregon-legislature": "The Legislature",
    "oregon-budget": "Budget & Expenditure",
    "oregon-audits": "Audits",
    "oregon-kpm": "Key Performance Measures",
    "oregon-counties": "Counties",
    "federal-reference": "Federal Reference",
    "oregon-collective-bargaining": "Collective Bargaining",
}
GROUP_LEDES = {
    "across": "Stories that only exist because the corpora join — each one walks at "
              "least two of them.",
}


def _chips(corpora: list[str]) -> str:
    """Identity chips for the story's source corpora — .legend/.chip is the toolkit's
    sanctioned pattern (colored chip beside ink text, never colored text)."""
    bits = []
    for c in corpora:
        slot, name = CORPUS_SLOTS.get(c, (None, c))
        chip = (f'<span class="chip" style="background:var(--s{slot})"></span>'
                if slot else "")
        bits.append(f'<span style="white-space:nowrap">{chip}{html.escape(name)}</span>')
    return (f'<p class="legend" style="margin:8px 0 0;font-size:12px;'
            f'color:var(--muted);gap:6px 14px">{"".join(bits)}</p>')


def _card(href: str, title: str, claim: str, corpora: list[str], sub: str) -> str:
    return (f'<div class="panel" style="margin:0">'
            f'<h2 style="margin:0 0 4px;font-size:17px">'
            f'<a href="{html.escape(href, quote=True)}">{html.escape(title)}</a></h2>'
            f'<p style="margin:0;color:var(--ink2);font-size:13px">{html.escape(claim)}</p>'
            f'{_chips(corpora)}'
            f'<p style="margin:6px 0 0;color:var(--muted);font-size:12px">{html.escape(sub)}</p>'
            f'</div>')


def _grouped(cards_by_group: dict[str, list[str]]) -> str:
    """Group sections in fixed order; a group renders only when it has cards (the
    landing-site rule — an empty section with a justification is worse than none).
    Grid is page-local inline style; graduating a .cards class into viz_css is a
    separate toolkit decision, deliberately not taken here."""
    out = []
    for key in ["across"] + list(CORPUS_SLOTS):
        cards = cards_by_group.get(key)
        if not cards:
            continue
        lede = GROUP_LEDES.get(key)
        out.append(
            f'<section style="margin:28px 0 0">'
            f'<p class="eyebrow" style="margin:0 0 2px">{html.escape(GROUP_TITLES[key])}'
            f' · {len(cards)}</p>'
            f'<hr style="border:0;border-top:1px solid var(--border);margin:4px 0 12px">'
            + (f'<p style="margin:0 0 10px;color:var(--ink2);font-size:13px">{lede}</p>' if lede else "")
            + f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px">'
            + "".join(cards) + "</div></section>")
    return "".join(out)


def _ledger_check(entry: dict) -> None:
    """Warn (never fail) when a fetch touched a corpus the manifest does not declare —
    the semantic caches and data.oregon.gov legitimately diverge, so this is a lint,
    not a gate."""
    import re as _re
    declared = set(entry.get("corpora", []))
    for f in data_sources.FETCHED:
        m = _re.search(r"(?:githubusercontent\.com/OregonAI|oregonai\.github\.io)/([a-z-]+)", f["url"])
        if m and m.group(1) in CORPUS_SLOTS and m.group(1) not in declared:
            print(f"  WARNING {entry['id']}: fetched {m.group(1)} but corpora: does not declare it")


def _build_local(entry: dict, out_root: pathlib.Path) -> tuple[str, str, int]:
    """Build one local story under out_root; (relpath, claim, n_sources)."""
    data_sources.FETCHED.clear()
    mod = importlib.import_module(f"stories.{entry['id']}")
    if hasattr(mod, "build_many"):
        slug, claim, pages = mod.build_many()
        for rel, html_page in pages:
            out = out_root / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html_page, encoding="utf-8")
        print(f"  built {len(pages)} page(s) under {slug.rsplit('/', 1)[0]}/")
    else:
        s, claim, page = mod.build()
        slug = f"{s}.html"
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / slug).write_text(page, encoding="utf-8")
        print(f"  built {slug}")
    return slug, claim, len(data_sources.FETCHED)


def main() -> int:
    # THE MANIFEST IS THE GATE (stories.yml): published entries render in the public
    # gallery; drafts build under site/drafts/ — reachable only through the drafts
    # index, which nothing public links to. Flipping a status is a PR: that diff is
    # the operator's triage decision, on the record.
    entries = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["stories"]
    SITE.mkdir(exist_ok=True)
    # A story appears EXACTLY ONCE: under its corpus, or under "Across the platform"
    # when it draws on two or more (7 of 13 do — that join is the platform's point,
    # so the cross-corpus group leads).
    cards_by_group: dict[str, list[str]] = {}
    draft_cards, n_published = [], 0
    for e in entries:
        published = e["status"] == "published"
        corpora = e.get("corpora", [])
        group = "across" if len(corpora) >= 2 else (corpora[0] if corpora else "across")
        if e["kind"] == "local":
            root = SITE if published else SITE / "drafts"
            slug, claim, n_src = _build_local(e, root)
            _ledger_check(e)
            title = e.get("title", slug)
            sub = f"{n_src} cited source artifact(s), hashes on the page."
            card = _card(slug, title, claim, corpora,
                         sub if published else f"DRAFT — {e.get('note', 'awaiting triage')}")
        else:
            # External: renders on a corpus page until its port lands (see issues).
            # The gallery is still the ONE index that knows it exists.
            sub = "Renders on its corpus page for now — port pending."
            card = _card(e["url"], e["title"], e["claim"], corpora,
                         sub if published else f"DRAFT — {e.get('note', 'awaiting triage')}")
            print(f"  indexed external {e['id']} ({e['status']})")
        if published:
            cards_by_group.setdefault(group, []).append(card)
            n_published += 1
        else:
            draft_cards.append(card)

    if draft_cards:
        drafts_dir = SITE / "drafts"
        drafts_dir.mkdir(exist_ok=True)
        drafts_index = viz.chart_page(
            title="Drafts — operator review area",
            eyebrow="oregon-stories · not published",
            lede_html=("Nothing here is published: no public page links this index, and "
                       "these entries have no gallery card. Publication is a one-line "
                       "manifest flip in a PR — that review is the editorial gate "
                       "(README.md), applied before anything below is presented as a "
                       "finding."),
            body_html=('<div style="display:grid;grid-template-columns:'
                       'repeat(auto-fill,minmax(300px,1fr));gap:12px">'
                       + "".join(draft_cards) + "</div>"),
            caveats_html="<p>Draft content may be wrong, unreviewed, or misframed. Do not cite.</p>",
            sources=[],
            generated=datetime.date.today().isoformat())
        (drafts_dir / "index.html").write_text(drafts_index, encoding="utf-8")
        print(f"wrote site/drafts/index.html ({len(draft_cards)} draft(s))")

    index = viz.chart_page(
        title="Oregon, measured from its own records",
        eyebrow="oregon-stories · Civic Corpus Platform",
        lede_html=("Each story below derives every number, at build time, from the "
                   "platform's mirrored public records — and links the exact artifacts "
                   "and their hashes so anyone can check. Non-authoritative throughout; "
                   "the records themselves live with the state."),
        body_html=_grouped(cards_by_group),
        caveats_html=("<p>Stories state what the records show, never why — cause is "
                      "not in the data. Every page carries its own caveats; read them "
                      "before quoting a figure.</p>"),
        sources=[{"label": "the Civic Corpus Platform",
                  "url": "https://oregonai.github.io/"}],
        generated=datetime.date.today().isoformat())
    (SITE / "index.html").write_text(index, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote site/index.html ({n_published} published card(s) in "
          f"{len(cards_by_group)} group(s), {len(draft_cards)} draft(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())

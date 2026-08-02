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


def _card(href: str, claim: str, sub: str) -> str:
    return (f'<div class="panel"><h2 style="margin:0 0 4px;font-size:17px">'
            f'<a href="{href}">{html.escape(claim)}</a></h2>'
            f'<p style="margin:0;color:var(--ink2);font-size:13px">{html.escape(sub)}</p></div>')


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
    cards, draft_cards = [], []
    for e in entries:
        published = e["status"] == "published"
        if e["kind"] == "local":
            root = SITE if published else SITE / "drafts"
            slug, claim, n_src = _build_local(e, root)
            sub = f"{n_src} cited source artifact(s), hashes on the page."
            (cards if published else draft_cards).append(
                _card(slug, claim, sub if published else
                      f"DRAFT — {e.get('note', 'awaiting triage')}"))
        else:
            # External: renders on a corpus page until its port lands (see issues).
            # The gallery is still the ONE index that knows it exists.
            sub = "Renders on its corpus page — port into this repo pending."
            card = _card(e["url"], e["claim"], sub if published else
                         f"DRAFT — {e.get('note', 'awaiting triage')}")
            (cards if published else draft_cards).append(card)
            print(f"  indexed external {e['id']} ({e['status']})")

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
            body_html="".join(draft_cards),
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
        body_html="".join(cards),
        caveats_html=("<p>Stories state what the records show, never why — cause is "
                      "not in the data. Every page carries its own caveats; read them "
                      "before quoting a figure.</p>"),
        sources=[{"label": "the Civic Corpus Platform",
                  "url": "https://oregonai.github.io/"}],
        generated=datetime.date.today().isoformat())
    (SITE / "index.html").write_text(index, encoding="utf-8")
    (SITE / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote site/index.html ({len(cards)} published card(s), {len(draft_cards)} draft(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())

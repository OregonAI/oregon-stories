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

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import data_sources
from corpus_toolkit import viz

SITE = pathlib.Path(__file__).parent / "site"

STORIES = ("agency_profiles",
           "rules_older_than_their_statutes",
           "county_code_cites_dead_law",
           "what_agencies_told_the_legislature",
           "can_you_read_your_countys_law",
           "where_appropriations_actually_land",
           "documents_that_exist_only_as_pictures",
           "the_federal_ceiling",
           "found_by_meaning",
           "the_copy_paste_rulebook",
           "the_map_of_stale_law",
           "far_from_their_authority",
           "rulemaking_and_stated_priorities")


def main() -> int:
    SITE.mkdir(exist_ok=True)
    cards = []
    for name in STORIES:
        data_sources.FETCHED.clear()
        mod = importlib.import_module(f"stories.{name}")
        if hasattr(mod, "build_many"):
            # Multi-page story: (entry_relpath, claim, [(relpath, html), ...])
            slug, claim, pages = mod.build_many()
            for rel, html_page in pages:
                out = SITE / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(html_page, encoding="utf-8")
            print(f"  built {len(pages)} page(s) under {slug.rsplit('/', 1)[0]}/")
        else:
            slug, claim, page = mod.build()
            slug = f"{slug}.html"
            (SITE / slug).write_text(page, encoding="utf-8")
        n_src = len(data_sources.FETCHED)
        cards.append(f'<div class="panel"><h2 style="margin:0 0 4px;font-size:17px">'
                     f'<a href="{slug}">{html.escape(claim)}</a></h2>'
                     f'<p style="margin:0;color:var(--ink2);font-size:13px">'
                     f'{n_src} cited source artifact(s), hashes on the page.</p></div>')
        print(f"  built {slug}")

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
    print(f"wrote site/index.html ({len(STORIES)} stories)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

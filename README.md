# oregon-stories

Data stories from the [Civic Corpus Platform](https://oregonai.github.io/): static
pages, every number derived at build time from the platform's mirrored public records,
every source artifact cited with its hash, every caveat on the page.

**Non-authoritative, throughout.** The records themselves live with the State of
Oregon; these pages summarize mirrors of them and must never be quoted as the law,
the budget, or the audit record.

Editorial rules (they bind every story):
- Strictly nonpartisan: officials by office, never by party; description, never cause.
- A failed data fetch fails the build — a story never quietly renders from partial data.
- Coverage before findings; denominators visible; "could not check" is never "is not there".
- Charts follow `corpus_toolkit.viz`'s palette rules (they are colorblind-safety
  mechanisms, not taste — see that module's docs).

Build: `pip install -r requirements.txt && python3 build.py` → `site/`.

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

## Porting an externally hosted chart (oregon-stories#2)

`stories.yml` still lists some charts as `kind: external` (they render on a corpus
repo's own Pages site). Each port is one small PR; the first to follow this recipe was
`statute_operationalization`.

1. **Re-measure the issue's checklist first.** The checklist in #2 drifts: audit-mix,
   regulatory-freshness, policy-age, agency-authority-graph and governor-priorities had
   already landed when it was last read. Grep `stories.yml` for `kind: external`, and
   check the corpus's `git log` for the chart's builder before trusting the issue.
2. **Find the builder, not the page.** The corpus's `src/build_*.py` states exactly which
   committed artifacts the chart is computed from. Those artifacts (raw files on the
   corpus's `main`, or its Pages `corpus-index.json`) are the runtime input. The
   corpus's `viz/*.html` is never fetched; it is only the *oracle* in step 4.
3. **Port the data shaping as pure functions** in `stories/<id>.py` (the module name is
   the manifest id), with the page as a `render(...)` function and `build()` doing only
   `fetch(...)` through `data_sources.fetch` so the footer cites each artifact's hash.
   Reproduce what the chart shows; a port is not a redesign. Where the original's label
   claims more than the data supports, keep the numbers and fix the label (state it in
   the PR).
4. **Test first, offline.** Commit an *excerpt* of the real artifacts under
   `tests/fixtures/` (whole-chapter slices, so counts are real, not hand-typed) together
   with the rows the corpus's own page carries for those slices (`expected_rows`) as the
   independent oracle. Tests call the pure functions and `build()` with `fetch`
   monkeypatched to the fixture; nothing in `tests/` touches the network.
5. **Check the full-size equivalence once, by hand.** Run the pure function over the whole
   artifact (from the corpus checkout's `git show origin/main:<path>`, read-only) and
   compare to the DATA blob inside the corpus page: equal rows, equal totals.
6. **Flip the manifest** in the same PR: drop the `kind: external` entry, add
   `{id: <module>, status: published, kind: local, title: ..., corpora: [...]}`. A local
   entry carries no `url`/`claim` (the build supplies the claim). `tests/test_manifest.py`
   is the offline manifest gate; add a one-line assertion for the new entry.
7. **Gates:** `python3 -m pytest tests -q`, then `python3 build.py` (needs network; CI's
   pages job runs it). Do not remove the chart from the corpus repo in this PR; that is a
   separate PR in that repo, after this one is live.

### Payload sizes

| chart | page shipped | gzip | build-time input fetched |
|---|---|---|---|
| statute-operationalization | 105 KB (ERF's copy: 101 KB) | 20 KB | graph.json 33.5 MB, ors.yml 5.8 MB, agencies.yml 0.15 MB |

The shipped page is what a reader downloads; the build-time input is paid once per
build, not per reader. #2 asks for a payload-size guideline; none is enforced yet.

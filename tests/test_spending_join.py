"""Which body a spending row lands on, and which key decides that.

The seam is `agency_profiles.slug_of_das_number(reg)`: registry rows in, the DAS-number
-> slug index the SODA join reads out. It is the same shape of seam as `slug_index`,
and for the same reason — the join is the claim ("this money is this body's"), so the
join is what gets tested, not the page that renders it.
"""
from stories.agency_profiles import slug_of_das_number

# Copied from ERF _meta/catalog/agencies.yml, 2026-08-21, with `budget_agency_code`
# dropped the way ERF #177 drops it from every row — verbatim in every other key. Both
# keys hold the same value on all 80 rows that carry one today, and ERF's own
# `deprecated-key-agrees` rule makes them impossible to diverge, so a fixture carrying
# both would pass whichever key the code read. Dropping the deprecated one is the only
# way this fixture can tell the two apart.
POST_177 = [
    {"slug": "board-of-chiropractic-examiners", "das_agency_number": "811"},
    {"slug": "board-of-nursing", "das_agency_number": "851"},
    {"slug": "bureau-of-labor-and-industries", "das_agency_number": "100"},
]


def test_the_join_resolves_a_registry_that_carries_only_das_agency_number():
    """The post-#177 registry, which is the one this page will be fetching from ERF's
    `main` the day #177 merges — over HTTP, with no commit to this repo to catch it."""
    assert slug_of_das_number(POST_177) == {"811": "board-of-chiropractic-examiners",
                                            "851": "board-of-nursing",
                                            "100": "bureau-of-labor-and-industries"}


def test_the_deprecated_budget_agency_code_joins_nothing():
    """ERF #175 left `budget_agency_code` beside the field of record holding the same
    value, so a fallback onto it would pass every test that reads today's registry and
    then resolve nothing the day #177 removes it. The fallback is what this asserts is
    absent — a row carrying only the deprecated key is not spending-joinable here."""
    assert slug_of_das_number([{"slug": "board-of-nursing",
                                "budget_agency_code": "851"}]) == {}

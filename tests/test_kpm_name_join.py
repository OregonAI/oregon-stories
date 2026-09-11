"""Which oar_name reading links a KPM agency string to a slug, when the registry name
carries a parent/child qualifier comma rather than a catalog-inversion comma.

The seam is `agency_profiles.slug_index(reg)`: registry rows in, the normalized-name
-> slug index the KPM join reads out. Same shape of seam as `slug_of_das_number` (see
tests/test_spending_join.py) -- the join is the claim ("this KPM row is this body's"),
so the join is what's tested, not the page that renders it.

The same flaw this pins was found and fixed in the sibling corpora during
OregonAI/executive-regulatory-frameworks#167: oregon-audits#30 and oregon-kpm#51 both
replace a forced comma-inversion with `norm_variants()`, a SET of readings rather than
a pipeline. Ported here verbatim (see `norm_variants` in stories/agency_profiles.py).
"""
from stories.agency_profiles import resolve_via_registry, slug_index


def test_a_qualifier_comma_still_links_its_uncommaed_kpm_spelling():
    """'Secretary of State, Audits Division' is ONE body with a parent/child qualifier
    comma, not a catalog entry to invert. Forcing comma-inversion (the pre-fix `_norm`)
    turns it into 'audits division secretary of state', which never matches the plain
    KPM spelling 'Secretary of State Audits Division' -- a measured miss (oregon-audits
    #30 took this same pair from 30/31 to 31/31 once punctuation-stripping and
    comma-inversion became a SET of readings the index carries, rather than the one
    forced pipeline reading)."""
    reg = [{"slug": "secretary-of-state-audits-division",
            "oar_name": "Secretary of State, Audits Division"}]
    idx = slug_index(reg)
    assert idx.get("secretary of state audits division") == \
        "secretary-of-state-audits-division"


def test_a_kpm_spelling_that_carries_the_comma_still_resolves():
    """The registry's oar_name here has NO comma (only one reading), but oregon-kpm's
    cover-page spelling of the same body DOES carry the qualifier comma. The query side
    of the join needs every reading too -- looking up only the comma-inverted reading
    of the KPM string ('audits division secretary of state') would miss an index that
    only ever held the plain reading, the same forced-single-reading failure on the
    other side of the join."""
    idx = slug_index([{"slug": "secretary-of-state-audits-division",
                       "oar_name": "Secretary of State Audits Division"}])
    assert resolve_via_registry(idx, "Secretary of State, Audits Division") == \
        "secretary-of-state-audits-division"

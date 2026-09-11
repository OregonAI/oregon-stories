"""Which oar_name reading links a KPM agency string to a slug, across the two jobs a
comma does in these strings: a parent/child qualifier ("Secretary of State, Audits
Division") and catalog inversion ("Administrative Services, Department of").

The seam is `agency_profiles.slug_index(reg)`: registry rows in, the normalized-name
-> slug index the KPM join reads out. Same shape of seam as `slug_of_das_number` (see
tests/test_spending_join.py) -- the join is the claim ("this KPM row is this body's"),
so the join is what's tested, not the page that renders it.

The same flaw this pins was found and fixed in the sibling corpora during
OregonAI/executive-regulatory-frameworks#167: oregon-audits#30 and oregon-kpm#51 both
replace a forced comma-inversion with `norm_variants()`, a SET of readings rather than
a pipeline. That function now lives once in `corpus_toolkit.crosswalk` (the platform's
one implementation, per its module docstring and ADR-0009) -- oregon-audits, oregon-kpm
and this repo all import it rather than each keeping a copy.
"""
from corpus_toolkit.crosswalk import norm_variants

from stories.agency_profiles import slug_for_name, slug_index


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
    assert slug_for_name(idx, "Secretary of State, Audits Division") == \
        "secretary-of-state-audits-division"


def test_a_catalog_comma_oar_name_still_resolves_its_inverted_kpm_spelling():
    """The OTHER direction the same comma has to carry: a registry oar_name spelled the
    catalog way ("Administrative Services, Department of") must still resolve the KPM
    cover-page spelling that inverts it ("Department of Administrative Services"). This
    is the reading 117 of today's 150 live KPM matches actually depend on -- a suite
    that only pinned the qualifier-comma direction (both tests above) could pass in
    full while a change silently dropped this one and zeroed the KPM join."""
    idx = slug_index([{"slug": "administrative-services-department-of",
                       "oar_name": "Administrative Services, Department of"}])
    assert slug_for_name(idx, "Department of Administrative Services") == \
        "administrative-services-department-of"


def test_two_bodies_whose_readings_collide_resolve_to_the_first_in_registry_order():
    """Widening the index to every reading `norm_variants` permits widens the surface
    for two different bodies to claim the same key. `slug_index` resolves any such
    clash silently, via `setdefault`, by registry row order -- this pins that resolution
    rather than leaving it undocumented. (0 keys are claimed by more than one slug on
    the live registry today, per OregonAI/oregon-stories#11's measurement -- this is a
    latent case, not a present one, but the issue's own title is about false matches
    from name normalization, and the widened index is exactly where a future collision
    would land.)"""
    # Two distinct bodies whose readings collide once comma is stripped either way.
    reg = [{"slug": "first-body", "oar_name": "Widgets, Board of"},
           {"slug": "second-body", "oar_name": "Board of Widgets"}]
    idx = slug_index(reg)
    # Both oar_names produce the reading "board of widgets" among others; the first
    # registry row to claim a key keeps it.
    assert idx["board of widgets"] == "first-body"
    assert norm_variants("Board of Widgets") & norm_variants("Widgets, Board of")

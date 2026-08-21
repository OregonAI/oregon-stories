"""What the profile page says about a body's parent, and what it refuses to say.

The seam is `agency_profiles.parentage(org, names)`: registry row in, the two rendered
strings the page shows out. Everything below asserts on that rendered text, because the
rendered text is the claim the public reads.
"""
from stories.agency_profiles import parentage

NAMES = {"department-of-agriculture": "Department of Agriculture"}


def test_undetermined_relation_still_names_the_parent():
    """Unknown is not none: the relationship stays, the kind is not claimed."""
    org = {"slug": "x",
           "relations": [{"target": "department-of-agriculture",
                          "source": "oar-index", "kind": "undetermined"}]}
    lede = parentage(org, NAMES).lede_html
    assert "Department of Agriculture" in lede
    assert "department-of-agriculture.html" in lede
    assert "part of" not in lede
    assert "administered by" not in lede


def test_part_of_relation_says_part_of():
    """A division's legal existence IS its parent's (ADR 0004), and the page says so."""
    org = {"slug": "x",
           "relations": [{"target": "department-of-agriculture", "source": "registry",
                          "kind": "part_of"}]}
    got = parentage(org, NAMES)
    assert ('part of <a href="department-of-agriculture.html">Department of '
            'Agriculture</a>') in got.lede_html
    assert "does not establish" not in got.lede_html
    assert got.eyebrow == " · sub-unit"


def test_administered_by_relation_cites_its_authority():
    """A separately constituted body attached to a department for administration.
    The authority is the point of recording a relation (ADR 0004), so it renders."""
    org = {"slug": "x",
           "relations": [{"target": "department-of-agriculture", "source": "statute",
                          "kind": "administered_by", "authority": "ORS 576.066"}]}
    got = parentage(org, NAMES)
    assert ('administered by <a href="department-of-agriculture.html">Department of '
            'Agriculture</a> (ORS 576.066)') in got.lede_html
    assert "part of" not in got.lede_html
    assert got.eyebrow == " · attached body"


# Copied from ERF _meta/catalog/agencies.yml, 2026-08-21, with `parent_slug` dropped the
# way ERF #174 drops it from every row — verbatim in every other key. It is the row this
# page was publishing as "part of Department of Agriculture" until the relations landed. ORS
# 576.062 establishes the commodity commissions AS STATE COMMISSIONS; the department's
# role over them is ORS 576.066's oversight. All 23 of them read like this row today.
ALBACORE = {"slug": "department-of-agriculture-oregon-albacore-commission",
            "name": "Department of Agriculture, Oregon Albacore Commission",
            "oar_chapter": "972", "parent_chapter": "603",
            "relations": [{"target": "department-of-agriculture",
                           "source": "oar-index", "kind": "undetermined"}]}


def test_a_commodity_commission_is_never_called_part_of_the_department():
    got = parentage(ALBACORE, NAMES)
    assert "part of" not in got.lede_html
    assert "part of" not in got.eyebrow
    assert "sub-unit" not in got.eyebrow
    assert "Department of Agriculture" in got.lede_html


def test_the_retired_parent_slug_places_nothing():
    """ERF #174 removed `parent_slug` from the registry, so `relations` is the page's only
    source of placement. A row carrying the retired key and no relations is under nothing
    as far as this page is concerned — reading it would be this page keeping a hierarchy
    alive that the registry has stopped stating, from a field no row carries."""
    org = {"slug": "x", "parent_slug": "department-of-agriculture"}
    assert parentage(org, NAMES) == ("", "")


def test_a_row_under_nothing_says_nothing():
    assert parentage({"slug": "department-of-agriculture"}, NAMES) == ("", "")


def test_a_parent_with_no_profile_page_is_named_but_not_linked():
    """Profiles exist only for registry rows; a target outside the registry gets no
    link, because a link to a page that was never built is a broken claim of its own."""
    org = {"slug": "x", "relations": [{"target": "some-body-not-in-the-registry",
                                       "source": "das", "kind": "undetermined"}]}
    got = parentage(org, NAMES)
    assert "some-body-not-in-the-registry" in got.lede_html
    assert "<a href" not in got.lede_html


def test_two_sources_disagreeing_about_the_parent_are_both_shown():
    """ADR 0004: a body may hold more than one relation, and that disagreement is a
    finding — recorded side by side rather than reconciled into silence."""
    names = dict(NAMES, **{"department-of-administrative-services":
                           "Department of Administrative Services"})
    org = {"slug": "x", "relations": [
        {"target": "department-of-agriculture", "source": "oar-index",
         "kind": "undetermined"},
        {"target": "department-of-administrative-services", "source": "das",
         "kind": "part_of"}]}
    lede = parentage(org, names).lede_html
    assert "Department of Agriculture" in lede
    assert "part of <a href=\"department-of-administrative-services.html\">" in lede


def test_a_recorded_kind_replaces_the_undetermined_entry_for_the_same_parent():
    """Once a source establishes the kind, the older 'nobody has established which'
    entry for the SAME parent has nothing left to say, and saying both would read as
    the page contradicting itself."""
    org = {"slug": "x", "relations": [
        {"target": "department-of-agriculture", "source": "oar-index",
         "kind": "undetermined"},
        {"target": "department-of-agriculture", "source": "statute",
         "kind": "administered_by", "authority": "ORS 576.066"}]}
    got = parentage(org, NAMES)
    assert "does not establish" not in got.lede_html
    assert got.lede_html.count("Department of Agriculture") == 1
    assert got.eyebrow == " · attached body"


def test_a_kind_this_page_does_not_know_claims_neither():
    """ADR 0004 does not settle that its two kinds are exhaustive (the semi-independent
    boards under ORS 182.456 may be a third). A kind arriving from upstream that this
    page has never seen must not be rendered as one of the two it has."""
    org = {"slug": "x",
           "relations": [{"target": "department-of-agriculture", "source": "statute",
                          "kind": "semi_independent"}]}
    got = parentage(org, NAMES)
    assert "Department of Agriculture" in got.lede_html
    assert "part of" not in got.lede_html
    assert "administered by" not in got.lede_html


def test_two_sources_disagreeing_about_the_same_parent_are_attributed():
    """Two claims about ONE parent, unattributed, read as the page contradicting itself.
    Naming the source turns the contradiction back into what ADR 0004 says it is: a
    disagreement between sources, recorded side by side."""
    org = {"slug": "x", "relations": [
        {"target": "department-of-agriculture", "source": "das", "kind": "part_of"},
        {"target": "department-of-agriculture", "source": "statute",
         "kind": "administered_by", "authority": "ORS 576.066"}]}
    lede = parentage(org, NAMES).lede_html
    assert "part of <a href=\"department-of-agriculture.html\">" in lede
    assert "(per the DAS listing)" in lede
    assert "(ORS 576.066, per statute)" in lede


def test_two_kinds_at_once_leave_the_eyebrow_claiming_neither():
    """One word cannot place a body that is a unit of one department and an attached
    body of another, so the eyebrow claims neither and the lede carries both."""
    names = dict(NAMES,
                 **{"department-of-transportation": "Department of Transportation"})
    org = {"slug": "x", "relations": [
        {"target": "department-of-agriculture", "source": "statute",
         "kind": "administered_by"},
        {"target": "department-of-transportation", "source": "das", "kind": "part_of"}]}
    got = parentage(org, names)
    assert got.eyebrow == " · under another body"
    assert "administered by" in got.lede_html and "part of" in got.lede_html


def test_the_same_claim_from_two_sources_is_stated_once_and_keeps_its_citation():
    """ADR 0004: the citation is the point of recording the relation. Collapsing a
    duplicate claim must not be what throws the citation away."""
    org = {"slug": "x", "relations": [
        {"target": "department-of-agriculture", "source": "das",
         "kind": "administered_by"},
        {"target": "department-of-agriculture", "source": "statute",
         "kind": "administered_by", "authority": "ORS 576.066"}]}
    lede = parentage(org, NAMES).lede_html
    assert lede.count("administered by") == 1
    assert "(ORS 576.066)" in lede


def test_the_retired_parent_slug_adds_no_parent_beside_the_relations():
    """The fallback used to append the pointer's parent whenever no relation named it.
    With the field retired (ERF #174) that is a body the page would place under a parent
    on the strength of a key the registry no longer writes — so the relations are the
    whole answer, and nothing else is added to them."""
    names = dict(NAMES, **{"oregon-health-authority": "Oregon Health Authority"})
    org = {"slug": "x", "parent_slug": "oregon-health-authority",
           "relations": [{"target": "department-of-agriculture", "source": "das",
                          "kind": "part_of"}]}
    lede = parentage(org, names).lede_html
    assert "Oregon Health Authority" not in lede
    assert "Department of Agriculture" in lede

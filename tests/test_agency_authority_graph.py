"""Port of ERF's agency-authority-graph (oregon-stories#2): rebuilt here from the
published _meta/agency-graph.json cache, never from ERF's own self-contained
viz/agency-authority-graph.html page. The force layout and edge projection stay
client-side JS (the whole point of that page: density/ubiquity controls need no
server) and are not under test here; the two seams tested are the pieces this port
computes server-side — `edge_weight` (the SAME formula the browser recomputes on every
slider move, so a Python test pins the one number both sides must agree on) and
`top_groups` (the categorical-color cap the house palette rule requires: at most 8
series, a 9th folds into "other" rather than cycling colors)."""
from stories.agency_authority_graph import edge_weight, slot_index, top_groups


def test_edge_weight_discounts_more_popular_chapters():
    """A chapter nearly every agency implements should weigh less than a chapter only
    a few implement — the whole point of the discount (ERF's own formula note)."""
    rare = edge_weight(pop=2)
    common = edge_weight(pop=150)
    assert rare > common > 0


def test_edge_weight_matches_the_published_formula_for_a_known_value():
    """1/ln(pop + e) — an independent worked value, not read back from the function
    under test."""
    import math
    assert abs(edge_weight(pop=10) - 1 / math.log(10 + math.e)) < 1e-9


def test_top_groups_keeps_at_most_eight_and_folds_the_rest_into_other():
    groups = [{"slug": f"g{i}", "name": f"G{i}", "members": 20 - i} for i in range(12)]
    kept, n_other_groups = top_groups(groups, slots=8)
    assert len(kept) == 8
    assert [g["slug"] for g in kept] == [f"g{i}" for i in range(8)]
    assert n_other_groups == 4


def test_top_groups_keeps_the_largest_departments_by_member_count():
    """The cap should drop the SMALLEST colored departments, not an arbitrary subset —
    the biggest groupings are the ones worth a dedicated color."""
    groups = [{"slug": "small", "name": "Small", "members": 2},
             {"slug": "big", "name": "Big", "members": 30}]
    kept, _ = top_groups(groups, slots=1)
    assert kept[0]["slug"] == "big"


def test_top_groups_with_room_to_spare_folds_nothing():
    groups = [{"slug": "a", "name": "A", "members": 5}]
    kept, n_other = top_groups(groups, slots=8)
    assert len(kept) == 1
    assert n_other == 0


def test_slot_index_matches_the_legend_order_largest_members_first():
    """The legend gives slot 1 to the group top_groups put first (by member count); a
    node's drawn color must index into the SAME order, not first-appearance-in-data —
    that mismatch put the wrong department on every legend color in the built page."""
    groups = [{"slug": "small", "name": "Small", "members": 3},
             {"slug": "big", "name": "Big", "members": 50}]
    kept, _ = top_groups(groups, slots=8)
    assert slot_index(kept) == {"big": 1, "small": 2}

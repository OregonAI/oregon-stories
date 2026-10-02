"""Port of ERF's policy-age chart (oregon-stories#2): rebuilt here from the published
cache _meta/policy_age.json, never from ERF's own viz/policy-age.html page.

Seams: `age_years(last_touched, today)` (the absolute clock the page reads age off —
computed at OUR build time, not inherited from whenever ERF last refreshed its cache)
and `agency_table` / `most_overdue` (the ranking panel and the "most overdue" list).
"""
import datetime

from stories.policy_age import age_years, agency_table, most_overdue, swarm_and_cite


def test_age_years_is_the_days_since_last_touched_in_years():
    today = datetime.date(2026, 1, 1)
    assert age_years("2024-01-01", today) == 2.0


def test_age_years_is_none_for_a_doc_with_no_last_touched_date():
    assert age_years(None, datetime.date(2026, 1, 1)) is None


def test_agency_table_counts_due_and_overdue_by_the_cadence_thresholds():
    today = datetime.date(2026, 1, 1)
    docs = [
        {"agency": "a", "last_touched": "2026-01-01"},   # 0y — current
        {"agency": "a", "last_touched": "2023-01-01"},   # 3y — due
        {"agency": "a", "last_touched": "2018-01-01"},   # 8y — overdue
        {"agency": "b", "last_touched": None},           # undated
    ]
    table = {row["agency"]: row for row in
            agency_table(docs, due=2, overdue=4, today=today)}
    assert table["a"]["total"] == 3
    assert table["a"]["dated"] == 3
    assert table["a"]["due"] == 1
    assert table["a"]["overdue"] == 1
    assert table["b"]["total"] == 1
    assert table["b"]["dated"] == 0


def test_most_overdue_sorts_oldest_first_and_respects_the_overdue_threshold():
    today = datetime.date(2026, 1, 1)
    docs = [
        {"id": "a", "agency": "x", "last_touched": "2020-01-01"},  # 6y
        {"id": "b", "agency": "x", "last_touched": "2010-01-01"},  # 16y
        {"id": "c", "agency": "x", "last_touched": "2025-01-01"},  # 1y, not overdue
    ]
    overdue = most_overdue(docs, overdue=4, today=today, limit=10)
    assert [o["id"] for o in overdue] == ["b", "a"]


def test_most_overdue_respects_the_limit():
    today = datetime.date(2026, 1, 1)
    docs = [{"id": str(i), "agency": "x", "last_touched": "2000-01-01"} for i in range(5)]
    assert len(most_overdue(docs, overdue=4, today=today, limit=2)) == 2


def test_swarm_and_cite_maps_each_point_to_its_own_citation_even_after_an_undated_doc():
    """A dated doc after an undated one must still map to its own citation — the swarm
    is built only from the dated subset, so an index into `swarm` and the same index
    into `cite` must always name the same document."""
    today = datetime.date(2026, 1, 1)
    docs = [
        {"id": "a", "doc_type": "policy", "citation": "A-1", "last_touched": "2024-01-01"},
        {"id": "b", "doc_type": "policy", "citation": "B-1", "last_touched": None},
        {"id": "c", "doc_type": "procedure", "citation": "C-1", "last_touched": "2020-01-01"},
    ]
    swarm, cite = swarm_and_cite(docs, today)
    assert len(swarm) == len(cite) == 2
    last_idx = swarm[-1][2]
    assert cite[last_idx] == "C-1"

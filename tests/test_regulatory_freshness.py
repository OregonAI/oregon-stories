"""Port of ERF's regulatory-freshness chart (oregon-stories#2): rebuilt here from the
published cache _meta/freshness.json, never from that corpus's own viz/ page.

Seams: `gap_years(doc)` (the lag a single rule/policy carries), `agency_table(rules,
policies)` (the ranking panel's rows) and `top_offenders(...)` (the "most worth
reviewing" list) — the three pure functions the page's claims are read off.
"""
from stories.regulatory_freshness import agency_table, gap_years, top_offenders


def test_gap_years_is_the_statute_year_minus_the_rule_year():
    assert gap_years({"yr": 2009, "ay": 2024}) == 15


def test_gap_years_is_none_when_either_side_is_undatable():
    assert gap_years({"yr": None, "ay": 2024}) is None
    assert gap_years({"yr": 2009, "ay": None}) is None


def test_agency_table_groups_rules_by_agency_and_counts_flagged():
    rules = [
        {"ag": "Dept A", "yr": 2000, "ay": 2020},  # gap 20, flagged
        {"ag": "Dept A", "yr": 2018, "ay": 2020},  # gap 2, not flagged
        {"ag": "Dept B", "yr": 2015, "ay": None},  # not datable (no ay)
    ]
    table = {row["name"]: row for row in agency_table(rules, [], flag=10)}
    assert table["Dept A"]["nr"] == 2
    assert table["Dept A"]["nd"] == 2
    assert table["Dept A"]["l10"] == 1
    assert table["Dept B"]["nr"] == 1
    assert table["Dept B"]["nd"] == 0
    assert table["Dept B"]["l10"] == 0


def test_agency_table_median_age_uses_rule_filing_year_not_the_gap():
    rules = [{"ag": "Dept A", "yr": 2010, "ay": 2020},
             {"ag": "Dept A", "yr": 2020, "ay": 2020}]
    table = {row["name"]: row for row in agency_table(rules, [], flag=10, now=2026)}
    # ages are 2026-2010=16 and 2026-2020=6; median of [16, 6] is 11
    assert table["Dept A"]["med"] == 11


def test_a_rule_with_no_recorded_agency_groups_under_unattributed():
    rules = [{"ag": None, "yr": 2000, "ay": 2020}]
    table = {row["name"]: row for row in agency_table(rules, [], flag=10)}
    assert "(unattributed)" in table


def test_top_offenders_sorts_by_gap_descending_and_respects_the_flag_threshold():
    rules = [
        {"id": "oar-1", "ag": "A", "yr": 2000, "ay": 2005, "sid": "ors-1"},  # gap 5
        {"id": "oar-2", "ag": "A", "yr": 1990, "ay": 2020, "sid": "ors-2"},  # gap 30
        {"id": "oar-3", "ag": "A", "yr": 2015, "ay": 2020, "sid": "ors-3"},  # gap 5
    ]
    offenders = top_offenders(rules, [], titles={}, flag=10, limit=10)
    assert [o["id"] for o in offenders] == ["oar-2"]
    assert offenders[0]["gap"] == 30


def test_top_offenders_respects_the_limit():
    rules = [{"id": f"oar-{i}", "ag": "A", "yr": 1990, "ay": 1990 + 20 + i, "sid": "x"}
             for i in range(5)]
    offenders = top_offenders(rules, [], titles={}, flag=10, limit=2)
    assert len(offenders) == 2
    # largest gaps first
    assert offenders[0]["gap"] >= offenders[1]["gap"]

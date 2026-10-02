"""oregon-stories#2: erf_governor_priorities (kind: external, draft) pointed at
executive-regulatory-frameworks/governor-priorities.html, which answers 404 (verified
2026-10-01) — the condition oregon-stories#2's checklist flagged that conflict-candidate
entry on. This story is its
local sibling, reading the SAME curated dataset (_meta/governor_priorities.json); the
port is closing the one real content gap between them — the original page's per-chapter
table (agency, chapter, rule count, recent-activity rate, and the curated REASONING for
why that chapter maps to the priority) — rather than standing up a duplicate entry for
data this story already renders. The seam is `chapter_rows(area)`, the table's data.
"""
from stories.rulemaking_and_stated_priorities import chapter_rows


def test_chapter_rows_computes_each_chapters_recent_activity_rate():
    area = {"chapters": [
        {"agency": "dept-of-x", "oar_chapter": "100", "reasoning": "it regulates X",
         "n_rules": 20, "n_dated": 10, "recent_2yr": 4},
    ]}
    rows = chapter_rows(area)
    assert rows[0]["rate"] == 0.4
    assert rows[0]["agency"] == "dept-of-x"
    assert rows[0]["reasoning"] == "it regulates X"


def test_chapter_rows_rate_is_zero_when_nothing_is_dated_not_a_crash():
    area = {"chapters": [{"agency": "a", "oar_chapter": "1", "reasoning": "r",
                          "n_rules": 5, "n_dated": 0, "recent_2yr": 0}]}
    assert chapter_rows(area)[0]["rate"] == 0


def test_chapter_rows_keeps_the_catalogs_own_chapter_order():
    """The chapter order is the curated catalog's own ordering (_meta/catalog/
    governor-priorities.yml) — not re-sorted by rate, which would read as this page
    picking winners among a judgment call it didn't make."""
    area = {"chapters": [
        {"agency": "b", "oar_chapter": "2", "reasoning": "r2", "n_rules": 1,
         "n_dated": 1, "recent_2yr": 1},
        {"agency": "a", "oar_chapter": "1", "reasoning": "r1", "n_rules": 1,
         "n_dated": 1, "recent_2yr": 0},
    ]}
    assert [r["oar_chapter"] for r in chapter_rows(area)] == ["2", "1"]

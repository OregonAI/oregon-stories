"""The audit-mix port reads oregon-audits' mirrored report front matter directly (the
published data artifact — reports/*.md), never that corpus's own viz/audit-mix.html
page. The seams tested here are the two pure functions the fetch feeds:
`aggregate(reports) -> {year: {type: [ids]}}` (oregon-audits#4's own `collect()` shape,
rebuilt from front matter records instead of files on disk) and
`decline_stats(data, partial_year)`, the numbers the lede states as a claim.
"""
import data_sources
from stories.audit_mix import _condense_fetch_ledger, aggregate, decline_stats


def test_reports_group_by_year_then_type():
    reports = [
        {"id": "2020-01", "report_date": "2020-02-01", "audit_type": "performance"},
        {"id": "2020-02", "report_date": "2020-03-01", "audit_type": "financial"},
        {"id": "2021-01", "report_date": "2021-01-15", "audit_type": "performance"},
    ]
    data = aggregate(reports)
    assert data == {
        "2020": {"performance": ["2020-01"], "financial": ["2020-02"]},
        "2021": {"performance": ["2021-01"]},
    }


def test_a_report_with_no_type_recorded_is_kept_under_none_recorded():
    """oregon-audits#4's collect() keys untyped reports as 'none recorded' rather than
    dropping them — nothing is hidden, only de-emphasized downstream."""
    reports = [{"id": "2022-01", "report_date": "2022-04-01", "audit_type": None}]
    data = aggregate(reports)
    assert data == {"2022": {"none recorded": ["2022-01"]}}


def test_ids_within_a_year_and_type_are_sorted():
    reports = [
        {"id": "2020-02", "report_date": "2020-03-01", "audit_type": "performance"},
        {"id": "2020-01", "report_date": "2020-02-01", "audit_type": "performance"},
    ]
    data = aggregate(reports)
    assert data["2020"]["performance"] == ["2020-01", "2020-02"]


def test_decline_stats_counts_performance_audits_at_each_end_of_the_complete_years():
    """The lede's claim ('fell from N to M per year') is read off the first and the
    last COMPLETE year — the partial year is excluded from that comparison, the same
    way oregon-audits#4's render() reads years[0] and the year before the partial one."""
    data = {
        "2020": {"performance": ["a", "b", "c", "d"]},
        "2021": {"performance": ["e", "f"]},
        "2022": {"performance": ["g"]},
    }
    stats = decline_stats(data, partial_year="2022")
    assert stats["perf_first"] == 4
    assert stats["perf_last_complete"] == 2
    assert stats["last_complete_year"] == "2021"


def test_decline_stats_with_no_partial_year_reads_the_final_year():
    data = {"2020": {"performance": ["a", "b"]}, "2021": {"performance": ["c"]}}
    stats = decline_stats(data, partial_year=None)
    assert stats["perf_first"] == 2
    assert stats["perf_last_complete"] == 1
    assert stats["last_complete_year"] == "2021"


def test_decline_stats_totals_every_report_across_years_and_types():
    data = {"2020": {"performance": ["a"], "financial": ["b", "c"]},
            "2021": {"performance": ["d"]}}
    stats = decline_stats(data, partial_year=None)
    assert stats["n_total"] == 4


def test_the_fetch_ledger_condenses_per_report_rows_into_one_citable_entry():
    """250 directory entries + 250 report fetches would be 250 near-identical rows in
    the page footer; the footer should cite the listing and ONE entry that still hashes
    every report's own (url, sha256) rather than the raw-bytes list."""
    data_sources.FETCHED[:] = [
        {"label": "listing", "url": "https://api.github.com/.../reports", "sha256": "L"},
        {"label": "a", "url": "https://raw/.../2020-01.md", "sha256": "h1"},
        {"label": "b", "url": "https://raw/.../2020-02.md", "sha256": "h2"},
    ]
    _condense_fetch_ledger()
    assert len(data_sources.FETCHED) == 2
    assert data_sources.FETCHED[0]["label"] == "listing"
    assert "2 mirrored reports" in data_sources.FETCHED[1]["label"]
    assert data_sources.FETCHED[1]["sha256"]

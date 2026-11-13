"""Port of ERF's statute-operationalization chart (oregon-stories#2): rebuilt here from
ERF's published artifacts (_meta/graph.json, _meta/catalog/agencies.yml,
_meta/catalog/ors.yml), never from that corpus's own viz/ page.

Seams: `rank_chapters(edges, orgs, chapters)` (the rows the page's bars are read off)
and `build()` with the network boundary (`fetch`) served from a committed excerpt of
the real artifacts. The excerpt's `expected_rows` come from ERF's own page, so the
oracle is the chart being ported, not a recomputation of this code.
"""
import json
import pathlib

import pytest

from stories import statute_operationalization as so

FX = json.loads((pathlib.Path(__file__).parent / "fixtures" /
                 "statute_operationalization_excerpt.json").read_text(encoding="utf-8"))


def _rank():
    return so.rank_chapters(FX["edges"], FX["organizations"], FX["chapters"])


def test_rows_reproduce_the_chart_being_ported_for_the_excerpted_chapters():
    rows, _ = _rank()
    assert rows == sorted(FX["expected_rows"], key=lambda r: -r["n"])


def test_total_links_counts_every_implementing_rule_edge_once():
    _, total = _rank()
    assert total == sum(r["n"] for r in FX["expected_rows"])


def test_only_ors_to_oar_implemented_by_edges_are_counted():
    edges = [
        {"from": "ors-1.001", "to": "oar-100-001-0010", "type": "implemented_by"},
        {"from": "oar-100-001-0010", "to": "ors-1.001", "type": "implements"},
        {"from": "ors-1.001", "to": "eo-22-11", "type": "implemented_by"},
        {"from": "ors-1.001", "to": "oar-100-001-0020", "type": "related"},
    ]
    orgs = [{"slug": "a", "name": "Dept A", "oar_chapter": "100"}]
    rows, total = so.rank_chapters(edges, orgs, [{"chapter": "1", "title": "Courts"}])
    assert total == 1 and rows[0]["n"] == 1 and rows[0]["ch"] == "1"
    assert rows[0]["title"] == "Courts"


def test_a_rule_whose_oar_chapter_has_no_registered_agency_is_unassigned_not_dropped():
    edges = [{"from": "ors-5.010", "to": "oar-999-001-0010", "type": "implemented_by"}]
    rows, total = so.rank_chapters(edges, [], [])
    assert total == 1
    assert rows[0]["top"] == [{"a": "(unassigned)", "n": 1}]
    assert rows[0]["title"] == ""


def test_a_chapter_with_a_letter_suffix_is_keyed_and_titled_upper_case():
    edges = [{"from": "ors-543a.010", "to": "oar-100-001-0010", "type": "implemented_by"}]
    orgs = [{"slug": "a", "name": "Department of Water", "oar_chapter": "100"}]
    rows, _ = so.rank_chapters(edges, orgs, [{"chapter": "543A", "title": "Water"}])
    assert rows[0]["ch"] == "543A" and rows[0]["title"] == "Water"
    assert rows[0]["top"][0]["a"] == "Dept. of Water"


def test_top_keeps_four_agencies_and_agencies_counts_all():
    rows, _ = _rank()
    r97 = next(r for r in rows if r["ch"] == "97")
    assert len(r97["top"]) == 4 and r97["agencies"] == 7


def _fake_fetch(url, label):
    if url.endswith("graph.json"):
        body = {"nodes": [], "edges": FX["edges"]}
    elif url.endswith("agencies.yml"):
        import yaml
        return yaml.safe_dump({"organizations": FX["organizations"]}).encode()
    elif url.endswith("ors.yml"):
        import yaml
        return yaml.safe_dump({"chapters": FX["chapters"]}).encode()
    else:
        raise AssertionError(f"unexpected fetch {url}")
    return json.dumps(body).encode()


def test_build_renders_a_page_from_the_fetched_artifacts_without_network(monkeypatch):
    monkeypatch.setattr(so, "fetch", _fake_fetch)
    slug, claim, page = so.build()
    assert slug == "statute-operationalization"
    assert "4 ORS chapters" in claim
    assert "Non-authoritative" in page
    assert "ORS 97" in page or '"ch":"97"' in page
    # never reads a corpus repo's rendered page
    assert "viz/" not in page


def test_page_states_the_counts_are_rules_naming_a_chapter_not_a_verdict():
    rows, total = _rank()
    page = so.render(rows, total)
    assert "not" in page.lower() and "Non-authoritative" in page


def test_link_stats_separates_links_from_distinct_rules_and_chapter_rule_pairs():
    edges = [
        {"from": "ors-1.001", "to": "oar-100-001-0010", "type": "implemented_by"},
        {"from": "ors-1.002", "to": "oar-100-001-0010", "type": "implemented_by"},  # same rule+chapter
        {"from": "ors-2.001", "to": "oar-100-001-0010", "type": "implemented_by"},  # same rule, 2nd chapter
        {"from": "ors-2.001", "to": "oar-100-001-0020", "type": "implemented_by"},
        {"from": "oar-100-001-0020", "to": "ors-2.001", "type": "implements"},      # ignored
    ]
    assert so.link_stats(edges) == {"links": 4, "rules": 2, "chapter_rule_pairs": 3}


def test_page_labels_the_unit_as_links_and_states_the_distinct_rule_count_from_data():
    stats = {"links": 10, "rules": 4, "chapter_rule_pairs": 6}
    rows, total = _rank()
    page = so.render(rows, total, stats=stats)
    assert "rule-to-section links" in page
    assert "10 links" in page and "4 distinct rules" in page and "6 chapter" in page

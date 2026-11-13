"""The manifest gate, offline: stories.yml is the one list of what the platform
publishes, and build.py trusts it. These checks need no network, so a bad entry fails
on the pull request instead of on the weekly Pages build."""
import importlib
import pathlib

import yaml

ENTRIES = yaml.safe_load(
    (pathlib.Path(__file__).resolve().parent.parent / "stories.yml").read_text(
        encoding="utf-8"))["stories"]
BY_ID = {e["id"]: e for e in ENTRIES}


def test_every_entry_has_a_unique_id_a_known_kind_and_status_and_corpora():
    assert len(BY_ID) == len(ENTRIES)
    for e in ENTRIES:
        assert e["kind"] in ("local", "external"), e["id"]
        assert e["status"] in ("published", "draft"), e["id"]
        assert e.get("corpora"), e["id"]
        assert e.get("title"), e["id"]


def test_a_local_entry_names_a_story_module_that_builds_and_carries_no_url():
    for e in ENTRIES:
        if e["kind"] != "local":
            continue
        mod = importlib.import_module(f"stories.{e['id']}")
        assert hasattr(mod, "build") or hasattr(mod, "build_many"), e["id"]
        assert "url" not in e, f"{e['id']}: a local story's URL is its built page"


def test_an_external_entry_names_the_page_it_indexes_and_its_claim():
    for e in ENTRIES:
        if e["kind"] == "external":
            assert e["url"].startswith("https://"), e["id"]
            assert e.get("claim"), e["id"]


def test_statute_operationalization_is_ported_to_a_local_story():
    e = BY_ID["statute_operationalization"]
    assert e["kind"] == "local" and e["status"] == "published"
    assert e["corpora"] == ["executive-regulatory-frameworks"]
    assert "erf_statute_operationalization" not in BY_ID

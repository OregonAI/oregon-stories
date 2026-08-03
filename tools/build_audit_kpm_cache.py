#!/usr/bin/env python3
"""Build data/semantic/audit_kpm.json — audits ↔ KPM by meaning, with the method's
own validity check published in the artifact.

  python3 tools/build_audit_kpm_cache.py

Same contract as build_semantic_cache.py (whose loaders this imports): numpy only,
reads the two corpora's local embeddings artifacts, writes a small committed cache
stamped with both fingerprints. Stories render the cache; they never recompute.

WHAT IT COMPUTES
1. THE VALIDITY CHECK, first, because it is the reason to believe anything else on
   the page: for every audit report carrying an agency_registry_slug, find the
   nearest KPM report by doc-mean cosine ACROSS ALL AGENCIES. The share whose
   nearest report belongs to the SAME agency is the recovery rate — the semantic
   index reconstructing a metadata join it never saw. Chance is ~1/n_kpm_slugs.
   Recovery is NOT accuracy: both corpora are the same agency writing about the
   same programs, so agency-level topical overlap is the null hypothesis.
2. THE PAIRS: for each audit whose agency has any KPM report, the nearest
   SAME-AGENCY KPM report + score, that report's reporting year, and its measures'
   at-target share for the year — actual vs target judged only where
   data_collection_period states a trend direction (the same rule
   what_agencies_told_the_legislature.py applies; measures without a stated
   direction are counted out loud, never guessed).
3. THE EXCLUSIONS, counted: audits with no registry slug, and audit agencies with
   no KPM counterpart.
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from build_semantic_cache import load_corpus, doc_means          # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AUD_REPO = Path("/home/dzinck/oregon-audits")
KPM_REPO = Path("/home/dzinck/oregon-kpm")
OUT = ROOT / "data" / "semantic" / "audit_kpm.json"

NUM = re.compile(r"-?[\d,]+\.?\d*")


def _fm(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8").split("---", 2)[1]) or {}


def _num(s):
    m = NUM.search(str(s or ""))
    return float(m.group(0).replace(",", "")) if m else None


def at_target(rows: list[dict], reporting_year: str) -> dict:
    """At-target share for one KPM report-year, by the sibling story's rule:
    judged only where the measure states its own trend direction."""
    met = judged = no_dir = no_num = 0
    for r in rows:
        if r.get("reporting_year") != reporting_year:
            continue
        a, t = _num(r.get("actual")), _num(r.get("target"))
        if a is None or t is None:
            no_num += 1
            continue
        dcp = (r.get("data_collection_period") or "").lower()
        up, down = "upward trend" in dcp, "downward trend" in dcp
        if not (up or down):
            no_dir += 1
            continue
        judged += 1
        if (up and a >= t) or (down and a <= t):
            met += 1
    return {"met": met, "judged": judged, "no_direction": no_dir, "no_number": no_num}


def main() -> int:
    aud_meta, aud_vecs, aud_ids = load_corpus(AUD_REPO / "_meta" / "embeddings")
    kpm_meta, kpm_vecs, kpm_ids = load_corpus(KPM_REPO / "_meta" / "embeddings")
    aud_docs, A = doc_means(aud_vecs, aud_ids)
    kpm_docs, K = doc_means(kpm_vecs, kpm_ids)

    aud_fm = {p.stem: _fm(p) for p in (AUD_REPO / "reports").glob("*.md")}
    kpm_slug = {p.stem: _fm(p).get("agency_registry_slug")
                for p in (KPM_REPO / "reports").glob("*.md")}
    kpm_year = {}
    series = json.load(open(KPM_REPO / "_meta" / "series.json"))["rows"]
    rows_by_doc: dict[str, list[dict]] = {}
    for r in series:
        rows_by_doc.setdefault(r["agency_doc"], []).append(r)

    kpm_index = {d: i for i, d in enumerate(kpm_docs)}
    sims = A @ K.T                                   # [n_aud, n_kpm]

    # 1. validity check — global nearest, does the agency match?
    slugged = [(i, d, aud_fm[d]["agency_registry_slug"]) for i, d in enumerate(aud_docs)
               if d in aud_fm and aud_fm[d].get("agency_registry_slug")]
    kpm_slugs_present = {s for s in kpm_slug.values() if s}
    recovered = 0
    for i, d, slug in slugged:
        nearest = kpm_docs[int(np.argmax(sims[i]))]
        if kpm_slug.get(nearest) == slug:
            recovered += 1

    # 2. within-agency nearest + at-target
    kpm_by_slug: dict[str, list[int]] = {}
    for doc, s in kpm_slug.items():
        if s and doc in kpm_index:
            kpm_by_slug.setdefault(s, []).append(kpm_index[doc])
    pairs, no_counterpart = [], set()
    for i, d, slug in slugged:
        idxs = kpm_by_slug.get(slug)
        if not idxs:
            no_counterpart.add(slug)
            continue
        best = max(idxs, key=lambda j: sims[i, j])
        kdoc = kpm_docs[best]
        krows = rows_by_doc.get(kdoc, [])
        ryear = max({r["reporting_year"] for r in krows}, default=None)
        pairs.append({
            "audit_id": d,
            "audit_title": aud_fm[d].get("title", d),
            "audit_type": aud_fm[d].get("audit_type"),
            "report_date": str(aud_fm[d].get("report_date") or ""),
            "agency_registry_slug": slug,
            "kpm_doc": kdoc,
            "score": round(float(sims[i, best]), 4),
            "kpm_reporting_year": ryear,
            "at_target": at_target(krows, ryear) if ryear else None,
        })
    pairs.sort(key=lambda p: -p["score"])

    out = {
        "generated": datetime.date.today().isoformat(),
        "model": aud_meta["model"],
        "audits_fingerprint": aud_meta["fingerprint"],
        "kpm_fingerprint": kpm_meta["fingerprint"],
        "note": ("Doc-mean cosine between oregon-audits and oregon-kpm embeddings. "
                 "Proximity SURFACES CANDIDATES, never findings: both corpora are the "
                 "same agencies writing about the same programs, so agency-level "
                 "overlap is the null hypothesis. The recovery rate is the method "
                 "check, not an accuracy claim."),
        "recovery": {
            "n_audits_slugged": len(slugged),
            "n_recovered_same_agency": recovered,
            "rate": round(recovered / len(slugged), 4) if slugged else None,
            "n_kpm_agency_slugs": len(kpm_slugs_present),
        },
        "excluded": {
            "audits_without_slug": len(aud_docs) - len(slugged),
            "audit_agencies_without_kpm": sorted(no_counterpart),
        },
        "n_pairs": len(pairs),
        "pairs": pairs,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(pairs)} pair(s); recovery "
          f"{recovered}/{len(slugged)} = {out['recovery']['rate']:.0%}; "
          f"{len(no_counterpart)} audit agencies without KPM counterpart")
    return 0


if __name__ == "__main__":
    sys.exit(main())

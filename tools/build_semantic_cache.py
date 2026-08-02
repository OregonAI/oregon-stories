#!/usr/bin/env python3
"""Build the committed semantic caches the semantic stories render from.

  python3 tools/build_semantic_cache.py

RUNS ONLY ON A MACHINE HOLDING THE EMBEDDING ARTIFACTS (gitignored in their corpora;
this is the same committed-cache pattern as ERF's topic-map UMAP cache: heavy compute
happens where the artifacts live, the derived, small, checkable result is committed,
and every cache records the artifact fingerprints it derives from). Stories NEVER
recompute this at build; they render the committed cache and print its provenance.

Outputs (data/semantic/):
  bridge.json     per audit report: nearest ERF rules/statutes by meaning, each marked
                  cited-or-not against the report's own citation edges
  twins.json      near-duplicate rule clusters across chapters (the copy-paste economy)
  authority.json  rules whose text is semantically farthest from the statute they cite
                  as authority — CANDIDATES for triage, never findings
"""
from __future__ import annotations

import datetime
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

ERF_EMB = Path("/home/dzinck/oregon-policy-repo/_meta/embeddings")
AUD_EMB = Path("/home/dzinck/oregon-audits/_meta/embeddings")
AUD_GRAPH = Path("/home/dzinck/oregon-audits/_meta/graph.json")
FRESH = Path("/home/dzinck/oregon-policy-repo/_meta/freshness.json")
OUT = Path(__file__).resolve().parent.parent / "data" / "semantic"


def load_corpus(emb_dir: Path):
    meta = json.loads((emb_dir / "meta.json").read_text())
    vecs = np.load(emb_dir / "vectors.i8.npy")
    ids = [json.loads(l)["doc_id"] for l in
           (emb_dir / "chunks.jsonl").read_text().splitlines()]
    assert len(ids) == vecs.shape[0] == meta["n_chunks"]
    return meta, vecs, ids


def doc_means(vecs: np.ndarray, ids: list[str]) -> tuple[list[str], np.ndarray]:
    """One L2-normalized float32 vector per document (mean of its chunks)."""
    order: list[str] = []
    ranges: dict[str, list[int]] = defaultdict(list)
    for i, d in enumerate(ids):
        if d not in ranges:
            order.append(d)
        ranges[d].append(i)
    out = np.zeros((len(order), vecs.shape[1]), dtype=np.float32)
    for j, d in enumerate(order):
        out[j] = vecs[ranges[d]].astype(np.float32).mean(axis=0)
    out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-9
    return order, out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    erf_meta, erf_vecs, erf_ids = load_corpus(ERF_EMB)
    aud_meta, aud_vecs, aud_ids = load_corpus(AUD_EMB)
    prov = {"generated": datetime.date.today().isoformat(),
            "model": erf_meta["model"],
            "erf_fingerprint": erf_meta["fingerprint"],
            "audits_fingerprint": aud_meta["fingerprint"],
            "method": "cosine over per-document mean of chunk vectors "
                      "(int8 L2*127 -> float32, renormalized)"}

    erf_docs, erf_M = doc_means(erf_vecs, erf_ids)
    idx_of = {d: i for i, d in enumerate(erf_docs)}
    law_mask = np.array([d.startswith(("oar-", "ors-")) for d in erf_docs])
    law_idx = np.where(law_mask)[0]
    law_M = erf_M[law_idx]
    law_docs = [erf_docs[i] for i in law_idx]

    # ---- 1. bridge: audit reports -> nearest law by meaning, vs their citations ----
    aud_docs, aud_M = doc_means(aud_vecs, aud_ids)
    cited = defaultdict(set)
    for e in json.loads(AUD_GRAPH.read_text())["edges"]:
        m = re.match(r"^ORS\s+(\d+[A-Z]?)\.(\d+[a-z]?)$", e["to"])
        if m:
            cited[e["from"]].add(f"ors-{m.group(1).lower()}.{m.group(2)}")
        m = re.match(r"^OAR\s+(\d+)-(\d+)-(\d+)$", e["to"])
        if m:
            cited[e["from"]].add(f"oar-{m.group(1)}-{m.group(2)}-{m.group(3)}")
    sims = aud_M @ law_M.T                       # 242 x n_law
    bridge = []
    n_top = 8
    for r, doc in enumerate(aud_docs):
        top = np.argsort(-sims[r])[:n_top]
        hits = [{"id": law_docs[t], "score": round(float(sims[r][t]), 3),
                 "cited": law_docs[t] in cited.get(doc, ())} for t in top]
        # chapter-level credit too: citing any section of the same chapter counts
        # toward "found by citation" (stricter section-match is also recorded)
        ch = lambda i: re.match(r"(oar-\d+|ors-\d+[a-z]?)", i).group(1)
        cited_ch = {ch(c) for c in cited.get(doc, ())}
        for h in hits:
            h["chapter_cited"] = ch(h["id"]) in cited_ch
        bridge.append({"report": doc, "n_cited_edges": len(cited.get(doc, ())),
                       "top": hits})
    (OUT / "bridge.json").write_text(json.dumps(
        {**prov, "n_reports": len(bridge), "reports": bridge}, indent=1))

    # ---- 2. twins: near-duplicate rules across the rulebook ----
    rule_idx = [i for i, d in enumerate(law_docs) if d.startswith("oar-")]
    R = law_M[rule_idx]
    rdocs = [law_docs[i] for i in rule_idx]
    THRESH = 0.985
    parent = list(range(len(rdocs)))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    pair_count = 0
    B = 2048
    for s in range(0, len(rdocs), B):
        block = R[s:s+B] @ R.T
        for bi in range(block.shape[0]):
            row = block[bi]
            i = s + bi
            js = np.where(row >= THRESH)[0]
            for j in js:
                if j <= i:
                    continue
                pa, pb = find(i), find(int(j))
                if pa != pb:
                    parent[pa] = pb
                pair_count += 1
    clusters = defaultdict(list)
    for i in range(len(rdocs)):
        clusters[find(i)].append(i)
    fams = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        docs = [rdocs[i] for i in members]
        chapters = sorted({d.split("-")[1] for d in docs})
        fams.append({"n": len(docs), "chapters": chapters,
                     "cross_chapter": len(chapters) > 1,
                     "members": sorted(docs)[:40]})
    fams.sort(key=lambda f: (-f["cross_chapter"], -len(f["chapters"]), -f["n"]))
    n_in_fams = sum(f["n"] for f in fams)
    (OUT / "twins.json").write_text(json.dumps(
        {**prov, "threshold": THRESH, "n_rules": len(rdocs),
         "n_rules_in_families": n_in_fams, "n_families": len(fams),
         "n_cross_chapter_families": sum(1 for f in fams if f["cross_chapter"]),
         "families": fams[:400]}, indent=1))

    # ---- 3. authority distance: rule text vs the statute it cites as authority ----
    fresh = json.loads(FRESH.read_text())
    rows = []
    for r in fresh["rules"]:
        sid = r.get("sid")
        ri, si = idx_of.get(r["id"]), idx_of.get(sid) if sid else None
        if ri is None or si is None:
            continue
        rows.append((r["id"], sid, float(erf_M[ri] @ erf_M[si]),
                     r.get("ag"), r.get("na")))
    rows.sort(key=lambda x: x[2])
    sims_all = np.array([x[2] for x in rows])
    (OUT / "authority.json").write_text(json.dumps(
        {**prov, "n_rules_scored": len(rows),
         "quartiles": [round(float(q), 3) for q in
                       np.percentile(sims_all, [5, 25, 50, 75, 95])],
         "farthest": [{"rule": a, "statute": b, "cos": round(c, 3), "agency": ag,
                       "n_authorities": na} for a, b, c, ag, na in rows[:60]],
         "nearest": [{"rule": a, "statute": b, "cos": round(c, 3)}
                     for a, b, c, *_ in rows[-5:]]}, indent=1))

    print(f"bridge: {len(bridge)} reports | twins: {len(fams)} families "
          f"({n_in_fams:,} rules, {sum(1 for f in fams if f['cross_chapter'])} "
          f"cross-chapter) | authority: {len(rows):,} rules scored, "
          f"p5={sims_all[int(len(rows)*.05)][0] if False else round(float(np.percentile(sims_all,5)),3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

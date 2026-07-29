#!/usr/bin/env python3
"""Fail closed when a daily digest is incomplete or malformed."""

import argparse
import json
import re
from collections import Counter

CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
VERSION_RE = re.compile(r"v\d+$")
SPACED_CHARACTER_RE = re.compile(r"(?:\b[A-Za-z]\s+){8,}[A-Za-z]\b")


def canonical_id(paper_id: str) -> str:
    return VERSION_RE.sub("", paper_id.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json_file")
    args = parser.parse_args()

    with open(args.json_file, encoding="utf-8") as handle:
        data = json.load(handle)

    errors = []
    papers = data.get("papers", [])
    hf_papers = data.get("hf_daily_papers", [])
    all_records = papers + hf_papers

    if not papers:
        errors.append("papers list is empty")

    ids = [canonical_id(p.get("id", "")) for p in papers]
    duplicates = sorted(paper_id for paper_id, count in Counter(ids).items() if paper_id and count > 1)
    if duplicates:
        errors.append(f"duplicate canonical arXiv IDs in papers: {duplicates[:10]}")

    missing_zh = [
        p.get("id", "<missing-id>")
        for p in all_records
        if len(p.get("summary_zh", "").strip()) < 40
        or len(CHINESE_RE.findall(p.get("summary_zh", ""))) < 15
    ]
    if missing_zh:
        errors.append(f"missing Chinese summaries: {len(missing_zh)} records; sample={missing_zh[:10]}")

    missing_en = [
        p.get("id", "<missing-id>")
        for p in all_records
        if len(p.get("summary_en", "").strip()) < 40
    ]
    if missing_en:
        errors.append(f"missing/short English summaries: {len(missing_en)} records; sample={missing_en[:10]}")

    malformed_abstracts = [
        p.get("id", "<missing-id>")
        for p in all_records
        if SPACED_CHARACTER_RE.search(p.get("abstract", ""))
    ]
    if malformed_abstracts:
        errors.append(f"character-spaced abstracts: {len(malformed_abstracts)} records; sample={malformed_abstracts[:10]}")

    hf_missing_metadata = [
        p.get("id", "<missing-id>")
        for p in hf_papers
        if not p.get("authors") or not p.get("categories")
    ]
    if hf_missing_metadata:
        errors.append(f"HF papers missing authors/categories: {len(hf_missing_metadata)}; sample={hf_missing_metadata[:10]}")

    summaries_by_id = {}
    inconsistent = set()
    for paper in all_records:
        paper_id = canonical_id(paper.get("id", ""))
        signature = (
            paper.get("summary_en", "").strip(),
            paper.get("summary_zh", "").strip(),
        )
        if paper_id in summaries_by_id and summaries_by_id[paper_id] != signature:
            inconsistent.add(paper_id)
        summaries_by_id[paper_id] = signature
    if inconsistent:
        errors.append(f"inconsistent duplicate summaries: {sorted(inconsistent)[:10]}")

    if errors:
        for error in errors:
            print(f"[error] {error}")
        raise SystemExit(1)

    unique_ids = {canonical_id(p.get("id", "")) for p in all_records}
    print(
        "[info] Digest validation passed: "
        f"papers={len(papers)}, hf={len(hf_papers)}, "
        f"unique={len(unique_ids)}, chinese_summaries={len(all_records)}"
    )


if __name__ == "__main__":
    main()

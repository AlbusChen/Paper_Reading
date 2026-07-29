#!/usr/bin/env python3
"""Apply or update the persistent paper-summary cache."""

import argparse
import hashlib
import json
import re
from pathlib import Path

SUMMARY_FIELDS = ("summary_en", "summary_zh", "institutions", "topic_keywords")


def canonical_id(paper_id: str) -> str:
    return re.sub(r"v\d+$", "", paper_id.strip())


def abstract_fingerprint(paper: dict) -> str:
    text = " ".join(paper.get("abstract", "").split())
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_papers(data: dict):
    yield from data.get("papers", [])
    yield from data.get("hf_daily_papers", [])


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def apply_cache(data: dict, cache: dict) -> int:
    applied = 0
    for paper in iter_papers(data):
        cached = cache.get(canonical_id(paper.get("id", "")))
        if not cached or cached.get("abstract_sha256") != abstract_fingerprint(paper):
            continue
        for field in SUMMARY_FIELDS:
            if cached.get(field) not in (None, "", []):
                paper[field] = cached[field]
        if paper.get("summary_zh"):
            applied += 1
    return applied


def update_cache(data: dict, cache: dict) -> int:
    updated = 0
    for paper in iter_papers(data):
        if not paper.get("summary_zh"):
            continue
        paper_id = canonical_id(paper.get("id", ""))
        if not paper_id:
            continue
        record = {
            "title": paper.get("title", ""),
            "abstract_sha256": abstract_fingerprint(paper),
        }
        for field in SUMMARY_FIELDS:
            if field in paper:
                record[field] = paper[field]
        if cache.get(paper_id) != record:
            cache[paper_id] = record
            updated += 1
    return updated


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("apply", "update"))
    parser.add_argument("digest_json")
    parser.add_argument(
        "--cache",
        default="papers/summary_cache.json",
        help="Persistent cache path",
    )
    args = parser.parse_args()

    digest_path = Path(args.digest_json)
    cache_path = Path(args.cache)
    data = load_json(digest_path, {})
    cache = load_json(cache_path, {})

    if args.action == "apply":
        count = apply_cache(data, cache)
        with digest_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        print(f"[info] Applied cached summaries to {count} paper records")
        return

    count = update_cache(data, cache)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[info] Updated {count} summary cache records; total={len(cache)}")


if __name__ == "__main__":
    main()

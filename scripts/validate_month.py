#!/usr/bin/env python3
"""Validate a backfilled month for summary coverage and historical uniqueness."""

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

VERSION_RE = re.compile(r"v\d+$")


def canonical_id(paper_id: str) -> str:
    return VERSION_RE.sub("", paper_id.strip())


def page_papers(path: Path, require_summaries: bool = True):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    cards = soup.select(".paper-card")
    if require_summaries and len(cards) != len(soup.select(".summary-zh")):
        raise RuntimeError(
            f"{path}: cards={len(cards)} but Chinese summaries="
            f"{len(soup.select('.summary-zh'))}"
        )
    for card in cards:
        link = card.select_one(".paper-title a[href]")
        if not link or "/abs/" not in link.get("href", ""):
            raise RuntimeError(f"{path}: paper card lacks an arXiv abstract link")
        yield canonical_id(link["href"].rsplit("/", 1)[-1])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("month", help="Month in YYYY-MM form")
    parser.add_argument("--papers-dir", default="papers")
    parser.add_argument("--registry", default="papers/seen_papers.json")
    args = parser.parse_args()

    papers_dir = Path(args.papers_dir)
    month_pages = sorted((papers_dir / args.month).glob(f"{args.month}-??.html"))
    if not month_pages:
        raise SystemExit(f"No daily pages found for {args.month}")

    prior_ids = set()
    for path in sorted(papers_dir.glob("????-??/????-??-??.html")):
        if path.stem >= f"{args.month}-01":
            continue
        prior_ids.update(page_papers(path, require_summaries=False))

    registry_path = Path(args.registry)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_records = registry.get("papers", {})

    month_ids = {}
    errors = []
    card_count = 0
    for path in month_pages:
        for paper_id in page_papers(path):
            card_count += 1
            if paper_id in prior_ids:
                errors.append(f"{paper_id} in {path.stem} already appeared before {args.month}")
            if paper_id in month_ids:
                errors.append(
                    f"{paper_id} repeated in {path.stem}; first appeared in "
                    f"{month_ids[paper_id]}"
                )
            month_ids.setdefault(paper_id, path.stem)
            first_seen = registry_records.get(paper_id, {}).get("first_seen")
            if first_seen != path.stem:
                errors.append(
                    f"{paper_id} registry first_seen={first_seen}, page={path.stem}"
                )

    if errors:
        for error in errors[:50]:
            print(f"[error] {error}")
        raise SystemExit(f"Month validation failed with {len(errors)} errors")

    print(
        f"[info] Month validation passed: month={args.month}, "
        f"pages={len(month_pages)}, cards={card_count}, unique={len(month_ids)}, "
        f"prior_ids={len(prior_ids)}"
    )


if __name__ == "__main__":
    main()

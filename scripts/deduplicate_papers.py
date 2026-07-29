#!/usr/bin/env python3
"""Keep each canonical arXiv paper only on its earliest digest date."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

VERSION_RE = re.compile(r"v\d+$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def canonical_id(paper_id: str) -> str:
    return VERSION_RE.sub("", paper_id.strip())


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temp_path.replace(path)


def empty_registry() -> dict:
    return {"version": 1, "papers": {}}


def validate_date(date_string: str) -> str:
    datetime.strptime(date_string, "%Y-%m-%d")
    return date_string


def iter_daily_pages(papers_dir: Path):
    yield from sorted(papers_dir.glob("????-??/????-??-??.html"))


def paper_id_from_href(href: str) -> str:
    if "/abs/" not in href:
        return ""
    return canonical_id(href.rsplit("/", 1)[-1])


def rebuild_registry(papers_dir: Path, before: str | None) -> dict:
    registry = empty_registry()
    records = registry["papers"]
    for page_path in iter_daily_pages(papers_dir):
        date_string = page_path.stem
        if not DATE_RE.match(date_string):
            continue
        if before and date_string >= before:
            continue
        soup = BeautifulSoup(page_path.read_text(encoding="utf-8"), "html.parser")
        for card in soup.select(".paper-card"):
            link = card.select_one(".paper-title a[href]")
            if not link:
                continue
            paper_id = paper_id_from_href(link.get("href", ""))
            if not paper_id or paper_id in records:
                continue
            records[paper_id] = {
                "first_seen": date_string,
                "title": link.get_text(" ", strip=True),
            }
    return registry


def iter_digest_papers(data: dict):
    yield from data.get("papers", [])
    yield from data.get("hf_daily_papers", [])


def filter_digest(data: dict, registry: dict) -> tuple[dict, set[str]]:
    target_date = validate_date(data["date"])
    seen = registry.get("papers", {})
    excluded = {
        paper_id
        for paper_id, record in seen.items()
        if record.get("first_seen", target_date) < target_date
    }

    before_papers = len(data.get("papers", []))
    before_hf = len(data.get("hf_daily_papers", []))
    for key in ("papers", "hf_daily_papers"):
        filtered = []
        current_ids = set()
        for paper in data.get(key, []):
            paper_id = canonical_id(paper.get("id", ""))
            if not paper_id or paper_id in excluded or paper_id in current_ids:
                continue
            current_ids.add(paper_id)
            paper["id"] = paper_id
            filtered.append(paper)
        data[key] = filtered

    data["total"] = len(data.get("papers", []))
    data["history_dedup"] = {
        "raw_papers": before_papers,
        "raw_hf_daily_papers": before_hf,
        "excluded_paper_records": before_papers - len(data.get("papers", [])),
        "excluded_hf_records": before_hf - len(data.get("hf_daily_papers", [])),
        "registry_size": len(seen),
    }
    return data, excluded


def update_registry(data: dict, registry: dict) -> tuple[dict, int]:
    target_date = validate_date(data["date"])
    records = registry.setdefault("papers", {})
    updated = 0
    for paper in iter_digest_papers(data):
        paper_id = canonical_id(paper.get("id", ""))
        if not paper_id:
            continue
        existing = records.get(paper_id)
        if existing and existing.get("first_seen", target_date) <= target_date:
            continue
        records[paper_id] = {
            "first_seen": target_date,
            "title": paper.get("title", ""),
        }
        updated += 1
    return registry, updated


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    rebuild = subparsers.add_parser("rebuild")
    rebuild.add_argument("--papers-dir", default="papers")
    rebuild.add_argument("--before")
    rebuild.add_argument("--registry", default="papers/seen_papers.json")

    filter_command = subparsers.add_parser("filter")
    filter_command.add_argument("digest_json")
    filter_command.add_argument("--registry", default="papers/seen_papers.json")

    update = subparsers.add_parser("update")
    update.add_argument("digest_json")
    update.add_argument("--registry", default="papers/seen_papers.json")

    args = parser.parse_args()
    registry_path = Path(args.registry)

    if args.command == "rebuild":
        before = validate_date(args.before) if args.before else None
        registry = rebuild_registry(Path(args.papers_dir), before)
        save_json(registry_path, registry)
        print(
            f"[info] Rebuilt seen registry: papers={len(registry['papers'])}, "
            f"before={before or 'none'}"
        )
        return

    digest_path = Path(args.digest_json)
    data = load_json(digest_path, {})
    registry = load_json(registry_path, empty_registry())

    if args.command == "filter":
        before_count = len(data.get("papers", []))
        before_hf = len(data.get("hf_daily_papers", []))
        data, excluded = filter_digest(data, registry)
        save_json(digest_path, data)
        print(
            "[info] Historical deduplication: "
            f"papers={before_count}->{len(data.get('papers', []))}, "
            f"hf={before_hf}->{len(data.get('hf_daily_papers', []))}, "
            f"prior_registry_ids={len(excluded)}"
        )
        return

    registry, updated_count = update_registry(data, registry)
    save_json(registry_path, registry)
    print(
        f"[info] Updated seen registry: added={updated_count}, "
        f"total={len(registry['papers'])}"
    )


if __name__ == "__main__":
    main()

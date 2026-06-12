#!/usr/bin/env python3
"""
Fetch paper metadata from arxiv and HuggingFace Daily Papers.
Outputs a JSON file with paper list for the given date.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
import requests
import feedparser

ARXIV_CATEGORIES = ["cs.MA", "cs.AI", "cs.LG", "cs.CL"]
ARXIV_API = "http://export.arxiv.org/api/query"

# Keywords for the current research focus:
# 1. Single-agent vs multi-agent comparisons and heterogeneous settings.
# 2. Agent-agent communication forms, channels, and outcomes.
PRIMARY_KEYWORDS = [
    "multi-agent", "multiagent", "multi agent",
    "single-agent", "single agent",
    "single-agent vs multi-agent", "single agent vs multi agent",
    "single-agent versus multi-agent", "single agent versus multi agent",
    "agent communication", "agent-agent communication",
    "inter-agent communication", "agent coordination",
    "communication protocol", "communication efficiency",
    "cooperative agent",
    "agent collaboration", "decentralized", "swarm intelligence",
    "message passing between agents", "inter-agent communication",
    "heterogeneous agents", "heterogeneous multi-agent",
]

SECONDARY_KEYWORDS = [
    "llm agent", "language agent", "tool use",
    "agent framework", "agent system",
    "scalable agent", "distributed agent",
    "emergent communication", "collective intelligence",
    "agent network", "agent graph",
    "multi-agent debate", "multi-agent discussion",
    "deliberation", "role specialization", "division of labor",
    "communication bandwidth", "natural language communication",
    "multimodal communication", "symbolic communication",
    "non-verbal communication", "blackboard", "shared memory",
    "message passing", "agent conversation", "agent dialogue",
]

FOCUS_TRACK_KEYWORDS = {
    "single_vs_multi": [
        "single-agent vs multi-agent", "single agent vs multi agent",
        "single-agent versus multi-agent", "single agent versus multi agent",
        "single-agent", "single agent", "multi-agent comparison",
        "heterogeneous agents", "heterogeneous multi-agent",
        "homogeneous agents", "role specialization", "division of labor",
    ],
    "agent_communication": [
        "agent-agent communication", "agent communication",
        "inter-agent communication", "communication protocol",
        "message passing", "emergent communication",
        "natural language communication", "multimodal communication",
        "symbolic communication", "non-verbal communication",
        "shared memory", "blackboard", "agent dialogue",
    ],
}

FOCUS_2026_QUERIES = [
    ("single_vs_multi", 'all:"single agent" AND all:"multi agent"'),
    ("single_vs_multi", 'all:"single-agent" AND all:"multi-agent"'),
    ("single_vs_multi", 'all:"heterogeneous agents" AND all:"multi-agent"'),
    ("single_vs_multi", 'all:"role specialization" AND all:"multi-agent"'),
    ("agent_communication", 'all:"agent communication"'),
    ("agent_communication", 'all:"agent-agent communication"'),
    ("agent_communication", 'all:"inter-agent communication"'),
    ("agent_communication", 'all:"communication protocol" AND all:"agent"'),
    ("agent_communication", 'all:"emergent communication" AND all:"agents"'),
    ("agent_communication", 'all:"message passing" AND all:"multi-agent"'),
]

# Tech report keywords (big labs)
TECH_REPORT_ORGS = [
    "openai", "google deepmind", "deepmind", "meta ai", "fair",
    "microsoft research", "anthropic", "apple", "nvidia research",
    "alibaba", "baidu", "tencent", "huawei",
    "stanford", "mit", "cmu", "berkeley", "oxford",
]

TECH_REPORT_KEYWORDS = [
    "technical report", "tech report", "system report",
    "model card", "model report",
]


def score_paper(title: str, abstract: str) -> dict:
    """Score paper relevance. Returns dict with score and matched keywords."""
    text = (title + " " + abstract).lower()
    matched_primary = [kw for kw in PRIMARY_KEYWORDS if kw in text]
    matched_secondary = [kw for kw in SECONDARY_KEYWORDS if kw in text]
    track_matches = {
        track: [kw for kw in keywords if kw in text]
        for track, keywords in FOCUS_TRACK_KEYWORDS.items()
    }

    is_tech_report = any(kw in text for kw in TECH_REPORT_KEYWORDS)
    from_major_org = any(org in text for org in TECH_REPORT_ORGS)

    score = len(matched_primary) * 3 + len(matched_secondary) * 1
    if all(track_matches.get(track) for track in ("single_vs_multi", "agent_communication")):
        score += 3
    if is_tech_report and from_major_org:
        score += 5

    return {
        "score": score,
        "primary_matches": matched_primary,
        "secondary_matches": matched_secondary,
        "track_matches": track_matches,
        "is_tech_report": is_tech_report and from_major_org,
    }


def paper_from_arxiv_entry(entry, source: str, primary_category: str | None = None, focus_track: str | None = None) -> dict:
    """Normalize one arxiv feed entry to the local paper schema."""
    arxiv_id = entry.id.split("/abs/")[-1]
    paper = {
        "id": arxiv_id,
        "title": entry.title.replace("\n", " ").strip(),
        "authors": [a.name for a in entry.authors[:5]],
        "abstract": entry.summary.replace("\n", " ").strip(),
        "url": entry.link,
        "pdf_url": entry.link.replace("/abs/", "/pdf/"),
        "published": entry.published,
        "categories": [t.term for t in entry.tags],
        "source": source,
        "primary_category": primary_category or (entry.tags[0].term if entry.tags else "arxiv"),
    }
    if focus_track:
        paper["focus_track"] = focus_track
    paper["relevance"] = score_paper(paper["title"], paper["abstract"])
    return paper


def fetch_arxiv(date: datetime) -> list:
    """Fetch papers from arxiv submitted on the given date."""
    papers = []
    date_str = date.strftime("%Y%m%d")
    next_date = (date + timedelta(days=1)).strftime("%Y%m%d")

    for category in ARXIV_CATEGORIES:
        query = f"cat:{category} AND submittedDate:[{date_str}0000 TO {next_date}0000]"
        params = {
            "search_query": query,
            "start": 0,
            "max_results": 100,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            resp = requests.get(ARXIV_API, params=params, timeout=30)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                paper = paper_from_arxiv_entry(entry, source="arxiv", primary_category=category)
                papers.append(paper)
        except Exception as e:
            print(f"[warn] arxiv {category} fetch failed: {e}", file=sys.stderr)
        time.sleep(1)  # be nice to arxiv

    # Deduplicate by arxiv ID
    seen = set()
    unique = []
    for p in papers:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)
    return unique


def fetch_arxiv_by_ids(ids: list[str]) -> dict:
    """Fetch arxiv metadata for explicit IDs, returning a mapping by ID."""
    if not ids:
        return {}

    papers = {}
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        params = {"id_list": ",".join(batch), "max_results": len(batch)}
        try:
            resp = requests.get(ARXIV_API, params=params, timeout=30)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                arxiv_id = entry.id.split("/abs/")[-1]
                paper = paper_from_arxiv_entry(entry, source="arxiv")
                papers[arxiv_id] = paper
        except Exception as e:
            print(f"[warn] arxiv id lookup failed for {','.join(batch)}: {e}", file=sys.stderr)
        time.sleep(1)
    return papers


def fetch_arxiv_focus_2026(max_results: int = 80) -> list:
    """Fetch recent 2026 papers matching the current two-track focus."""
    papers = {}
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    per_query = max(10, min(30, max_results // max(1, len(FOCUS_2026_QUERIES)) + 1))

    for focus_track, focus_query in FOCUS_2026_QUERIES:
        query = f"({focus_query}) AND submittedDate:[202601010000 TO {today}2359]"
        params = {
            "search_query": query,
            "start": 0,
            "max_results": per_query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            resp = requests.get(ARXIV_API, params=params, timeout=30)
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                arxiv_id = entry.id.split("/abs/")[-1]
                paper = paper_from_arxiv_entry(
                    entry,
                    source="arxiv_focus_2026",
                    focus_track=focus_track,
                )
                paper["focus_query"] = focus_query
                existing = papers.get(arxiv_id)
                if existing:
                    existing_tracks = set(existing.get("focus_tracks", []))
                    existing_tracks.add(focus_track)
                    existing["focus_tracks"] = sorted(existing_tracks)
                    continue
                paper["focus_tracks"] = [focus_track]
                papers[arxiv_id] = paper
        except Exception as e:
            print(f"[warn] arxiv 2026 focus fetch failed for {focus_query}: {e}", file=sys.stderr)
        time.sleep(1)

    results = list(papers.values())
    results.sort(key=lambda p: (p["relevance"]["score"], p.get("published", "")), reverse=True)
    return results[:max_results]


def fetch_huggingface_detail(arxiv_id: str) -> dict:
    """Fetch title and abstract from a HuggingFace paper detail page."""
    url = f"https://huggingface.co/papers/{arxiv_id}"
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        title_el = soup.find("h1")
        abstract = ""
        abstract_header = soup.find(lambda tag: tag.name in {"h2", "h3"} and tag.get_text(strip=True) == "Abstract")
        if abstract_header:
            abstract_el = abstract_header.find_next("p")
            if abstract_el:
                abstract = abstract_el.get_text(" ", strip=True)
        if not abstract:
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            abstract = max(paragraphs, key=len, default="")
        return {
            "title": title_el.get_text(" ", strip=True) if title_el else "",
            "abstract": abstract,
        }
    except Exception as e:
        print(f"[warn] HuggingFace detail fetch failed for {arxiv_id}: {e}", file=sys.stderr)
        return {}


def fetch_huggingface(date: datetime) -> list:
    """Fetch HuggingFace Daily Papers for the given date."""
    date_str = date.strftime("%Y-%m-%d")
    url = f"https://huggingface.co/papers?date={date_str}"
    papers = []
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # HF papers page: each paper is in an article element
        articles = soup.find_all("article")
        for article in articles:
            title_el = article.find("h3") or article.find("h2")
            link_el = article.find("a", href=True)
            abstract_el = article.find("p")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            href = link_el["href"]
            if href.startswith("/papers/"):
                arxiv_id = href.replace("/papers/", "").strip()
                abstract = abstract_el.get_text(strip=True) if abstract_el else ""
                paper = {
                    "id": arxiv_id,
                    "title": title,
                    "authors": [],
                    "abstract": abstract,
                    "url": f"https://arxiv.org/abs/{arxiv_id}",
                    "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                    "published": date_str,
                    "categories": [],
                    "source": "huggingface_daily",
                    "primary_category": "HF Daily",
                }
                relevance = score_paper(title, abstract)
                paper["relevance"] = relevance
                papers.append(paper)
    except Exception as e:
        print(f"[warn] HuggingFace fetch failed: {e}", file=sys.stderr)

    # The HF listing often omits abstracts. Enrich from HF detail pages first so
    # fallback pages still have useful text and relevance scores when Codex fails.
    for paper in papers:
        if paper.get("abstract"):
            continue
        detail = fetch_huggingface_detail(paper["id"])
        if not detail:
            continue
        paper["title"] = detail.get("title") or paper["title"]
        paper["abstract"] = detail.get("abstract", "")
        paper["relevance"] = score_paper(paper["title"], paper["abstract"])
        time.sleep(0.2)

    # Use arxiv as a secondary metadata source for any entries still missing
    # abstracts, and for richer author/category metadata when available.
    metadata = fetch_arxiv_by_ids([p["id"] for p in papers if not p.get("abstract")])
    for paper in papers:
        enriched = metadata.get(paper["id"])
        if not enriched:
            continue
        paper.update({
            "title": enriched["title"] or paper["title"],
            "authors": enriched["authors"],
            "abstract": enriched["abstract"],
            "url": enriched["url"],
            "pdf_url": enriched["pdf_url"],
            "published": enriched["published"],
            "categories": enriched["categories"],
            "primary_category": enriched["primary_category"],
            "hf_daily": True,
        })
        paper["relevance"] = score_paper(paper["title"], paper["abstract"])
    return papers


def main():
    parser = argparse.ArgumentParser(description="Fetch papers for a given date")
    parser.add_argument(
        "--date",
        default=None,
        help="Date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="Minimum relevance score to include (default: 0, include all)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file (default: stdout)",
    )
    parser.add_argument(
        "--include-2026-focus",
        action="store_true",
        help="Also include recent 2026 arxiv papers for the current focus topics",
    )
    parser.add_argument(
        "--max-focus-results",
        type=int,
        default=80,
        help="Maximum number of 2026 focus papers to merge when --include-2026-focus is used",
    )
    args = parser.parse_args()

    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        target_date = datetime.now(timezone.utc) - timedelta(days=1)
        target_date = target_date.replace(tzinfo=None)

    print(f"[info] Fetching papers for {target_date.strftime('%Y-%m-%d')} ...", file=sys.stderr)

    arxiv_papers = fetch_arxiv(target_date)
    print(f"[info] arxiv: {len(arxiv_papers)} papers", file=sys.stderr)

    hf_papers = fetch_huggingface(target_date)
    print(f"[info] HuggingFace: {len(hf_papers)} papers", file=sys.stderr)
    focus_papers = []
    if args.include_2026_focus:
        focus_papers = fetch_arxiv_focus_2026(args.max_focus_results)
        print(f"[info] arxiv 2026 focus: {len(focus_papers)} papers", file=sys.stderr)

    # Merge: prefer arxiv metadata if same ID appears in both
    all_ids = {p["id"]: p for p in arxiv_papers}
    for p in hf_papers:
        if p["id"] not in all_ids:
            all_ids[p["id"]] = p
        else:
            # Mark as also featured on HF Daily
            all_ids[p["id"]]["hf_daily"] = True
    for p in focus_papers:
        if p["id"] not in all_ids:
            all_ids[p["id"]] = p
        else:
            all_ids[p["id"]]["focus_2026"] = True
            all_ids[p["id"]]["focus_tracks"] = sorted(set(
                all_ids[p["id"]].get("focus_tracks", []) + p.get("focus_tracks", [])
            ))

    papers = list(all_ids.values())
    papers.sort(key=lambda p: p["relevance"]["score"], reverse=True)

    if args.min_score > 0:
        papers = [p for p in papers if p["relevance"]["score"] >= args.min_score]

    result = {
        "date": target_date.strftime("%Y-%m-%d"),
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total": len(papers),
        "papers": papers,
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[info] Saved to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

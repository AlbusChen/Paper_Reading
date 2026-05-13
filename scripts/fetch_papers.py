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

ARXIV_CATEGORIES = ["cs.MA", "cs.AI", "cs.LG"]
ARXIV_API = "http://export.arxiv.org/api/query"

# Keywords for multi-agent efficiency/communication focus
PRIMARY_KEYWORDS = [
    "multi-agent", "multiagent", "multi agent",
    "agent communication", "agent coordination",
    "communication efficiency", "multi-agent efficiency",
    "cooperative agent", "agent collaboration",
    "decentralized", "swarm intelligence",
    "message passing between agents", "inter-agent communication",
]

SECONDARY_KEYWORDS = [
    "llm agent", "language agent", "tool use",
    "agent framework", "agent system",
    "scalable agent", "distributed agent",
    "emergent communication", "collective intelligence",
    "agent network", "agent graph",
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

    is_tech_report = any(kw in text for kw in TECH_REPORT_KEYWORDS)
    from_major_org = any(org in text for org in TECH_REPORT_ORGS)

    score = len(matched_primary) * 3 + len(matched_secondary) * 1
    if is_tech_report and from_major_org:
        score += 5

    return {
        "score": score,
        "primary_matches": matched_primary,
        "secondary_matches": matched_secondary,
        "is_tech_report": is_tech_report and from_major_org,
    }


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
                    "source": "arxiv",
                    "primary_category": category,
                }
                relevance = score_paper(paper["title"], paper["abstract"])
                paper["relevance"] = relevance
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

    # Merge: prefer arxiv metadata if same ID appears in both
    all_ids = {p["id"]: p for p in arxiv_papers}
    for p in hf_papers:
        if p["id"] not in all_ids:
            all_ids[p["id"]] = p
        else:
            # Mark as also featured on HF Daily
            all_ids[p["id"]]["hf_daily"] = True

    papers = list(all_ids.values())
    papers.sort(key=lambda p: p["relevance"]["score"], reverse=True)

    if args.min_score > 0:
        papers = [p for p in papers if p["relevance"]["score"] >= args.min_score]

    result = {
        "date": target_date.strftime("%Y-%m-%d"),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
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

#!/usr/bin/env python3
"""Generate grounded bilingual summaries through batched Codex CLI calls."""

import argparse
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
VERSION_RE = re.compile(r"v\d+$")
SUMMARY_FIELDS = ("summary_en", "summary_zh", "institutions", "topic_keywords")


def canonical_id(paper_id: str) -> str:
    return VERSION_RE.sub("", paper_id.strip())


def compact_text(value) -> str:
    return " ".join(str(value or "").split())


def iter_papers(data: dict):
    yield from data.get("papers", [])
    yield from data.get("hf_daily_papers", [])


def has_valid_summary(paper: dict) -> bool:
    summary_en = compact_text(paper.get("summary_en", ""))
    summary_zh = compact_text(paper.get("summary_zh", ""))
    return (
        len(summary_en) >= 40
        and len(summary_zh) >= 40
        and len(CHINESE_RE.findall(summary_zh)) >= 15
    )


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json_atomic(path: Path, data: dict):
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(path)


def synchronize_existing_summaries(data: dict):
    summaries = {}
    for paper in iter_papers(data):
        if has_valid_summary(paper):
            summaries.setdefault(
                canonical_id(paper.get("id", "")),
                {field: paper.get(field, [] if field in {"institutions", "topic_keywords"} else "")
                 for field in SUMMARY_FIELDS},
            )
    for paper in iter_papers(data):
        summary = summaries.get(canonical_id(paper.get("id", "")))
        if not summary:
            continue
        for field, value in summary.items():
            paper[field] = value


def unique_missing_papers(data: dict) -> list[dict]:
    first_by_id = {}
    order = []
    groups = {}
    for paper in iter_papers(data):
        paper_id = canonical_id(paper.get("id", ""))
        if not paper_id:
            continue
        if paper_id not in first_by_id:
            first_by_id[paper_id] = paper
            groups[paper_id] = []
            order.append(paper_id)
        groups[paper_id].append(paper)
    return [
        first_by_id[paper_id]
        for paper_id in order
        if any(not has_valid_summary(paper) for paper in groups[paper_id])
    ]


def input_record(paper: dict) -> dict:
    return {
        "id": canonical_id(paper.get("id", "")),
        "title": compact_text(paper.get("title", "")),
        "abstract": compact_text(paper.get("abstract", "")),
        "authors": paper.get("authors", []),
        "categories": paper.get("categories", []),
        "source": paper.get("source", ""),
        "is_hf_daily": bool(paper.get("hf_daily")),
    }


def build_batches(papers: list[dict], max_items: int, max_chars: int):
    batch = []
    char_count = 0
    for paper in papers:
        record = input_record(paper)
        size = len(json.dumps(record, ensure_ascii=False))
        if batch and (len(batch) >= max_items or char_count + size > max_chars):
            yield batch
            batch = []
            char_count = 0
        batch.append(record)
        char_count += size
    if batch:
        yield batch


def parse_json_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start:end + 1])


def validate_model_results(records: list[dict], response: dict) -> dict:
    papers = response.get("papers") if isinstance(response, dict) else None
    if not isinstance(papers, list):
        raise RuntimeError("Codex output is missing the papers list")

    results = {
        canonical_id(str(paper.get("id", ""))): paper
        for paper in papers
        if isinstance(paper, dict)
    }
    expected_ids = {record["id"] for record in records}
    if set(results) != expected_ids:
        raise RuntimeError(
            f"Codex ID mismatch: expected={sorted(expected_ids)}, got={sorted(results)}"
        )

    cleaned = {}
    for record in records:
        paper_id = record["id"]
        result = results[paper_id]
        summary_en = compact_text(result.get("summary_en", ""))
        summary_zh = compact_text(result.get("summary_zh", ""))
        if len(summary_en) < 40:
            raise RuntimeError(f"English summary is too short for {paper_id}")
        if len(summary_zh) < 40 or len(CHINESE_RE.findall(summary_zh)) < 15:
            raise RuntimeError(f"Chinese summary is too short for {paper_id}")

        keywords = result.get("topic_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        keywords = [compact_text(keyword) for keyword in keywords if compact_text(keyword)][:4]
        if len(keywords) < 2:
            raise RuntimeError(f"Too few topic keywords for {paper_id}")

        try:
            score = int(result.get("relevance_score", 0))
        except (TypeError, ValueError):
            raise RuntimeError(f"Invalid relevance score for {paper_id}") from None
        if not 0 <= score <= 9:
            raise RuntimeError(f"Out-of-range relevance score for {paper_id}: {score}")

        cleaned[paper_id] = {
            "summary_en": summary_en,
            "summary_zh": summary_zh,
            "institutions": [],
            "topic_keywords": keywords,
            "relevance_score": score,
        }
    return cleaned


def run_codex_batch(
    records: list[dict],
    *,
    codex: str,
    prompt_text: str,
    timeout: int,
) -> dict:
    prompt = (
        prompt_text.rstrip()
        + "\n\nInput papers JSON array:\n"
        + json.dumps(records, ensure_ascii=False)
    )
    with tempfile.NamedTemporaryFile(
        mode="w+",
        encoding="utf-8",
        delete=False,
        dir="/tmp",
        prefix="paper_summary_batch_",
        suffix=".json",
    ) as output:
        output_path = Path(output.name)

    try:
        command = [
            codex,
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--cd",
            "/tmp",
            "-c",
            'model_reasoning_effort="low"',
            "--output-last-message",
            str(output_path),
            "-",
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        if completed.returncode:
            detail = (completed.stderr or completed.stdout).strip()[-2400:]
            raise RuntimeError(f"Codex exited {completed.returncode}: {detail}")
        response = parse_json_response(output_path.read_text(encoding="utf-8"))
        return validate_model_results(records, response)
    finally:
        output_path.unlink(missing_ok=True)


def summarize_resilient(
    records: list[dict],
    *,
    codex: str,
    prompt_text: str,
    timeout: int,
) -> dict:
    try:
        return run_codex_batch(
            records,
            codex=codex,
            prompt_text=prompt_text,
            timeout=timeout,
        )
    except Exception as error:
        print(f"[warn] Summary batch of {len(records)} failed: {error}", flush=True)
        if len(records) == 1:
            time.sleep(2)
            return run_codex_batch(
                records,
                codex=codex,
                prompt_text=prompt_text,
                timeout=timeout,
            )
        midpoint = len(records) // 2
        summaries = summarize_resilient(
            records[:midpoint],
            codex=codex,
            prompt_text=prompt_text,
            timeout=timeout,
        )
        summaries.update(
            summarize_resilient(
                records[midpoint:],
                codex=codex,
                prompt_text=prompt_text,
                timeout=timeout,
            )
        )
        return summaries


def apply_summaries(data: dict, summaries: dict) -> int:
    applied = 0
    for paper in iter_papers(data):
        summary = summaries.get(canonical_id(paper.get("id", "")))
        if not summary:
            continue
        for field in SUMMARY_FIELDS:
            paper[field] = summary[field]
        relevance = paper.get("relevance")
        if isinstance(relevance, dict):
            relevance["score"] = summary["relevance_score"]
        applied += 1
    return applied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("digest_json")
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--prompt", default="scripts/daily_prompt.md")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--max-input-chars", type=int, default=42_000)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    digest_path = Path(args.digest_json)
    prompt_text = Path(args.prompt).read_text(encoding="utf-8")
    data = load_json(digest_path)
    synchronize_existing_summaries(data)
    save_json_atomic(digest_path, data)

    missing = unique_missing_papers(data)
    batches = list(build_batches(missing, args.batch_size, args.max_input_chars))
    print(
        f"[info] Summary target: unique_missing={len(missing)}, batches={len(batches)}",
        flush=True,
    )

    processed = 0
    for batch_number, records in enumerate(batches, start=1):
        paper_ids = [record["id"] for record in records]
        print(
            f"[info] Summary batch {batch_number}/{len(batches)}: "
            f"size={len(records)}, first={paper_ids[0]}, last={paper_ids[-1]}",
            flush=True,
        )
        summaries = summarize_resilient(
            records,
            codex=args.codex,
            prompt_text=prompt_text,
            timeout=args.timeout,
        )
        data = load_json(digest_path)
        applied = apply_summaries(data, summaries)
        save_json_atomic(digest_path, data)
        processed += len(records)
        print(
            f"[info] Saved summaries: canonical={processed}/{len(missing)}, "
            f"records_applied={applied}",
            flush=True,
        )

    data = load_json(digest_path)
    synchronize_existing_summaries(data)
    remaining = unique_missing_papers(data)
    if remaining:
        raise RuntimeError(f"Summary generation incomplete: {len(remaining)} papers remain")
    save_json_atomic(digest_path, data)
    print("[info] All bilingual summaries generated", flush=True)


if __name__ == "__main__":
    main()

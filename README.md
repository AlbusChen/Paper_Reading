# Paper Reading Collection

Daily paper digest focused on **single-agent vs multi-agent systems** and **agent-agent communication**.  
Hosted on GitHub Pages: **https://AlbusChen.github.io/Paper_Reading**

---

## Topics of Interest

**Primary track A: single-agent vs multi-agent**
- Comparisons of single-agent and multi-agent systems
- When one setting is stronger or weaker
- Heterogeneous vs homogeneous agent settings, role specialization, division of labor
- Methods that reduce the gap between single-agent and multi-agent setups

**Primary track B: agent-agent communication**
- Natural-language, structured-text, shared-memory, blackboard, message-passing, tool-mediated, multimodal, symbolic, or non-text communication
- Communication protocols, bandwidth/cost constraints, and emergent communication
- How communication form affects performance, robustness, coordination, and cost

**Also collect:**
- LLM-based agents, agent orchestration, tool use, agent frameworks, multi-agent debate/discussion
- AI/LLM technical reports from major labs when they include agent, orchestration, communication, or multi-agent evaluation content
- Hugging Face Daily Papers as a separate broad module, excluding 3D, robotics, image generation, video generation, and music generation topics

---

## Repository Structure

```
Paper_Reading/
├── scripts/
│   ├── fetch_papers.py       # Fetch paper metadata from arxiv + HuggingFace
│   ├── generate_html.py      # Generate bilingual HTML digest from JSON
│   ├── run_daily.sh          # Cron entry point: fetch → summarize → HTML → push
│   ├── daily_prompt.md       # Instructions for the daily Codex agent session
│   └── requirements.txt
├── papers/                   # Generated HTML files (tracked in git → GitHub Pages)
│   ├── index.html            # Main landing page
│   ├── YYYY-MM/
│   │   ├── index.html        # Monthly index
│   │   └── YYYY-MM-DD.html   # Daily digest
│   └── logs/                 # Cron run logs (gitignored)
├── index.html                # Root redirect → papers/index.html (for GitHub Pages)
└── README.md
```

---

## Daily Update Workflow

### Schedule
Cron runs at **01:30 UTC (09:30 CST)** every day, covering the **previous day's** papers.

```
crontab entry:
30 9 * * * mkdir -p /raid/longhorn/huangchen/Paper_Reading/papers/logs && \
           /raid/longhorn/huangchen/Paper_Reading/scripts/run_daily.sh
```

### Step-by-step Process

**Step 1 — Fetch paper metadata** (`fetch_papers.py`)

Pulls paper titles, authors, abstracts, and URLs from:
- **arxiv API**: categories `cs.MA`, `cs.AI`, `cs.LG`, `cs.CL`, filtered for papers submitted on the target date
- **HuggingFace Daily Papers**: scrapes `https://huggingface.co/papers?date=YYYY-MM-DD`
- **2026 focus search**: optional arxiv search over 2026 papers matching the current two research tracks

Each paper is scored by keyword matching (primary keywords score ×3, secondary ×1, with a bonus for papers touching both tracks). Output is a JSON file at `/tmp/papers_YYYY-MM-DD.json`. The JSON also includes `hf_daily_papers`, a separate Hugging Face Daily module filtered only to remove 3D, robotics, image-generation, video-generation, and music-generation topics.

> **Note**: The arxiv API occasionally rejects connections from this server. If all three arxiv categories fail, fall back to WebFetch: search `https://arxiv.org/search/?searchtype=all&query=multi-agent&order=-announced_date_first` and manually identify papers submitted on the target date.

**Step 2 — Read and evaluate each paper** (Codex agent, via `daily_prompt.md`)

The daily Codex session (`codex exec --cd "$REPO_DIR" --dangerously-bypass-approvals-and-sandbox - < scripts/daily_prompt.md`) reads the candidate list and:

1. For papers with `relevance.score >= 3`: fetches the full arxiv abstract page via `WebFetch` (`https://arxiv.org/abs/PAPER_ID`)
2. Reads the abstract carefully and re-scores based on actual content (keyword scoring produces false positives)
3. Writes two fields into the JSON for each relevant paper:
   - `summary_en`: 2–3 sentence English summary — what problem, what method, key result, and relevance to the two tracks
   - `summary_zh`: 2–3 sentence Chinese summary (中文学术风格，可补充背景)
   - `institutions`: main author affiliations or organizations, when visible from arxiv/Hugging Face/PDF metadata
   - Optional `topic_keywords`: 2–4 compact labels for page/index discovery
4. Writes bilingual summaries and institutions for `hf_daily_papers` using a broader paper-summary lens, without forcing them into the two-track research framing
5. Adjusts `relevance.score` to reflect true relevance (override keyword score)

**Relevance scoring guide:**
| Score | Meaning |
|-------|---------|
| 7–9 | Directly about single-vs-multi comparison or agent-agent communication |
| 5–6 | Related to heterogeneous agents, communication protocols, orchestration, or agent architecture |
| 3–4 | Tangentially related agent or multi-agent work |
| 1–2 | False positive or very loosely related |
| 0 | Drop entirely |

**Step 3 — Generate HTML** (`generate_html.py`)

Reads the updated JSON and writes:
- `papers/YYYY-MM/YYYY-MM-DD.html` — daily digest with bilingual summaries
- `papers/YYYY-MM/index.html` — monthly index (updated)
- `papers/index.html` — main index showing last 14 days (updated)

Papers are grouped into sections: ⭐ Highly Relevant (score ≥ 6) → 🏢 Tech Reports → ◆ Relevant (3–5) → · Others.
When available, the page also includes a separate 🤗 Hugging Face Daily / Broad Picks module before the research-focused sections.
Paper cards show institutions when the daily reading step identifies them.

**Step 4 — Push to GitHub**

```bash
git add papers/*.html papers/*/*.html index.html
git commit -m "Daily digest YYYY-MM-DD" --author="Codex Bot <noreply@openai.com>"
git push origin main
```

GitHub Pages auto-deploys within ~1 minute of push.

---

## Running Manually

```bash
cd /raid/longhorn/huangchen/Paper_Reading

# Fetch metadata for a specific date plus current 2026 focus papers
python3 scripts/fetch_papers.py --date 2026-05-13 --include-2026-focus --output /tmp/papers.json

# After manually adding summary_en / summary_zh fields to the JSON:
python3 scripts/generate_html.py /tmp/papers.json

# Push
git add papers/ index.html && git commit -m "Manual digest YYYY-MM-DD" && git push
```

---

## Environment

- **Server**: `/raid/longhorn/huangchen/Paper_Reading`
- **Python**: `/raid/longhorn/huangchen/anaconda3/bin/python3`
- **Codex CLI**: `/raid/longhorn/huangchen/anaconda3/bin/codex`
- **Git remote**: `git@github.com:AlbusChen/Paper_Reading.git` (SSH)
- **Dependencies**: `pip install feedparser requests beautifulsoup4`

---

## Known Issues

- arxiv API (`export.arxiv.org`) occasionally returns `Connection reset by peer` for this server's IP. Workaround: use `WebFetch` on `arxiv.org/search/` to manually find papers submitted on the target date, then fetch individual abstract pages.
- `papers/logs/` is gitignored. Check `papers/logs/YYYY-MM-DD.log` to debug cron failures.

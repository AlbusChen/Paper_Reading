# Daily Paper Collection Agent Instructions

You are running as a scheduled daily paper collection agent. Your task is to:

1. **Fetch paper metadata** for yesterday's date
2. **Read and evaluate each paper** from the candidate list
3. **Write bilingual summaries** (English + Chinese) for relevant papers
4. **Generate the HTML digest** for the day

## Step 1: Set date and fetch

Run:
```bash
cd /raid/longhorn/huangchen/Paper_Reading
DATE=$(date -d "yesterday" +%Y-%m-%d)
python3 scripts/fetch_papers.py --date $DATE --output /tmp/papers_${DATE}.json
```

## Step 2: Read the candidate list

Load the JSON and identify:
- Papers with score >= 3 (relevant, read abstract carefully)
- Papers with score >= 6 (highly relevant, read full abstract + possibly skim introduction)
- Tech reports from major labs (always include regardless of score)

Focus on papers about:
- **Primary**: multi-agent efficiency, communication protocols, coordination mechanisms
- **Primary**: agent communication overhead, scalability of multi-agent systems
- **Secondary**: LLM-based agents, tool use efficiency, agent frameworks
- **Include**: AI/LLM technical reports from major labs (OpenAI, DeepMind, Meta AI, Anthropic, NVIDIA, Microsoft Research, major universities)

## Step 3: For each relevant paper, fetch the abstract page

Use WebFetch on the arxiv abstract URL (https://arxiv.org/abs/PAPER_ID) to:
- Read the full abstract
- Note key contributions and methods
- Assess relevance to multi-agent efficiency/communication

## Step 4: Write summaries into the JSON

For each paper you've read, add to the JSON:
- `summary_en`: 2-3 sentence English summary focusing on: what problem, what method, key result
- `summary_zh`: 2-3 sentence Chinese summary (同一内容的中文表达，可适当补充背景)

Format for summary_zh: Concise Chinese academic style. Example:
"本文提出了一种基于图注意力网络的多智能体通信协议，通过自适应选择通信邻居降低了通信开销。实验显示在StarCraft II任务上比基线方法提升了15%的胜率，同时减少60%的通信量。"

## Step 5: Update JSON and generate HTML

Save the updated JSON with summaries, then run:
```bash
python3 scripts/generate_html.py /tmp/papers_${DATE}.json
```

## Step 6: Verify output

Check that the HTML file was created:
```bash
ls -lh /raid/longhorn/huangchen/Paper_Reading/papers/${DATE:0:7}/${DATE}.html
```

Open and verify the structure looks correct.

## Quality Guidelines

- **Be selective**: if a paper is only marginally related, mark it as low relevance
- **Be accurate**: summaries must reflect the actual paper content
- **Be concise**: summaries should be 2-3 sentences max
- **Tech reports**: always include AI/LLM tech reports from major labs even if not agent-focused
- If arxiv is slow, use exponential backoff between requests
- If a paper's abstract is too short to summarize, use the available text as-is

## Output confirmation

After completion, report:
- Total papers processed
- High relevance count
- Papers with full summaries written
- HTML file path generated

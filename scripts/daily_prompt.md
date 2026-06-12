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
python3 scripts/fetch_papers.py --date $DATE --include-2026-focus --output /tmp/papers_${DATE}.json
```

## Step 2: Read the candidate list

Load the JSON and identify:
- Papers with score >= 3 (relevant, read abstract carefully)
- Papers with score >= 6 (highly relevant, read full abstract + possibly skim introduction)
- Tech reports from major labs when they contain agent, orchestration, communication, or multi-agent evaluation content

Focus on two research tracks:
- **Track A: single-agent vs multi-agent**. Prioritize papers that compare single-agent and multi-agent systems, identify when one setting is stronger or weaker, study task/context heterogeneity, or propose mechanisms to close the gap between the two settings.
- **Track B: agent-agent communication**. Prioritize papers about how agents communicate with each other: natural language, structured text, tool calls, shared memory/blackboards, message passing, multimodal or non-text signals, bandwidth constraints, communication protocols, and how these choices affect performance, robustness, cost, coordination, or emergent behavior.
- **Secondary**: LLM-based agents, agent orchestration, tool use, agent frameworks, role specialization, heterogeneous agents, and multi-agent debate/discussion when they provide evidence for Track A or Track B.
- **Include**: AI/LLM technical reports from major labs only when they contain material relevant to agents, orchestration, communication, or multi-agent evaluation.
- **Date scope**: include yesterday's papers, but also consider relevant 2026 papers found by the focus search. Recent 2026 papers are acceptable even if they were not posted yesterday.

## Step 3: For each relevant paper, fetch the abstract page

Use live web search or direct network fetches on the arxiv abstract URL (https://arxiv.org/abs/PAPER_ID) to:
- Read the full abstract
- Note key contributions and methods
- Assess relevance to single-vs-multi agent settings or agent-agent communication

## Step 4: Write summaries into the JSON

For each paper you've read, add to the JSON:
- `summary_en`: 2-3 sentence English summary focusing on: what problem, what method, key result, and what it says about single-vs-multi or agent-agent communication.
- `summary_zh`: 2-3 sentence Chinese summary (同一内容的中文表达，可适当补充背景)
- If useful, add `topic_keywords`: 2-4 short labels such as `single-vs-multi`, `heterogeneous agents`, `language communication`, `shared memory`, `message passing`, `multimodal communication`, or `communication cost`.

Format for summary_zh: Concise Chinese academic style. Example:
"本文比较了单智能体与多智能体在长程规划任务中的表现，发现多智能体在需要角色分工和并行探索时更强，但在信息整合成本高的场景下会被通信开销抵消。作者进一步提出结构化消息协议来降低跨智能体冗余交流，实验显示该协议在保持成功率的同时减少了通信轮数。"

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
- **Tech reports**: include AI/LLM tech reports from major labs when they have agent, communication, orchestration, or multi-agent evaluation content
- If arxiv is slow, use exponential backoff between requests
- If a paper's abstract is too short to summarize, use the available text as-is

## Output confirmation

After completion, report:
- Total papers processed
- High relevance count
- Papers with full summaries written
- HTML file path generated

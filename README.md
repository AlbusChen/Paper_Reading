# Paper Reading Collection

Daily paper digest focused on **multi-agent system efficiency and communication**.

## Structure

```
scripts/        # Fetch and HTML generation utilities (tracked in git)
papers/         # Daily HTML digests — local only, not tracked
```

## Topics

- Multi-agent system efficiency
- Agent communication protocols
- Cooperative/coordination mechanisms
- AI/LLM tech reports from major labs

## Sources

- arxiv: cs.MA, cs.AI, cs.LG
- HuggingFace Daily Papers

## Running Manually

```bash
python3 scripts/fetch_papers.py --date YYYY-MM-DD
```

## Schedule

Automated daily run at 09:30 CST via cron. Covers previous day's papers.

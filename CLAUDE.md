# Reddit Need Research

Deep market research system that enriches Reddit need signals into actionable product insights.

## Usage
```
python src/main.py <input.json or dir/> [-c 3] [-o output/] [--dry-run] [--limit N]
```

## Architecture
- main.py: CLI + asyncio orchestration with semaphore concurrency
- researcher.py: spawns `claude -p --model claude-opus-4-6` per record, writes .md
- prompt.py: research prompt template (most important file)
- config.py: defaults (model, concurrency, timeout)

## Key decisions
- Output is raw Markdown from Claude stdout (no parsing)
- Concurrency default 3 (Opus is slow/expensive)
- 10 min timeout per session
- No retry logic -- failures show in index.md, re-run with filtered input

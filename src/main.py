"""CLI entry point for Reddit Need Research."""

import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime

from src.config import DEFAULT_CONCURRENCY, DEFAULT_MODEL, DEFAULT_OUTPUT_DIR, DEFAULT_TIMEOUT
from src.researcher import run_research

log = logging.getLogger("research")


def load_records(path: str) -> list[dict]:
    """Load records from a JSON file or all JSON files in a directory."""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else [data]
    elif os.path.isdir(path):
        records = []
        for fname in sorted(os.listdir(path)):
            if fname.endswith(".json"):
                with open(os.path.join(path, fname), encoding="utf-8") as f:
                    data = json.load(f)
                    records.extend(data if isinstance(data, list) else [data])
        return records
    else:
        raise FileNotFoundError(f"Path not found: {path}")


def write_index(results: list[dict], output_dir: str) -> None:
    """Write index.md summarizing all research reports."""
    ok = sum(1 for r in results if r["success"])
    lines = [
        "# Reddit Need Research Index",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\nTotal: {len(results)} | Successful: {ok} | Failed: {len(results) - ok}",
        "\n## Reports\n",
    ]
    for r in results:
        if r["success"]:
            lines.append(f"- [{r['title']}]({r['filename']}) ({r['elapsed']:.0f}s)")
        else:
            lines.append(f"- ~~{r['title']}~~ -- FAILED: {r.get('error', 'unknown')}")

    with open(os.path.join(output_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Index written to %s/index.md", output_dir)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deep market research from Reddit need signals")
    parser.add_argument("input", help="JSON file or directory of JSON files")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--limit", type=int, default=None, help="Process only first N records")
    parser.add_argument("--dry-run", action="store_true", help="List records without researching")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%H:%M:%S",
    )

    records = load_records(args.input)
    if args.limit:
        records = records[: args.limit]
    log.info("Loaded %d records from %s", len(records), args.input)

    if args.dry_run:
        for i, r in enumerate(records):
            print(f"  {i+1}. [{r.get('subreddit', '?')}] {r.get('title', 'untitled')}")
        return

    os.makedirs(args.output, exist_ok=True)
    sem = asyncio.Semaphore(args.concurrency)

    async def bounded(record):
        async with sem:
            return await run_research(record, args.output, args.model, args.timeout)

    log.info("Starting research: concurrency=%d, model=%s", args.concurrency, args.model)
    t0 = time.monotonic()
    results = await asyncio.gather(*[bounded(r) for r in records])
    elapsed = time.monotonic() - t0

    write_index(results, args.output)

    ok = sum(1 for r in results if r["success"])
    log.info("--- Done in %.1fs: %d/%d succeeded ---", elapsed, ok, len(results))


if __name__ == "__main__":
    asyncio.run(main())

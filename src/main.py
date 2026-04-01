"""CLI entry point for Reddit Need Research."""

import argparse
import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime

from src.config import DEFAULT_CONCURRENCY, DEFAULT_MODEL, DEFAULT_OUTPUT_DIR, DEFAULT_TIMEOUT
from src.researcher import run_research, sanitize_filename

log = logging.getLogger("research")

# Map Chinese CSV column names to internal field names
CSV_COLUMN_MAP = {
    "标题": "title",
    "Select": "select",
    "userDefined:URL": "url",
    "付费意愿": "willingness_to_pay",
    "匹配关键词": "matched_keyword",
    "子版块": "subreddit",
    "帖子摘要": "post_summary",
    "点赞数": "upvotes",
    "热门评论": "top_comments_summary",
    "现有解决方案": "existing_solutions",
    "竞品": "competitors_mentioned",
    "研究状态": "research_status",
}


def load_records(path: str) -> list[dict]:
    """Load records from a JSON file, CSV file, or directory of JSON files."""
    if os.path.isfile(path):
        if path.endswith(".csv"):
            return _load_csv(path)
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


def _load_csv(path: str) -> list[dict]:
    """Load records from a CSV file, mapping Chinese column names."""
    records = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {}
            for csv_col, internal_key in CSV_COLUMN_MAP.items():
                if csv_col in row:
                    record[internal_key] = row[csv_col]
            # Keep original CSV column names too for marking back
            record["_csv_row"] = dict(row)
            records.append(record)
    return records


def mark_csv_status(csv_path: str, title: str, status: str) -> None:
    """Update the research status column for a specific row in the CSV."""
    rows = []
    fieldnames = None
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Add status column if not present
    if "研究状态" not in fieldnames:
        fieldnames.append("研究状态")

    for row in rows:
        if row.get("标题") == title:
            row["研究状态"] = status
            break

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def is_already_done(record: dict, output_dir: str) -> bool:
    """Check if this record has already been successfully researched."""
    title = record.get("title", "untitled")
    filename = sanitize_filename(title) + ".md"
    filepath = os.path.join(output_dir, filename)
    # Consider done if output file exists and is substantial (>1KB)
    return os.path.isfile(filepath) and os.path.getsize(filepath) > 1024


def write_index(results: list[dict], output_dir: str) -> None:
    """Write index.md summarizing all research reports."""
    ok = sum(1 for r in results if r["success"])
    skipped = sum(1 for r in results if r.get("skipped"))
    lines = [
        "# Reddit Need Research Index",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\nTotal: {len(results)} | Successful: {ok} | Skipped (already done): {skipped} | Failed: {len(results) - ok - skipped}",
        "\n## Reports\n",
    ]
    for r in results:
        if r.get("skipped"):
            lines.append(f"- [{r['title']}]({r['filename']}) (skipped, already done)")
        elif r["success"]:
            lines.append(f"- [{r['title']}]({r['filename']}) ({r['elapsed']:.0f}s)")
        else:
            lines.append(f"- ~~{r['title']}~~ -- FAILED: {r.get('error', 'unknown')}")

    with open(os.path.join(output_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Index written to %s/index.md", output_dir)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Deep market research from Reddit need signals")
    parser.add_argument("input", help="JSON file, CSV file, or directory of JSON files")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("-c", "--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("-m", "--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--limit", type=int, default=None, help="Process only first N records")
    parser.add_argument("--dry-run", action="store_true", help="List records without researching")
    parser.add_argument("--no-resume", action="store_true", help="Re-run all records even if already done")
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
            done = is_already_done(r, args.output)
            marker = " [DONE]" if done else ""
            print(f"  {i+1}. [{r.get('subreddit', '?')}] {r.get('title', 'untitled')}{marker}")
        return

    os.makedirs(args.output, exist_ok=True)
    is_csv = args.input.endswith(".csv")
    sem = asyncio.Semaphore(args.concurrency)
    results = []

    async def process_one(record):
        title = record.get("title", "untitled")
        filename = sanitize_filename(title) + ".md"

        # Resume: skip already-completed records
        if not args.no_resume and is_already_done(record, args.output):
            log.info("[%s] Already done, skipping", title[:40])
            return {"title": title, "filename": filename, "success": True,
                    "elapsed": 0, "error": None, "skipped": True}

        async with sem:
            result = await run_research(record, args.output, args.model, args.timeout)

        # Mark in CSV if successful
        if is_csv and result["success"]:
            try:
                mark_csv_status(args.input, record.get("_csv_row", {}).get("标题", title), "已完成")
            except Exception as e:
                log.warning("Failed to mark CSV status: %s", e)

        return result

    log.info("Starting research: concurrency=%d, model=%s", args.concurrency, args.model)
    t0 = time.monotonic()

    # Process sequentially to allow graceful interruption and CSV marking
    tasks = [process_one(r) for r in records]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle exceptions from gather
    final_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            title = records[i].get("title", "untitled")
            log.error("[%s] Exception: %s", title[:40], r)
            final_results.append({"title": title, "filename": "", "success": False,
                                  "elapsed": 0, "error": str(r)})
        else:
            final_results.append(r)

    elapsed = time.monotonic() - t0
    write_index(final_results, args.output)

    ok = sum(1 for r in final_results if r["success"])
    skipped = sum(1 for r in final_results if r.get("skipped"))
    failed = len(final_results) - ok - skipped
    log.info("--- Done in %.1fs: %d succeeded, %d skipped, %d failed ---",
             elapsed, ok - skipped, skipped, failed)


if __name__ == "__main__":
    asyncio.run(main())

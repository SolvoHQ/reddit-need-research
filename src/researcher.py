"""Spawns claude -p research sessions."""

import asyncio
import logging
import os
import re
import time

from src.prompt import build_research_prompt

log = logging.getLogger("research")


def sanitize_filename(title: str) -> str:
    """Convert a title to a safe filename."""
    name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return name[:80]


async def run_research(
    record: dict,
    output_dir: str,
    model: str,
    timeout: int,
) -> dict:
    """Run a single research session. Returns result metadata dict."""
    title = record.get("title", "untitled")
    filename = sanitize_filename(title) + ".md"
    filepath = os.path.join(output_dir, filename)
    tag = f"[{title[:40]}]"

    prompt = build_research_prompt(record)
    log.info("%s Starting research...", tag)
    t0 = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "--model", model, prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        log.error("%s Timed out after %.1fs", tag, elapsed)
        return {"title": title, "filename": filename, "success": False,
                "elapsed": elapsed, "error": "timeout"}

    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        log.error("%s Failed (exit %d, %.1fs)", tag, proc.returncode, elapsed)
        return {"title": title, "filename": filename, "success": False,
                "elapsed": elapsed, "error": stderr.decode()[:500]}

    markdown = stdout.decode().strip()
    log.info("%s Done in %.1fs (%d bytes)", tag, elapsed, len(markdown))

    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    return {"title": title, "filename": filename, "success": True,
            "elapsed": elapsed, "error": None}

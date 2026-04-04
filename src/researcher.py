"""Spawns claude -p research sessions."""

import asyncio
import hashlib
import json
import logging
import os
import re
import time

from src.prompt import build_research_prompt

log = logging.getLogger("research")

MIN_REPORT_SIZE = 1024  # minimum bytes for a valid report


def sanitize_filename(title: str) -> str:
    """Convert a title to a safe filename.

    For titles with mostly non-ASCII characters (e.g. Chinese),
    falls back to a short hash to avoid empty or colliding names.
    """
    name = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if len(name) < 4:
        # Title was mostly non-ASCII; use hash prefix + whatever ASCII we got
        hash_prefix = hashlib.md5(title.encode()).hexdigest()[:10]
        name = f"{hash_prefix}-{name}" if name else hash_prefix
    return name[:80]


async def _run_claude(prompt: str, model: str, timeout: int, tag: str) -> tuple[str, float, str | None]:
    """Run a single claude -p session. Returns (markdown, elapsed, error)."""
    t0 = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", "--output-format", "json", "--model", model, prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - t0
        return "", elapsed, "timeout"

    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        return "", elapsed, stderr.decode("utf-8", errors="replace")[:500]

    # Parse JSON output and extract the result text
    raw = stdout.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        markdown = data.get("result", "").strip()
    except json.JSONDecodeError:
        # Fallback: treat as plain text
        markdown = raw.strip()

    return markdown, elapsed, None


async def run_research(
    record: dict,
    output_dir: str,
    model: str,
    timeout: int,
) -> dict:
    """Run a single research session with auto-retry on short output."""
    title = record.get("title", "untitled")
    filename = sanitize_filename(title) + ".md"
    filepath = os.path.join(output_dir, filename)
    tag = f"[{title[:40]}]"

    prompt = build_research_prompt(record)
    max_attempts = 2
    total_elapsed = 0

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log.info("%s Retry attempt %d (previous output too short)", tag, attempt)

        log.info("%s Starting research...", tag)
        markdown, elapsed, error = await _run_claude(prompt, model, timeout, tag)
        total_elapsed += elapsed

        if error:
            log.error("%s Failed: %s (%.1fs)", tag, error, elapsed)
            if attempt < max_attempts:
                continue
            return {"title": title, "filename": filename, "success": False,
                    "elapsed": total_elapsed, "error": error}

        log.info("%s Done in %.1fs (%d bytes)", tag, elapsed, len(markdown))

        # Strip chain-of-thought leakage before the first heading
        heading_pos = markdown.find("# ")
        if heading_pos > 0:
            log.debug("%s Stripped %d bytes of pre-heading text", tag, heading_pos)
            markdown = markdown[heading_pos:]

        if len(markdown) < MIN_REPORT_SIZE:
            log.warning("%s Output too short (%d bytes < %d), %s",
                        tag, len(markdown), MIN_REPORT_SIZE,
                        "retrying..." if attempt < max_attempts else "giving up")
            if attempt < max_attempts:
                continue
            # Last attempt: save whatever we got but mark as failed
            if markdown:
                os.makedirs(output_dir, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(markdown)
            return {"title": title, "filename": filename, "success": False,
                    "elapsed": total_elapsed, "error": f"output too short ({len(markdown)} bytes)"}

        # Success: write the report
        os.makedirs(output_dir, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)

        return {"title": title, "filename": filename, "success": True,
                "elapsed": total_elapsed, "error": None}

    # Should not reach here, but just in case
    return {"title": title, "filename": filename, "success": False,
            "elapsed": total_elapsed, "error": "unexpected end of retry loop"}

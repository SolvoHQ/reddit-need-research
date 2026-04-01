import asyncio
from unittest.mock import AsyncMock, patch
from src.researcher import sanitize_filename, run_research


def test_sanitize_basic():
    assert sanitize_filename("Looking for a tool") == "looking-for-a-tool"


def test_sanitize_special_chars():
    assert sanitize_filename("What's the best $5/mo app?") == "what-s-the-best-5-mo-app"


def test_sanitize_truncates_long_titles():
    long_title = "a" * 100
    result = sanitize_filename(long_title)
    assert len(result) <= 80


def test_sanitize_unicode():
    assert sanitize_filename("Müller's café tool") == "m-ller-s-caf-tool"


def test_sanitize_chinese_title():
    result = sanitize_filename("有没有漫画管理的推荐")
    assert len(result) >= 4  # should use hash fallback
    assert result  # not empty


def test_sanitize_chinese_with_ascii():
    result = sanitize_filename("有没有 App 帮助从多张相似照片中选出最佳？")
    assert len(result) >= 4  # "app" alone is < 4, so hash fallback kicks in
    assert "app" in result


def test_run_research_success(tmp_path):
    record = {"title": "Test Post", "url": "https://reddit.com/test"}
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"# Report\nContent here", b""))

    with patch("src.researcher.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = asyncio.run(run_research(record, str(tmp_path), "claude-opus-4-6", 600))

    assert result["success"] is True
    assert result["title"] == "Test Post"
    assert (tmp_path / "test-post.md").read_text() == "# Report\nContent here"


def test_run_research_failure(tmp_path):
    record = {"title": "Fail Post"}
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error msg"))

    with patch("src.researcher.asyncio.create_subprocess_exec", return_value=mock_proc):
        result = asyncio.run(run_research(record, str(tmp_path), "claude-opus-4-6", 600))

    assert result["success"] is False
    assert "error msg" in result["error"]
    assert not (tmp_path / "fail-post.md").exists()

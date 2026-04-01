import csv
import json
from src.main import load_records, write_index, is_already_done, mark_csv_status


def test_load_records_single_file(tmp_path):
    data = [{"title": "A"}, {"title": "B"}]
    f = tmp_path / "needs.json"
    f.write_text(json.dumps(data))
    assert load_records(str(f)) == data


def test_load_records_directory(tmp_path):
    f1 = tmp_path / "a.json"
    f1.write_text(json.dumps([{"title": "A"}]))
    f2 = tmp_path / "b.json"
    f2.write_text(json.dumps([{"title": "B"}]))
    result = load_records(str(tmp_path))
    assert len(result) == 2


def test_load_records_single_object(tmp_path):
    f = tmp_path / "one.json"
    f.write_text(json.dumps({"title": "Solo"}))
    result = load_records(str(f))
    assert result == [{"title": "Solo"}]


def test_load_records_csv(tmp_path):
    f = tmp_path / "needs.csv"
    f.write_text(
        "\ufeff标题,Select,userDefined:URL,子版块,帖子摘要\n"
        "Test Post,可以研究,https://reddit.com/test,r/selfhosted,A summary\n",
        encoding="utf-8",
    )
    records = load_records(str(f))
    assert len(records) == 1
    assert records[0]["title"] == "Test Post"
    assert records[0]["url"] == "https://reddit.com/test"
    assert records[0]["subreddit"] == "r/selfhosted"
    assert "_csv_row" in records[0]


def test_write_index(tmp_path):
    results = [
        {"title": "Good", "filename": "good.md", "success": True, "elapsed": 30.0, "error": None},
        {"title": "Bad", "filename": "bad.md", "success": False, "elapsed": 5.0, "error": "timeout"},
    ]
    write_index(results, str(tmp_path))
    content = (tmp_path / "index.md").read_text()
    assert "[Good](good.md)" in content
    assert "FAILED" in content


def test_write_index_with_skipped(tmp_path):
    results = [
        {"title": "Done", "filename": "done.md", "success": True, "elapsed": 0, "error": None, "skipped": True},
    ]
    write_index(results, str(tmp_path))
    content = (tmp_path / "index.md").read_text()
    assert "already done" in content


def test_is_already_done(tmp_path):
    record = {"title": "Test Post"}
    assert not is_already_done(record, str(tmp_path))

    # Create a small file (< 1KB) — should not count as done
    (tmp_path / "test-post.md").write_text("short")
    assert not is_already_done(record, str(tmp_path))

    # Create a substantial file (> 1KB) — should count as done
    (tmp_path / "test-post.md").write_text("x" * 2000)
    assert is_already_done(record, str(tmp_path))


def test_mark_csv_status(tmp_path):
    csv_path = tmp_path / "needs.csv"
    csv_path.write_text(
        "\ufeff标题,Select,子版块\n"
        "Post A,可以研究,r/test\n"
        "Post B,可以研究,r/test\n",
        encoding="utf-8",
    )
    mark_csv_status(str(csv_path), "Post A", "已完成")

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert rows[0]["研究状态"] == "已完成"
    assert rows[1].get("研究状态", "") == ""

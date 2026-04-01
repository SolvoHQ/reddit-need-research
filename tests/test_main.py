import json
from src.main import load_records, write_index


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


def test_write_index(tmp_path):
    results = [
        {"title": "Good", "filename": "good.md", "success": True, "elapsed": 30.0, "error": None},
        {"title": "Bad", "filename": "bad.md", "success": False, "elapsed": 5.0, "error": "timeout"},
    ]
    write_index(results, str(tmp_path))
    content = (tmp_path / "index.md").read_text()
    assert "[Good](good.md)" in content
    assert "FAILED" in content

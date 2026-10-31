import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_checker():
    path = ROOT / "tools" / "check_text.py"
    spec = importlib.util.spec_from_file_location("check_text", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_text_has_no_problems(tmp_path):
    checker = load_checker()
    path = tmp_path / "clean.txt"
    path.write_text("Normal text with a hyphen and a period.\n", encoding="utf-8")
    assert checker.check_file(str(path)) == []


def test_em_dash_is_reported(tmp_path):
    checker = load_checker()
    path = tmp_path / "bad.txt"
    path.write_text("one \u2014 two\n", encoding="utf-8")
    problems = checker.check_file(str(path))
    assert len(problems) == 1
    assert "em dash" in problems[0]


def test_en_dash_is_reported(tmp_path):
    checker = load_checker()
    path = tmp_path / "bad.txt"
    path.write_text("one \u2013 two\n", encoding="utf-8")
    problems = checker.check_file(str(path))
    assert len(problems) == 1
    assert "en dash" in problems[0]


def test_banned_phrase_is_reported(tmp_path):
    checker = load_checker()
    path = tmp_path / "bad.txt"
    path.write_text("This is a " + "ro" + "bust" + " plan.\n", encoding="utf-8")
    problems = checker.check_file(str(path))
    assert len(problems) == 1
    assert "banned phrase" in problems[0]


def test_repository_text_check_passes(capsys):
    checker = load_checker()
    assert checker.main() == 0
    assert "Text check passed" in capsys.readouterr().out


def test_checker_ignores_working_directory_files(tmp_path, monkeypatch, capsys):
    checker = load_checker()
    (tmp_path / "NTUSER.DAT").write_bytes(b"\x00ro" + b"bust\x00")
    (tmp_path / "notes.md").write_text("ro" + "bust", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert checker.main() == 0
    assert "Text check passed" in capsys.readouterr().out


def test_tracked_files_only_returns_text_extensions():
    checker = load_checker()
    paths = list(checker.tracked_files())
    assert paths
    assert all(Path(path).suffix.lower() in checker.TEXT_SUFFIXES for path in paths)

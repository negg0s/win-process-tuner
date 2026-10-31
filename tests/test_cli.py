from click.testing import CliRunner

from win_process_tuner import cli as cli_mod


def test_list_command():
    runner = CliRunner()
    with patch_list():
        result = runner.invoke(cli_mod.cli, ["list", "--top", "2"])
    assert result.exit_code == 0


def test_inspect_command():
    runner = CliRunner()
    with patch_inspect():
        result = runner.invoke(cli_mod.cli, ["inspect", "5"])
    assert result.exit_code == 0
    assert "pid: 5" in result.output.lower() or "pid: 5" in result.output


def test_set_priority_dry_run():
    runner = CliRunner()
    with patch_set_priority():
        result = runner.invoke(cli_mod.cli, ["set-priority", "5", "--level", "high", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_set_affinity_dry_run():
    runner = CliRunner()
    with patch_set_affinity():
        result = runner.invoke(cli_mod.cli, ["set-affinity", "5", "--cpus", "0,2", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_timer_dry_run():
    runner = CliRunner()
    with patch_timer():
        result = runner.invoke(cli_mod.cli, ["timer-resolution", "--ms", "5", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_profile_dry_run():
    runner = CliRunner()
    with patch_profile():
        result = runner.invoke(cli_mod.cli, ["profile", "apply", "gaming", "--pid", "5", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_doctor_command():
    runner = CliRunner()
    result = runner.invoke(cli_mod.cli, ["doctor"])
    assert result.exit_code == 0


# helpers

from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def patch_list():
    with patch("win_process_tuner.cli.list_processes", return_value=[
        {"pid": 1, "name": "a", "cpu": 1.0, "memory": 100, "status": "running"}
    ]):
        yield


@contextmanager
def patch_inspect():
    with patch("win_process_tuner.cli.inspect_process", return_value={
        "pid": 5, "name": "x", "status": "running", "cpu_percent": 1.0,
        "memory_rss": 50, "num_threads": 2, "cpu_affinity": [0, 1],
        "nice": 8, "create_time": 1.0, "exe": "x", "cmdline": ["x"],
    }):
        yield


@contextmanager
def patch_set_priority():
    with patch("win_process_tuner.cli.set_priority", return_value={
        "pid": 5, "level": "high", "current": 8, "new": 128, "changed": True, "dry_run": True,
    }):
        yield


@contextmanager
def patch_set_affinity():
    with patch("win_process_tuner.cli.set_affinity", return_value={
        "pid": 5, "current": [0, 1], "new": [0, 2], "changed": True, "dry_run": True,
    }):
        yield


@contextmanager
def patch_timer():
    with patch("win_process_tuner.cli.apply_timer_resolution", return_value={
        "ms": 5, "action": "timeBeginPeriod", "dry_run": True,
        "would_call": "timeBeginPeriod(5)",
    }):
        yield


@contextmanager
def patch_profile():
    with patch("win_process_tuner.cli.apply_gaming_profile", return_value={
        "pid": 5, "profile": "gaming", "priority": "high",
        "affinity": [0, 2, 4, 6], "dry_run": True,
    }):
        with patch("win_process_tuner.profile.physical_cores_heuristic", return_value=[0, 2, 4, 6]):
            yield

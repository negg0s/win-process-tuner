import json
from unittest.mock import patch

import psutil
import pytest
from click.testing import CliRunner

from win_process_tuner import cli as cli_mod
from win_process_tuner.safety import SafetyError


def invoke(args):
    return CliRunner().invoke(cli_mod.cli, args)


def test_help():
    result = invoke(["--help"])
    assert result.exit_code == 0
    assert "timer-resolution" in result.output


def test_list_command():
    rows = [
        {"pid": 1, "name": "a", "cpu": 1.0, "memory": 100, "status": "running", "denied": False}
    ]
    with patch("win_process_tuner.cli.list_processes", return_value=rows):
        result = invoke(["list", "--top", "2"])
    assert result.exit_code == 0
    assert "PID" in result.output
    assert "a" in result.output


def test_list_json():
    rows = [
        {"pid": 2, "name": "b", "cpu": None, "memory": None, "status": "denied", "denied": True},
        {"pid": 1, "name": "a", "cpu": 1.0, "memory": 100, "status": "running", "denied": False},
    ]
    with patch("win_process_tuner.cli.list_processes", return_value=rows):
        result = invoke(["list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert [row["pid"] for row in data] == [2, 1]
    assert data[0]["denied"] is True


def test_list_renders_denied_values():
    rows = [
        {
            "pid": 2,
            "name": "<access denied>",
            "cpu": None,
            "memory": None,
            "status": "denied",
            "denied": True,
        }
    ]
    with patch("win_process_tuner.cli.list_processes", return_value=rows):
        result = invoke(["list"])
    assert result.exit_code == 0
    assert "<access denied>" in result.output
    assert "-" in result.output


def test_inspect_command():
    info = {
        "pid": 5,
        "name": "x",
        "status": "running",
        "cpu_percent": 1.0,
        "memory_rss": 50,
        "num_threads": 2,
        "cpu_affinity": [0, 1],
        "priority": "normal",
        "priority_value": 32,
        "create_time": 1.0,
        "exe": "x",
        "cmdline": ["x"],
    }
    with patch("win_process_tuner.cli.inspect_process", return_value=info):
        result = invoke(["inspect", "5"])
    assert result.exit_code == 0
    assert "pid: 5" in result.output


def test_inspect_json():
    info = {"pid": 5, "name": "x", "cpu_affinity": [0, 1]}
    with patch("win_process_tuner.cli.inspect_process", return_value=info):
        result = invoke(["inspect", "5", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["pid"] == 5


def test_set_priority_dry_run():
    with patch(
        "win_process_tuner.cli.set_priority",
        return_value={
            "pid": 5,
            "level": "high",
            "current": 8,
            "new": 128,
            "changed": True,
            "dry_run": True,
        },
    ):
        result = invoke(["set-priority", "5", "--level", "high", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_set_priority_safety_refusal():
    with patch(
        "win_process_tuner.cli.set_priority",
        side_effect=SafetyError("Refusing to tune PID 4: protected"),
    ):
        result = invoke(["set-priority", "4", "--level", "high", "--yes"])
    assert result.exit_code == 1
    assert "Refusing" in result.output


def test_set_priority_access_denied_hint():
    with patch(
        "win_process_tuner.cli.set_priority",
        side_effect=psutil.AccessDenied(pid=5),
    ):
        with patch("win_process_tuner.cli.is_admin", return_value=False):
            result = invoke(["set-priority", "5", "--level", "high", "--yes"])
    assert result.exit_code == 1
    assert "Administrator" in result.output


def test_set_affinity_dry_run():
    with patch(
        "win_process_tuner.cli.set_affinity",
        return_value={
            "pid": 5,
            "current": [0, 1],
            "new": [0, 2],
            "changed": True,
            "dry_run": True,
        },
    ):
        result = invoke(["set-affinity", "5", "--cpus", "0,2", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_set_affinity_bad_cpus():
    result = invoke(["set-affinity", "5", "--cpus", "0,x", "--yes"])
    assert result.exit_code == 1
    assert "Invalid CPU" in result.output


def test_timer_dry_run():
    with patch(
        "win_process_tuner.cli.apply_timer_resolution",
        return_value={
            "ms": 5,
            "dry_run": True,
            "would_call": "timeBeginPeriod(5); hold 0s; timeEndPeriod(5)",
        },
    ):
        result = invoke(["timer-resolution", "--ms", "5", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output
    assert "timer behavior" in result.output


def test_timer_success_reports_both_calls():
    with patch(
        "win_process_tuner.cli.apply_timer_resolution",
        return_value={
            "ms": 1,
            "dry_run": False,
            "begin_code": 0,
            "ended": True,
            "end_code": 0,
            "end_success": True,
            "success": True,
        },
    ):
        result = invoke(["timer-resolution", "--ms", "1", "--yes"])
    assert result.exit_code == 0
    assert "timeBeginPeriod(1): OK" in result.output
    assert "timeEndPeriod(1): OK" in result.output


def test_timer_failure_exits_nonzero():
    with patch(
        "win_process_tuner.cli.apply_timer_resolution",
        return_value={
            "ms": 1,
            "dry_run": False,
            "begin_code": 97,
            "ended": False,
            "success": False,
        },
    ):
        result = invoke(["timer-resolution", "--ms", "1", "--yes"])
    assert result.exit_code == 1


def test_profile_dry_run():
    with patch("win_process_tuner.cli.physical_core_cpus", return_value=[0, 2, 4, 6]):
        with patch(
            "win_process_tuner.cli.apply_gaming_profile",
            return_value={
                "pid": 5,
                "profile": "gaming",
                "priority": "high",
                "affinity": [0, 2, 4, 6],
                "dry_run": True,
            },
        ):
            result = invoke(["profile", "apply", "gaming", "--pid", "5", "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_capture_prints_json():
    state = {"version": 1, "pid": 5, "priority_value": 32, "affinity": [0, 1]}
    with patch("win_process_tuner.cli.capture_state", return_value=state):
        result = invoke(["capture", "5"])
    assert result.exit_code == 0
    assert json.loads(result.output)["pid"] == 5


def test_capture_writes_file(tmp_path):
    state = {"version": 1, "pid": 5, "priority_value": 32, "affinity": [0, 1]}
    path = str(tmp_path / "snap.json")
    with patch("win_process_tuner.cli.capture_state", return_value=state):
        with patch("win_process_tuner.cli.write_snapshot") as writer:
            result = invoke(["capture", "5", "--output", path])
    assert result.exit_code == 0
    writer.assert_called_once_with(state, path)


def test_restore_dry_run():
    state = {"version": 1, "pid": 5, "priority_value": 32, "affinity": [0, 1]}
    restored = {
        "pid": 5,
        "priority": {"current": 128, "new": 32},
        "affinity": {"current": [0], "new": [0, 1]},
        "dry_run": True,
        "applied": False,
    }
    with patch("win_process_tuner.cli.load_snapshot", return_value=state):
        with patch("win_process_tuner.cli.restore_state", return_value=restored):
            result = invoke(["restore", "5", "--input", __file__, "--dry-run"])
    assert result.exit_code == 0
    assert "dry-run" in result.output


def test_restore_invalid_snapshot_exits():
    with patch("win_process_tuner.cli.load_snapshot", side_effect=ValueError("bad snapshot")):
        result = invoke(["restore", "5", "--input", __file__, "--yes"])
    assert result.exit_code == 1
    assert "bad snapshot" in result.output


def test_doctor_command():
    result = invoke(["doctor"])
    assert result.exit_code == 0

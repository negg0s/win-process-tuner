import contextlib
import json
from unittest.mock import MagicMock, patch

import psutil
import pytest

import win_process_tuner.state as state_mod


def _make_proc(pid=42, name="game.exe"):
    proc = MagicMock()
    proc.pid = pid
    proc.name.return_value = name
    proc.nice.return_value = psutil.HIGH_PRIORITY_CLASS
    proc.cpu_affinity.return_value = [0, 2, 4]
    proc.oneshot.return_value = contextlib.nullcontext()
    return proc


def _snapshot(pid=42):
    return {
        "version": 1,
        "pid": pid,
        "name": "game.exe",
        "priority_value": psutil.HIGH_PRIORITY_CLASS,
        "affinity": [0, 2],
        "captured_at": "2026-01-01T00:00:00Z",
    }


def test_capture_state_reads_priority_and_affinity():
    with patch.object(state_mod, "check_target", return_value=_make_proc()):
        data = state_mod.capture_state(42)
    assert data["pid"] == 42
    assert data["priority_value"] == psutil.HIGH_PRIORITY_CLASS
    assert data["affinity"] == [0, 2, 4]
    assert data["version"] == 1


def test_write_and_load_snapshot(tmp_path):
    path = tmp_path / "snap.json"
    state_mod.write_snapshot(_snapshot(), str(path))
    assert not (tmp_path / "snap.json.tmp").exists()
    loaded = state_mod.load_snapshot(str(path))
    assert loaded["affinity"] == [0, 2]


def test_validate_snapshot_rejects_wrong_version():
    data = _snapshot()
    data["version"] = 99
    with pytest.raises(ValueError):
        state_mod.validate_snapshot(data)


def test_validate_snapshot_rejects_bad_priority():
    data = _snapshot()
    data["priority_value"] = 7
    with pytest.raises(ValueError):
        state_mod.validate_snapshot(data)


def test_validate_snapshot_rejects_empty_affinity():
    data = _snapshot()
    data["affinity"] = []
    with pytest.raises(ValueError):
        state_mod.validate_snapshot(data)


def test_restore_state_dry_run_does_not_apply():
    proc = _make_proc()
    with patch.object(state_mod, "check_target", return_value=proc):
        with patch.object(
            state_mod,
            "set_priority",
            return_value={"pid": 42, "current": 32, "new": 128, "dry_run": True},
        ) as mock_priority:
            with patch.object(
                state_mod,
                "set_affinity",
                return_value={"pid": 42, "current": [0, 1], "new": [0, 2], "dry_run": True},
            ) as mock_affinity:
                res = state_mod.restore_state(42, _snapshot(), dry_run=True)
    assert res["applied"] is False
    mock_priority.assert_called_once_with(42, "high", dry_run=True)
    mock_affinity.assert_called_once_with(42, [0, 2], dry_run=True)


def test_restore_state_refuses_pid_mismatch():
    with patch.object(state_mod, "check_target", return_value=_make_proc()):
        with pytest.raises(ValueError):
            state_mod.restore_state(42, _snapshot(pid=43), dry_run=True)


def test_restore_state_refuses_protected_pid():
    with pytest.raises(Exception):
        state_mod.restore_state(4, _snapshot(pid=4), dry_run=True)


def test_load_snapshot_rejects_missing_file(tmp_path):
    with pytest.raises(OSError):
        state_mod.load_snapshot(str(tmp_path / "missing.json"))


def test_capture_game_state_records_process_identity_and_priority():
    proc = _make_proc()
    proc.create_time.return_value = 1234.5
    with patch.object(state_mod, "check_target", return_value=proc):
        data = state_mod.capture_game_state(42)
    assert data == {
        "version": 1,
        "pid": 42,
        "name": "game.exe",
        "create_time": 1234.5,
        "priority_value": psutil.HIGH_PRIORITY_CLASS,
    }


def test_restore_game_state_refuses_reused_pid():
    proc = _make_proc()
    proc.create_time.return_value = 9999.0
    saved = {
        "version": 1,
        "pid": 42,
        "name": "game.exe",
        "create_time": 1234.5,
        "priority_value": psutil.NORMAL_PRIORITY_CLASS,
    }
    with patch.object(state_mod, "check_target", return_value=proc):
        with pytest.raises(ValueError, match="different process"):
            state_mod.restore_game_state(saved)


def test_restore_game_state_restores_only_saved_priority():
    proc = _make_proc()
    proc.create_time.return_value = 1234.5
    saved = {
        "version": 1,
        "pid": 42,
        "name": "game.exe",
        "create_time": 1234.5,
        "priority_value": psutil.NORMAL_PRIORITY_CLASS,
    }
    with patch.object(state_mod, "check_target", return_value=proc) as target:
        result = state_mod.restore_game_state(saved)
    target.assert_called_once_with(42)
    assert proc.nice.call_args_list[-1].args == (psutil.NORMAL_PRIORITY_CLASS,)
    assert result["priority"]["new"] == 32


def test_apply_game_priority_uses_captured_process_identity():
    proc = _make_proc()
    proc.create_time.return_value = 1234.5
    saved = {
        "version": 1,
        "pid": 42,
        "name": "game.exe",
        "create_time": 1234.5,
        "priority_value": psutil.NORMAL_PRIORITY_CLASS,
    }
    with patch.object(state_mod, "check_target", return_value=proc):
        result = state_mod.apply_game_priority(saved)
    assert proc.nice.call_args_list[-1].args == (psutil.ABOVE_NORMAL_PRIORITY_CLASS,)
    assert result["applied"] is True


def test_apply_game_priority_refuses_pid_reuse():
    proc = _make_proc()
    proc.create_time.return_value = 9999.0
    saved = {
        "version": 1,
        "pid": 42,
        "name": "game.exe",
        "create_time": 1234.5,
        "priority_value": psutil.NORMAL_PRIORITY_CLASS,
    }
    with patch.object(state_mod, "check_target", return_value=proc):
        with pytest.raises(ValueError, match="different process"):
            state_mod.apply_game_priority(saved)
    proc.nice.assert_not_called()

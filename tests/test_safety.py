import contextlib
from unittest.mock import MagicMock, patch

import pytest

import win_process_tuner.safety as safety


def test_check_target_refuses_pid_zero():
    with pytest.raises(safety.SafetyError):
        safety.check_target(0)


def test_check_target_refuses_pid_four():
    with pytest.raises(safety.SafetyError):
        safety.check_target(4)


def test_check_target_refuses_critical_name():
    proc = MagicMock()
    proc.name.return_value = "csrss.exe"
    with pytest.raises(safety.SafetyError) as excinfo:
        safety.check_target(123, proc)
    assert "critical" in str(excinfo.value)


def test_check_target_allows_normal_process():
    proc = MagicMock()
    proc.name.return_value = "game.exe"
    proc.pid = 123
    assert safety.check_target(123, proc) is proc


def test_check_target_refuses_negative_pid():
    with pytest.raises(safety.SafetyError):
        safety.check_target(-1)


def test_is_admin_uses_windows_api():
    with patch.object(safety.ctypes, "windll") as windll:
        windll.shell32.IsUserAnAdmin.return_value = 1
        assert safety.is_admin() is True


def test_is_admin_handles_failure():
    with patch.object(safety.ctypes, "windll") as windll:
        windll.shell32.IsUserAnAdmin.side_effect = OSError("no shell32")
        assert safety.is_admin() is False

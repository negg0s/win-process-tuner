import contextlib
from unittest.mock import MagicMock, patch

import psutil
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


def test_check_target_refuses_system_account_process():
    proc = MagicMock()
    proc.name.return_value = "svchost.exe"
    proc.username.return_value = "NT AUTHORITY\\SYSTEM"
    with pytest.raises(safety.SafetyError, match="system-owned"):
        safety.check_target(123, proc)


def test_check_target_refuses_service_account_process():
    proc = MagicMock()
    proc.name.return_value = "gamingservices.exe"
    proc.username.return_value = "NT SERVICE\\GamingServices"
    with pytest.raises(safety.SafetyError, match="system-owned"):
        safety.check_target(123, proc)


def test_check_target_refuses_process_from_windows_directory():
    proc = MagicMock()
    proc.name.return_value = "example.exe"
    proc.username.return_value = "user"
    proc.exe.return_value = "C:\\Windows\\System32\\example.exe"
    with patch.dict("os.environ", {"WINDIR": "C:\\Windows"}):
        with pytest.raises(safety.SafetyError, match="Windows directory"):
            safety.check_target(123, proc)


def test_check_target_refuses_process_when_owner_cannot_be_checked():
    proc = MagicMock()
    proc.name.return_value = "unknown.exe"
    proc.username.side_effect = psutil.AccessDenied(123)
    with pytest.raises(safety.SafetyError, match="cannot verify process owner"):
        safety.check_target(123, proc)


def test_check_target_refuses_process_when_executable_cannot_be_checked():
    proc = MagicMock()
    proc.name.return_value = "unknown.exe"
    proc.username.return_value = "user"
    proc.exe.side_effect = psutil.AccessDenied(123)
    with pytest.raises(safety.SafetyError, match="cannot verify executable location"):
        safety.check_target(123, proc)


def test_check_target_allows_normal_process():
    proc = MagicMock()
    proc.name.return_value = "game.exe"
    proc.username.return_value = "current-user"
    proc.exe.return_value = "C:\\Games\\game.exe"
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

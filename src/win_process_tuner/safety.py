"""Guardrails for process mutations."""

import ctypes
import ntpath
import os

import psutil

PROTECTED_PIDS = frozenset({0, 4})

CRITICAL_NAMES = frozenset(
    {
        "system",
        "system idle process",
        "registry",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "winlogon.exe",
        "services.exe",
        "lsass.exe",
    }
)


class SafetyError(RuntimeError):
    """Raised when an operation is refused for safety reasons."""


def is_admin():
    """Return True when the current process has administrator rights."""
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevation_hint():
    return "Run the terminal as Administrator and try again."


def check_target(pid, process=None):
    """Validate a target PID and return a psutil.Process.

    Refuses PID 0, PID 4, and known critical system processes.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        raise SafetyError(f"Invalid PID: {pid!r}")
    if pid <= 0:
        raise SafetyError(
            f"Refusing to tune PID {pid}: only positive process IDs are allowed."
        )
    if pid in PROTECTED_PIDS:
        raise SafetyError(
            f"Refusing to tune PID {pid}: it is a protected system process."
        )
    proc = process or psutil.Process(pid)
    try:
        name = proc.name()
    except psutil.AccessDenied:
        name = None
    except psutil.NoSuchProcess:
        raise
    if name and name.lower() in CRITICAL_NAMES:
        raise SafetyError(
            f"Refusing to tune PID {pid} ({name}): it is a critical system process."
        )
    try:
        username = proc.username()
    except psutil.AccessDenied:
        raise SafetyError(f"Refusing to tune PID {pid}: cannot verify process owner.")
    if not isinstance(username, str):
        raise SafetyError(f"Refusing to tune PID {pid}: cannot verify process owner.")
    folded_username = username.casefold()
    system_account = folded_username.startswith(("nt authority\\", "nt service\\"))
    system_account = system_account or folded_username in {
        "system",
        "local service",
        "network service",
    }
    if system_account:
        raise SafetyError(
            f"Refusing to tune PID {pid} ({name or 'unknown'}): it is system-owned."
        )
    windows_dir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    try:
        executable = proc.exe()
    except psutil.AccessDenied:
        raise SafetyError(f"Refusing to tune PID {pid}: cannot verify executable location.")
    if not isinstance(executable, str):
        raise SafetyError(f"Refusing to tune PID {pid}: cannot verify executable location.")
    if windows_dir:
        try:
            if ntpath.commonpath(
                [ntpath.normcase(executable), ntpath.normcase(windows_dir)]
            ) == ntpath.normcase(windows_dir):
                raise SafetyError(
                    f"Refusing to tune PID {pid} ({name or 'unknown'}): it runs from the Windows directory."
                )
        except ValueError:
            pass
    return proc

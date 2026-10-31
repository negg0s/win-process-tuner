"""Guardrails for process mutations."""

import ctypes
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
    return proc

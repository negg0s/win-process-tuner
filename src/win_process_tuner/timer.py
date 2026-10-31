"""Windows timer resolution helpers using ctypes/winmm."""

import ctypes

TIMERR_NOERROR = 0


def _winmm():
    return ctypes.WinDLL("winmm")


def begin_period(ms):
    """Call timeBeginPeriod. Returns (success_bool, code)."""
    if not (1 <= ms <= 16):
        raise ValueError("ms must be between 1 and 16")
    dll = _winmm()
    code = dll.timeBeginPeriod(int(ms))
    return code == TIMERR_NOERROR, int(code)


def end_period(ms):
    """Call timeEndPeriod. Returns (success_bool, code)."""
    if not (1 <= ms <= 16):
        raise ValueError("ms must be between 1 and 16")
    dll = _winmm()
    code = dll.timeEndPeriod(int(ms))
    return code == TIMERR_NOERROR, int(code)


def apply_timer_resolution(ms, dry_run=False):
    """Apply (begin) timer resolution. Returns result dict."""
    if not (1 <= ms <= 16):
        raise ValueError("ms must be between 1 and 16")
    if dry_run:
        return {
            "ms": ms,
            "action": "timeBeginPeriod",
            "dry_run": True,
            "would_call": f"timeBeginPeriod({ms})",
        }
    success, code = begin_period(ms)
    return {
        "ms": ms,
        "action": "timeBeginPeriod",
        "success": success,
        "code": code,
        "dry_run": False,
    }

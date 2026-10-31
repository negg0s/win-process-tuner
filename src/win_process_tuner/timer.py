"""Windows timer resolution helpers using ctypes/winmm."""

import ctypes
import time

TIMERR_NOERROR = 0


def _winmm():
    dll = ctypes.WinDLL("winmm")
    dll.timeBeginPeriod.argtypes = [ctypes.c_uint]
    dll.timeBeginPeriod.restype = ctypes.c_uint
    dll.timeEndPeriod.argtypes = [ctypes.c_uint]
    dll.timeEndPeriod.restype = ctypes.c_uint
    return dll


def _validate_ms(ms):
    if not isinstance(ms, int) or not 1 <= ms <= 16:
        raise ValueError("ms must be an integer between 1 and 16")


def begin_period(ms):
    """Call timeBeginPeriod. Returns (success_bool, code)."""
    _validate_ms(ms)
    code = _winmm().timeBeginPeriod(ms)
    return code == TIMERR_NOERROR, int(code)


def end_period(ms):
    """Call timeEndPeriod. Returns (success_bool, code)."""
    _validate_ms(ms)
    code = _winmm().timeEndPeriod(ms)
    return code == TIMERR_NOERROR, int(code)


def apply_timer_resolution(ms, dry_run=False, hold_seconds=0):
    """Begin a timer period, optionally hold it, then end it.

    timeEndPeriod is only called when timeBeginPeriod succeeded, which is the
    pairing required by the Windows API.
    """
    _validate_ms(ms)
    if hold_seconds < 0:
        raise ValueError("hold_seconds must be zero or greater")
    if dry_run:
        return {
            "ms": ms,
            "action": "timeBeginPeriod/timeEndPeriod",
            "dry_run": True,
            "hold_seconds": hold_seconds,
            "would_call": f"timeBeginPeriod({ms}); hold {hold_seconds}s; timeEndPeriod({ms})",
        }

    begin_ok, begin_code = begin_period(ms)
    result = {
        "ms": ms,
        "action": "timeBeginPeriod/timeEndPeriod",
        "dry_run": False,
        "hold_seconds": hold_seconds,
        "begin_code": begin_code,
        "success": begin_ok,
        "ended": False,
    }
    if not begin_ok:
        return result

    try:
        if hold_seconds > 0:
            time.sleep(hold_seconds)
    finally:
        end_ok, end_code = end_period(ms)
        result["ended"] = True
        result["end_code"] = end_code
        result["end_success"] = end_ok
        result["success"] = end_ok
    return result

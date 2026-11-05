"""Environment diagnostics."""

import ctypes
import platform
import sys

import psutil


def run_doctor():
    checks = []
    # Python
    checks.append(("python", True, f"{sys.version.split()[0]}"))
    # psutil
    try:
        checks.append(("psutil", True, psutil.__version__))
    except Exception as exc:
        checks.append(("psutil", False, str(exc)))
    # winmm
    try:
        ctypes.WinDLL("winmm")
        checks.append(("winmm", True, "loadable"))
    except Exception as exc:
        checks.append(("winmm", False, str(exc)))
    # admin
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin = False
    checks.append(("administrator", is_admin, "recommended for mutating processes"))
    # cpu
    try:
        checks.append(
            (
                "cpu",
                True,
                f"logical={psutil.cpu_count(logical=True)} physical={psutil.cpu_count(logical=False)}",
            )
        )
    except Exception as exc:
        checks.append(("cpu", False, str(exc)))
    # platform
    checks.append(("platform", platform.system() == "Windows", platform.platform()))
    # timer resolution
    from .timer import query_timer_resolution
    t_info = query_timer_resolution()
    detail = f"current={t_info['current_ms']}ms (min={t_info['min_ms']}ms, max={t_info['max_ms']}ms)" if t_info["supported"] else "unavailable"
    checks.append(("timer_resolution", t_info["supported"], detail))
    return checks

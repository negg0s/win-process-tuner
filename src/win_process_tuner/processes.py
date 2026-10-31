"""Process inspection and tuning helpers built on psutil."""

import psutil

from .safety import check_target

PRIORITY_LEVELS = {
    "high": psutil.HIGH_PRIORITY_CLASS,
    "above-normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    "normal": psutil.NORMAL_PRIORITY_CLASS,
    "below-normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
    "idle": psutil.IDLE_PRIORITY_CLASS,
}

PRIORITY_NAMES = {v: k for k, v in PRIORITY_LEVELS.items()}


def _read_row(proc):
    try:
        with proc.oneshot():
            return {
                "pid": proc.pid,
                "name": proc.name(),
                "cpu": proc.cpu_percent(interval=None),
                "memory": proc.memory_info().rss,
                "status": proc.status(),
                "denied": False,
            }
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return None
    except psutil.AccessDenied:
        return {
            "pid": proc.pid,
            "name": "<access denied>",
            "cpu": None,
            "memory": None,
            "status": "denied",
            "denied": True,
        }
    except Exception:
        return None


def list_processes(top=10, sort="cpu"):
    """Return process dicts sorted by cpu or memory.

    Processes that deny access are kept with ``denied`` set so they can be
    reported instead of breaking the whole listing.
    """
    if sort not in ("cpu", "memory"):
        raise ValueError(f"Unknown sort key: {sort}")
    rows = []
    for proc in psutil.process_iter(["pid"]):
        row = _read_row(proc)
        if row is not None:
            rows.append(row)

    def sort_key(row):
        value = row.get(sort)
        if value is None:
            value = -1
        return (-value, row["pid"])

    rows.sort(key=sort_key)
    if top is not None and top > 0:
        rows = rows[:top]
    return rows


def inspect_process(pid):
    """Return detailed info dict for a process."""
    proc = psutil.Process(pid)
    with proc.oneshot():
        priority = proc.nice()
        info = {
            "pid": proc.pid,
            "name": proc.name(),
            "status": proc.status(),
            "cpu_percent": proc.cpu_percent(interval=None),
            "memory_rss": proc.memory_info().rss,
            "num_threads": proc.num_threads(),
            "cpu_affinity": proc.cpu_affinity(),
            "priority": PRIORITY_NAMES.get(priority),
            "priority_value": priority,
            "create_time": proc.create_time(),
            "exe": _safe(proc.exe),
            "cmdline": _safe(proc.cmdline),
        }
    return info


def _safe(callable_):
    try:
        return callable_()
    except Exception as exc:
        return f"<error: {exc}>"


def set_priority(pid, level, dry_run=False):
    """Set process priority class. Returns result dict."""
    if level not in PRIORITY_LEVELS:
        raise ValueError(f"Unknown priority level: {level}")
    proc = check_target(pid)
    new_value = PRIORITY_LEVELS[level]
    current = proc.nice()
    result = {
        "pid": proc.pid,
        "level": level,
        "current": current,
        "new": new_value,
        "changed": current != new_value,
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    proc.nice(new_value)
    result["applied"] = True
    return result


def set_affinity(pid, cpus, dry_run=False):
    """Set process CPU affinity. cpus is a list of ints."""
    proc = check_target(pid)
    cpus = parse_cpu_list(cpus)
    logical = psutil.cpu_count(logical=True) or 1
    invalid = [c for c in cpus if c < 0 or c >= logical]
    if invalid:
        raise ValueError(
            f"CPU index out of range: {invalid}. This machine has {logical} logical CPUs."
        )
    try:
        current = proc.cpu_affinity()
    except psutil.AccessDenied:
        current = []
    result = {
        "pid": proc.pid,
        "current": current,
        "new": cpus,
        "changed": sorted(current) != sorted(cpus),
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    proc.cpu_affinity(cpus)
    result["applied"] = True
    return result


def parse_cpu_list(value):
    if isinstance(value, str):
        parts = [x.strip() for x in value.split(",") if x.strip() != ""]
    else:
        parts = list(value)
    out = []
    for part in parts:
        try:
            cpu = int(part)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid CPU index: {part!r}")
        if cpu < 0:
            raise ValueError(f"Invalid CPU index: {cpu}")
        if cpu not in out:
            out.append(cpu)
    if not out:
        raise ValueError("No CPUs provided")
    return out


parse_cpus = parse_cpu_list

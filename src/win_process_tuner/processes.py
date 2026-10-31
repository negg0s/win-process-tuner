"""Process inspection and tuning helpers built on psutil."""

import psutil

PRIORITY_LEVELS = {
    "high": psutil.HIGH_PRIORITY_CLASS,
    "above-normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
    "normal": psutil.NORMAL_PRIORITY_CLASS,
    "below-normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
    "idle": psutil.IDLE_PRIORITY_CLASS,
}

PRIORITY_NAMES = {v: k for k, v in PRIORITY_LEVELS.items()}


def list_processes(top=10, sort="cpu"):
    """Return a list of process dicts sorted by cpu or memory."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "status"]):
        try:
            with p.oneshot():
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_info().rss
                name = p.name()
                status = p.status()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
        procs.append(
            {
                "pid": p.pid,
                "name": name,
                "cpu": cpu,
                "memory": mem,
                "status": status,
            }
        )
    key = "cpu" if sort == "cpu" else "memory"
    procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)
    if top is not None and top > 0:
        procs = procs[:top]
    return procs


def inspect_process(pid):
    """Return detailed info dict for a process."""
    p = psutil.Process(pid)
    with p.oneshot():
        info = {
            "pid": p.pid,
            "name": p.name(),
            "status": p.status(),
            "cpu_percent": p.cpu_percent(interval=None),
            "memory_rss": p.memory_info().rss,
            "num_threads": p.num_threads(),
            "cpu_affinity": p.cpu_affinity(),
            "nice": p.nice(),
            "create_time": p.create_time(),
            "exe": _safe(p.exe),
            "cmdline": _safe(p.cmdline),
        }
    return info


def _safe(callable_):
    try:
        return callable_()
    except Exception as exc:  # pragma: no cover - defensive
        return f"<error: {exc}>"


def set_priority(pid, level, dry_run=False):
    """Set process priority class. Returns result dict."""
    if level not in PRIORITY_LEVELS:
        raise ValueError(f"Unknown priority level: {level}")
    p = psutil.Process(pid)
    new_value = PRIORITY_LEVELS[level]
    current = p.nice()
    result = {
        "pid": pid,
        "level": level,
        "current": current,
        "new": new_value,
        "changed": current != new_value,
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    p.nice(new_value)
    result["applied"] = True
    return result


def set_affinity(pid, cpus, dry_run=False):
    """Set process CPU affinity. cpus is a list of ints."""
    p = psutil.Process(pid)
    cpus = [int(c) for c in cpus]
    current = p.cpu_affinity()
    result = {
        "pid": pid,
        "current": current,
        "new": cpus,
        "changed": sorted(current) != sorted(cpus),
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    p.cpu_affinity(cpus)
    result["applied"] = True
    return result


def parse_cpus(value):
    """Parse '0,2,4' into list of ints."""
    parts = [x.strip() for x in str(value).split(",") if x.strip() != ""]
    out = []
    for part in parts:
        out.append(int(part))
    if not out:
        raise ValueError("No CPUs provided")
    return out

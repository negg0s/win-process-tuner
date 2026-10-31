"""Process profiles (e.g. gaming)."""

import psutil

from .processes import PRIORITY_LEVELS, set_affinity, set_priority


def physical_cores_heuristic():
    """Return list of logical CPU indices approximating physical cores."""
    logical = psutil.cpu_count(logical=True) or 1
    physical = psutil.cpu_count(logical=False) or 1
    if logical <= physical or physical == 1:
        return list(range(logical))
    # Assume sibling logical processors are adjacent pairs.
    cpus = list(range(0, logical, 2))[:physical]
    if not cpus:
        cpus = list(range(physical))
    return cpus


def apply_gaming_profile(pid, dry_run=False, yes=False):
    """Apply gaming profile: high priority + affinity to physical cores."""
    cpus = physical_cores_heuristic()
    result = {
        "pid": pid,
        "profile": "gaming",
        "priority": "high",
        "affinity": cpus,
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    set_priority(pid, "high", dry_run=False)
    set_affinity(pid, cpus, dry_run=False)
    result["applied"] = True
    return result

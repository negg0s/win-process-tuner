"""Capture and restore process priority and affinity."""

import json
import os
import time

import psutil

from .processes import PRIORITY_LEVELS, set_affinity, set_priority
from .safety import check_target

SNAPSHOT_VERSION = 1


def capture_state(pid):
    """Read priority and affinity into a plain dict."""
    proc = check_target(pid)
    with proc.oneshot():
        state = {
            "version": SNAPSHOT_VERSION,
            "pid": proc.pid,
            "name": proc.name(),
            "priority_value": proc.nice(),
            "affinity": proc.cpu_affinity(),
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    return state


def write_snapshot(state, path):
    """Write a snapshot atomically."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, path)


def load_snapshot(path):
    """Load and validate a snapshot file."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return validate_snapshot(data)


def validate_snapshot(data):
    if not isinstance(data, dict):
        raise ValueError("Snapshot must be a JSON object")
    if data.get("version") != SNAPSHOT_VERSION:
        raise ValueError(f"Unsupported snapshot version: {data.get('version')!r}")
    pid = data.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError("Snapshot has an invalid pid")
    priority = data.get("priority_value")
    if not isinstance(priority, int) or priority not in PRIORITY_LEVELS.values():
        raise ValueError("Snapshot has an invalid priority_value")
    affinity = data.get("affinity")
    if not isinstance(affinity, list) or not affinity:
        raise ValueError("Snapshot has an invalid affinity list")
    if any(not isinstance(cpu, int) or cpu < 0 for cpu in affinity):
        raise ValueError("Snapshot affinity must contain non-negative integers")
    return data


def restore_state(pid, state, dry_run=False):
    """Restore priority and affinity from a validated snapshot."""
    check_target(pid)
    if state["pid"] != pid:
        raise ValueError(
            f"Snapshot is for PID {state['pid']}, not PID {pid}. "
            "Refusing to restore across processes."
        )
    level = next(
        name for name, value in PRIORITY_LEVELS.items() if value == state["priority_value"]
    )
    priority_result = set_priority(pid, level, dry_run=dry_run)
    affinity_result = set_affinity(pid, state["affinity"], dry_run=dry_run)
    return {
        "pid": pid,
        "priority": priority_result,
        "affinity": affinity_result,
        "dry_run": dry_run,
        "applied": not dry_run,
    }


def capture_game_state(pid):
    """Capture only the priority and identity needed by the beginner game flow."""
    proc = check_target(pid)
    with proc.oneshot():
        return {
            "version": SNAPSHOT_VERSION,
            "pid": proc.pid,
            "name": proc.name(),
            "create_time": proc.create_time(),
            "priority_value": proc.nice(),
        }


def validate_game_snapshot(data):
    if not isinstance(data, dict):
        raise ValueError("Game undo file must be a JSON object")
    if data.get("version") != SNAPSHOT_VERSION:
        raise ValueError("Unsupported game undo file version")
    if not isinstance(data.get("pid"), int) or data["pid"] <= 0:
        raise ValueError("Game undo file has an invalid pid")
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise ValueError("Game undo file has an invalid process name")
    if not isinstance(data.get("create_time"), (int, float)):
        raise ValueError("Game undo file has an invalid process start time")
    if data.get("priority_value") not in PRIORITY_LEVELS.values():
        raise ValueError("Game undo file has an invalid priority")
    return data


def load_game_snapshot(path):
    with open(path, "r", encoding="utf-8") as handle:
        return validate_game_snapshot(json.load(handle))


def write_game_snapshot(state, path):
    validate_game_snapshot(state)
    write_snapshot(state, path)


def apply_game_priority(state):
    """Raise priority only if the target still matches the captured process."""
    validate_game_snapshot(state)
    proc = check_target(state["pid"])
    if (
        proc.name().lower() != state["name"].lower()
        or proc.create_time() != state["create_time"]
    ):
        raise ValueError("PID now belongs to a different process. Refusing to apply.")
    current = proc.nice()
    new = PRIORITY_LEVELS["above-normal"]
    proc.nice(new)
    return {
        "pid": state["pid"],
        "current": current,
        "new": new,
        "applied": True,
    }


def restore_game_state(state):
    """Restore priority only if the PID still identifies the captured process."""
    validate_game_snapshot(state)
    proc = check_target(state["pid"])
    if (
        proc.name().lower() != state["name"].lower()
        or proc.create_time() != state["create_time"]
    ):
        raise ValueError("PID now belongs to a different process. Refusing to restore.")
    current = proc.nice()
    new = state["priority_value"]
    proc.nice(new)
    priority_result = {
        "pid": state["pid"],
        "current": current,
        "new": new,
        "dry_run": False,
        "applied": True,
    }
    return {"pid": state["pid"], "priority": priority_result, "applied": True}


def game_snapshot_path():
    """Return the per-user location for the one-step game undo file."""
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".win-process-tuner")
    if os.environ.get("LOCALAPPDATA"):
        base = os.path.join(base, "win-process-tuner")
    return os.path.join(base, "game-undo.json")


def remove_game_snapshot(path):
    os.remove(path)


def snapshot_path(pid, directory=None):
    base = directory or os.getcwd()
    return os.path.join(base, f"wpt-{pid}.json")


def process_exists(pid):
    try:
        return psutil.pid_exists(pid)
    except Exception:
        return False

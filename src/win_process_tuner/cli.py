"""Command-line interface for win-process-tuner."""

import json
import os
import sys

import click
import psutil

from . import __version__
from .doctor import run_doctor
from .processes import (
    PRIORITY_LEVELS,
    inspect_process,
    list_processes,
    parse_cpu_list,
    set_affinity,
    set_priority,
)
from .profile import apply_gaming_profile, physical_core_cpus
from .safety import CRITICAL_NAMES, PROTECTED_PIDS, SafetyError, check_target, elevation_hint, is_admin
from .state import (
    apply_game_priority,
    capture_game_state,
    capture_state,
    game_snapshot_path,
    load_game_snapshot,
    load_snapshot,
    remove_game_snapshot,
    restore_game_state,
    restore_state,
    write_game_snapshot,
    write_snapshot,
)
from .timer import apply_timer_resolution


def _confirm(yes, dry_run, message):
    if dry_run or yes:
        return
    if not click.confirm(message, default=False):
        raise click.Abort()


def _fail(exc):
    if isinstance(exc, SafetyError):
        message = str(exc)
    elif isinstance(exc, psutil.AccessDenied):
        message = f"Access denied: {exc}"
        if not is_admin():
            message = f"{message}\n{elevation_hint()}"
    elif isinstance(exc, psutil.NoSuchProcess):
        message = f"No such process: {exc}"
    else:
        message = str(exc)
    click.echo(f"Error: {message}", err=True)
    sys.exit(1)


def _fmt_bytes(n):
    if n is None:
        return "-"
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _fmt_cpu(value):
    return "-" if value is None else f"{value:.1f}"


def _dump_json(value):
    click.echo(json.dumps(value, indent=2, sort_keys=False))


@click.group()
@click.version_option(__version__)
def cli():
    """Windows process tuner CLI."""


@cli.command("list")
@click.option("--top", default=10, type=int, show_default=True, help="Number of processes to show.")
@click.option(
    "--sort",
    type=click.Choice(["cpu", "memory"]),
    default="cpu",
    show_default=True,
    help="Sort key.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of a table.")
def list_cmd(top, sort, as_json):
    """List running processes."""
    try:
        rows = list_processes(top=top, sort=sort)
    except Exception as exc:
        _fail(exc)
    if as_json:
        _dump_json(rows)
        return
    if not rows:
        click.echo("No processes found.")
        return
    click.echo(f"{'PID':>8}  {'CPU%':>6}  {'MEMORY':>10}  {'STATUS':<12}  NAME")
    for row in rows:
        name = str(row["name"])
        if len(name) > 48:
            name = name[:47] + "~"
        click.echo(
            f"{row['pid']:>8}  {_fmt_cpu(row['cpu']):>6}  "
            f"{_fmt_bytes(row['memory']):>10}  {str(row['status']):<12}  {name}"
        )


@cli.command("inspect")
@click.argument("pid", type=int)
@click.option("--json", "as_json", is_flag=True, help="Print JSON instead of key/value lines.")
def inspect_cmd(pid, as_json):
    """Inspect a process by PID."""
    try:
        info = inspect_process(pid)
    except Exception as exc:
        _fail(exc)
    if as_json:
        _dump_json(info)
        return
    for key, value in info.items():
        click.echo(f"{key}: {value}")


@cli.command("set-priority")
@click.argument("pid", type=int)
@click.option(
    "--level",
    required=True,
    type=click.Choice(list(PRIORITY_LEVELS.keys())),
    help="Priority level.",
)
@click.option("--dry-run", is_flag=True, help="Print intended change without applying.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def set_priority_cmd(pid, level, dry_run, yes):
    """Set process priority class."""
    _confirm(yes, dry_run, f"Set priority of PID {pid} to {level}?")
    try:
        res = set_priority(pid, level, dry_run=dry_run)
    except Exception as exc:
        _fail(exc)
    if dry_run:
        click.echo(f"[dry-run] PID {res['pid']}: {res['current']} -> {res['new']} ({level})")
    else:
        click.echo(f"PID {res['pid']} priority set to {level} ({res['new']}).")


@cli.command("set-affinity")
@click.argument("pid", type=int)
@click.option("--cpus", required=True, help="Comma-separated CPU indices, e.g. 0,2,4.")
@click.option("--dry-run", is_flag=True, help="Print intended change without applying.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def set_affinity_cmd(pid, cpus, dry_run, yes):
    """Set process CPU affinity."""
    try:
        cpu_list = parse_cpu_list(cpus)
    except Exception as exc:
        _fail(exc)
    _confirm(yes, dry_run, f"Set affinity of PID {pid} to {cpu_list}?")
    try:
        res = set_affinity(pid, cpu_list, dry_run=dry_run)
    except Exception as exc:
        _fail(exc)
    if dry_run:
        click.echo(f"[dry-run] PID {res['pid']}: affinity {res['current']} -> {res['new']}")
    else:
        click.echo(f"PID {res['pid']} affinity set to {res['new']}.")


@cli.command("timer-resolution")
@click.option("--ms", required=True, type=click.IntRange(1, 16), help="Timer resolution in ms (1-16).")
@click.option(
    "--hold",
    default=0.0,
    type=click.FloatRange(min=0),
    show_default=True,
    help="Seconds to hold the timer period before calling timeEndPeriod.",
)
@click.option("--dry-run", is_flag=True, help="Print intended change without applying.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def timer_resolution_cmd(ms, hold, dry_run, yes):
    """Begin and end a Windows timer period."""
    click.echo(
        "Note: timeBeginPeriod changes timer behavior for this process and can "
        "affect other processes on some Windows versions.",
        err=True,
    )
    _confirm(yes, dry_run, f"Set timer resolution to {ms} ms for {hold} seconds?")
    try:
        res = apply_timer_resolution(ms, dry_run=dry_run, hold_seconds=hold)
    except Exception as exc:
        _fail(exc)
    if dry_run:
        click.echo(f"[dry-run] would call {res['would_call']}")
        return
    begin = "OK" if res.get("begin_code") == 0 else "FAILED"
    click.echo(f"timeBeginPeriod({ms}): {begin} (code={res.get('begin_code')})")
    if res.get("ended"):
        ended = "OK" if res.get("end_success") else "FAILED"
        click.echo(f"timeEndPeriod({ms}): {ended} (code={res.get('end_code')})")
    if not res.get("success"):
        sys.exit(1)


@cli.group("profile")
def profile_group():
    """Process profiles."""


@profile_group.command("apply")
@click.argument("name", type=click.Choice(["gaming"]))
@click.option("--pid", required=True, type=int, help="Target PID.")
@click.option("--dry-run", is_flag=True, help="Print intended change without applying.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def profile_apply_cmd(name, pid, dry_run, yes):
    """Apply a profile to a process."""
    try:
        cpus = physical_core_cpus()
    except Exception:
        cpus = []
    _confirm(yes, dry_run, f"Apply gaming profile to PID {pid} (priority high, affinity {cpus})?")
    try:
        res = apply_gaming_profile(pid, dry_run=dry_run, cpus=cpus)
    except Exception as exc:
        _fail(exc)
    if dry_run:
        click.echo(f"[dry-run] PID {res['pid']}: priority -> high, affinity -> {res['affinity']}")
    else:
        click.echo(
            f"PID {res['pid']} gaming profile applied (priority high, affinity {res['affinity']})."
        )


@cli.command("capture")
@click.argument("pid", type=int)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Write the snapshot to this file. Prints JSON when omitted.",
)
def capture_cmd(pid, output):
    """Capture priority and affinity to JSON."""
    try:
        state = capture_state(pid)
        if output:
            write_snapshot(state, output)
    except Exception as exc:
        _fail(exc)
    if output:
        click.echo(f"Snapshot for PID {pid} written to {output}.")
    else:
        _dump_json(state)


@cli.command("restore")
@click.argument("pid", type=int)
@click.option(
    "-i",
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Snapshot file created by capture.",
)
@click.option("--dry-run", is_flag=True, help="Print intended change without applying.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def restore_cmd(pid, input_path, dry_run, yes):
    """Restore priority and affinity from JSON."""
    try:
        state = load_snapshot(input_path)
    except Exception as exc:
        _fail(exc)
    _confirm(
        yes,
        dry_run,
        f"Restore PID {pid} priority {state['priority_value']} and affinity {state['affinity']}?",
    )
    try:
        res = restore_state(pid, state, dry_run=dry_run)
    except Exception as exc:
        _fail(exc)
    detail = f"priority {res['priority']['current']} -> {res['priority']['new']}, "
    detail += f"affinity {res['affinity']['current']} -> {res['affinity']['new']}"
    if dry_run:
        click.echo(f"[dry-run] PID {pid}: {detail}")
    else:
        click.echo(f"PID {pid} restored: {detail}.")


@cli.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Print JSON.")
def doctor_cmd(as_json):
    """Run environment diagnostics."""
    checks = run_doctor()
    passed = sum(1 for _, ok, _ in checks if ok)
    if as_json:
        payload = {
            "checks": [{"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks],
            "passed": passed,
            "total": len(checks),
        }
        click.echo(json.dumps(payload, indent=2))
        return
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        click.echo(f"{name:16} {status:5} {detail}")


@cli.command("game")
@click.option("--dry-run", is_flag=True, help="Preview only. Do not save or change anything.")
@click.option("--name", "game_name", help="Filter by part of the game process name.")
def game_cmd(dry_run, game_name):
    """Choose a running game process and safely raise its priority one step."""
    snapshot_path = game_snapshot_path()
    if not dry_run and os.path.exists(snapshot_path):
        click.echo("An undo is already saved. Run 'win-process-tuner undo' before tuning another process.", err=True)
        sys.exit(1)
    try:
        rows = list_processes(top=None, sort="cpu")
    except Exception as exc:
        _fail(exc)
    safe_processes = []
    for row in rows:
        if (
            row.get("denied")
            or not row.get("name")
            or row["name"].lower() in CRITICAL_NAMES
            or row["pid"] in PROTECTED_PIDS
        ):
            continue
        try:
            check_target(row["pid"])
        except Exception:
            continue
        safe_processes.append(row)

    if game_name is None:
        game_name = click.prompt("Part of the game's process name", type=str).strip()
    if not game_name:
        click.echo("Enter part of the game process name and try again.")
        return
    choices = [row for row in safe_processes if game_name.casefold() in row["name"].casefold()]
    choices = choices[:40]
    if not choices:
        click.echo("No safe process matched. Check the name in Task Manager's Details tab and try again.")
        return

    click.echo("Choose the game process, not its launcher:")
    for index, row in enumerate(choices, start=1):
        click.echo(f"  {index}. {row['name']} (PID {row['pid']})")
    selected = click.prompt("Process number", type=click.IntRange(1, len(choices)))
    target = choices[selected - 1]

    try:
        check_target(target["pid"])
        saved_state = capture_game_state(target["pid"])
    except Exception as exc:
        _fail(exc)
    current_level = next(
        (name for name, value in PRIORITY_LEVELS.items() if value == saved_state["priority_value"]),
        str(saved_state["priority_value"]),
    )
    if current_level not in {"normal", "below-normal", "idle"}:
        click.echo(f"Current priority is {current_level}, already above normal. No change was made.")
        return
    click.echo(f"\nPreview for {saved_state['name']} (PID {saved_state['pid']}):")
    click.echo(f"  Priority: {current_level} -> Above normal")
    click.echo("  CPU affinity, timer settings, and other processes: unchanged")
    if dry_run:
        click.echo("Preview only. Nothing was changed.")
        return

    if not click.confirm("Apply this priority change?", default=False):
        click.echo("Cancelled. Nothing was changed.")
        return
    try:
        write_game_snapshot(saved_state, snapshot_path)
        apply_game_priority(saved_state)
    except Exception as exc:
        if os.path.exists(snapshot_path):
            click.echo("The undo file is available. Run 'win-process-tuner undo' if the change took effect.")
        _fail(exc)
    click.echo("Applied. Original priority saved for undo.")
    click.echo("To restore it later, run: win-process-tuner undo")


@cli.command("undo")
def undo_cmd():
    """Restore the priority saved by the last successful game command."""
    snapshot_path = game_snapshot_path()
    try:
        saved_state = load_game_snapshot(snapshot_path)
    except FileNotFoundError:
        click.echo("No game change is saved to undo.", err=True)
        sys.exit(1)
    except Exception as exc:
        _fail(exc)
    try:
        result = restore_game_state(saved_state)
    except psutil.NoSuchProcess:
        remove_game_snapshot(snapshot_path)
        click.echo("The game process has exited. Its priority is gone, so the undo file was cleared.")
        return
    except ValueError as exc:
        if "different process" in str(exc):
            remove_game_snapshot(snapshot_path)
            click.echo("The original game process has exited. No other process was changed; undo file cleared.")
            return
        _fail(exc)
    except Exception as exc:
        _fail(exc)
    try:
        remove_game_snapshot(snapshot_path)
    except Exception as exc:
        _fail(exc)
    click.echo(f"PID {result['pid']} priority restored. Undo file removed.")


if __name__ == "__main__":
    cli()

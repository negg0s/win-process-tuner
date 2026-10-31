"""Command-line interface for win-process-tuner."""

import sys

import click

from . import __version__
from .doctor import run_doctor
from .processes import (
    PRIORITY_LEVELS,
    inspect_process,
    list_processes,
    parse_cpus,
    set_affinity,
    set_priority,
)
from .profile import apply_gaming_profile
from .timer import apply_timer_resolution


def _confirm(yes, dry_run, message):
    if dry_run or yes:
        return
    if not click.confirm(message, default=False):
        raise click.Abort()


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


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
def list_cmd(top, sort):
    """List running processes."""
    try:
        rows = list_processes(top=top, sort=sort)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    if not rows:
        click.echo("No processes found.")
        return
    click.echo(f"{'PID':>8}  {'CPU%':>6}  {'MEMORY':>10}  {'STATUS':<12}  NAME")
    for r in rows:
        click.echo(
            f"{r['pid']:>8}  {r['cpu']:>6.1f}  {_fmt_bytes(r['memory']):>10}  "
            f"{str(r['status']):<12}  {r['name']}"
        )


@cli.command("inspect")
@click.argument("pid", type=int)
def inspect_cmd(pid):
    """Inspect a process by PID."""
    try:
        info = inspect_process(pid)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
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
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    if dry_run:
        click.echo(
            f"[dry-run] PID {res['pid']}: {res['current']} -> {res['new']} ({level})"
        )
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
        cpu_list = parse_cpus(cpus)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    _confirm(yes, dry_run, f"Set affinity of PID {pid} to {cpu_list}?")
    try:
        res = set_affinity(pid, cpu_list, dry_run=dry_run)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    if dry_run:
        click.echo(
            f"[dry-run] PID {res['pid']}: affinity {res['current']} -> {res['new']}"
        )
    else:
        click.echo(f"PID {res['pid']} affinity set to {res['new']}.")


@cli.command("timer-resolution")
@click.option("--ms", required=True, type=click.IntRange(1, 16), help="Timer resolution in ms (1-16).")
@click.option("--dry-run", is_flag=True, help="Print intended change without applying.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
def timer_resolution_cmd(ms, dry_run, yes):
    """Set Windows timer resolution."""
    _confirm(yes, dry_run, f"Set timer resolution to {ms} ms?")
    try:
        res = apply_timer_resolution(ms, dry_run=dry_run)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    if dry_run:
        click.echo(f"[dry-run] would call {res['would_call']}")
    else:
        status = "OK" if res.get("success") else "FAILED"
        click.echo(f"timer resolution {ms} ms: {status} (code={res.get('code')})")


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
    if name == "gaming":
        cpus = None
        try:
            from .profile import physical_cores_heuristic

            cpus = physical_cores_heuristic()
        except Exception:
            cpus = []
        _confirm(yes, dry_run, f"Apply gaming profile to PID {pid} (priority high, affinity {cpus})?")
        try:
            res = apply_gaming_profile(pid, dry_run=dry_run)
        except Exception as exc:
            click.echo(f"Error: {exc}", err=True)
            sys.exit(1)
        if dry_run:
            click.echo(
                f"[dry-run] PID {res['pid']}: priority -> high, affinity -> {res['affinity']}"
            )
        else:
            click.echo(
                f"PID {res['pid']} gaming profile applied (priority high, affinity {res['affinity']})."
            )


@cli.command("doctor")
def doctor_cmd():
    """Run environment diagnostics."""
    checks = run_doctor()
    for name, ok, detail in checks:
        status = "OK" if ok else "FAIL"
        click.echo(f"{name:16} {status:5} {detail}")


if __name__ == "__main__":
    cli()

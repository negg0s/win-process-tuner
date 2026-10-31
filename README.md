# win-process-tuner

A small command line tool for inspecting and tuning Windows processes. It can
read process details, change priority and affinity, apply a gaming profile, and
hold a timer resolution for a fixed period.

Requirements: Windows, Python 3.9 or newer.

## Install

```bash
pip install -e . --no-cache-dir
```

For development:

```bash
pip install -e . --no-cache-dir pytest
```

## Commands

```text
win-process-tuner list [--top N] [--sort cpu|memory] [--json]
win-process-tuner inspect PID [--json]
win-process-tuner set-priority PID --level high|above-normal|normal|below-normal|idle [--dry-run] [--yes]
win-process-tuner set-affinity PID --cpus 0,2,4 [--dry-run] [--yes]
win-process-tuner capture PID [--output FILE]
win-process-tuner restore PID --input FILE [--dry-run] [--yes]
win-process-tuner timer-resolution --ms 1..16 [--hold SECONDS] [--dry-run] [--yes]
win-process-tuner profile apply gaming --pid PID [--dry-run] [--yes]
win-process-tuner doctor
```

## Examples

Show the busiest processes:

```bash
win-process-tuner list --top 15 --sort cpu
```

Read a process as JSON for a script:

```bash
win-process-tuner inspect 4242 --json
```

Set priority without a prompt:

```bash
win-process-tuner set-priority 4242 --level above-normal --yes
```

Pin a process to CPUs 0, 2, 4:

```bash
win-process-tuner set-affinity 4242 --cpus 0,2,4 --yes
```

Save the current priority and affinity, then restore them later:

```bash
win-process-tuner capture 4242 --output 4242.json
win-process-tuner restore 4242 --input 4242.json --yes
```

Preview the gaming profile. The profile sets high priority and affinity to one
logical CPU per physical core:

```bash
win-process-tuner profile apply gaming --pid 4242 --dry-run
```

Begin a 1 ms timer period for 30 seconds. The command calls `timeBeginPeriod`
at the start and `timeEndPeriod` when the hold ends:

```bash
win-process-tuner timer-resolution --ms 1 --hold 30 --yes
```

Check the environment:

```bash
win-process-tuner doctor
```

## Safety

Mutating commands ask for confirmation unless `--yes` is passed. `--dry-run`
prints the intended change and does not apply it.

The tool refuses to change PID 0, PID 4, and known critical system processes
such as `csrss.exe`, `wininit.exe`, `winlogon.exe`, `services.exe`, and
`lsass.exe`.

Changing another process can fail with access denied. Run the terminal as
Administrator in that case. `doctor` reports whether the current process has
administrator rights.

`restore` refuses to load a snapshot whose PID does not match the target PID.
Snapshots are written to a temporary file and then moved into place.

## Limitations

`timer-resolution` holds the timer period only while the command runs. When the
hold ends, the command calls `timeEndPeriod` and exits. Windows versions differ
in whether a timer period affects only the calling process or the whole system,
so avoid leaving short timer periods active for long periods.

The gaming profile uses `GetLogicalProcessorInformationEx` to find one logical
CPU per physical core. If that call fails or the CPU topology is not supported,
it uses every logical CPU instead of guessing. It does not detect or manage
processor groups larger than 64 logical CPUs.

Process affinity on Windows is limited to the processor group that contains the
target process. CPU index validation uses the total logical CPU count.

Reading some processes requires elevation. `list` keeps inaccessible processes
in the output with `<access denied>` and `denied: true` in JSON mode.

## Tests

```bash
pytest
python tools/check_text.py
```

The text check fails on em dashes, en dashes, and a fixed list of filler
phrases in tracked text files.

## License

MIT

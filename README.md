# win-process-tuner

A small Windows process tuning CLI built with Python, `click`, and `psutil`.
Uses `ctypes` to call `winmm` timer resolution APIs.

## Install

```bash
pip install -e .
```

## Commands

```bash
win-process-tuner list [--top N] [--sort cpu|memory]
win-process-tuner inspect PID
win-process-tuner set-priority PID --level high|above-normal|normal|below-normal|idle [--dry-run] [--yes]
win-process-tuner set-affinity PID --cpus 0,2,4 [--dry-run] [--yes]
win-process-tuner timer-resolution --ms 1..16 [--dry-run] [--yes]
win-process-tuner profile apply gaming --pid PID [--dry-run] [--yes]
win-process-tuner doctor
```

## Safety

Mutating commands prompt for confirmation unless `--yes` is passed.
`--dry-run` prints intended changes without applying them.

## License

MIT
```
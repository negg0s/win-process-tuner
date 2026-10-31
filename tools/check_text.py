#!/usr/bin/env python3
"""Fail when tracked text files contain banned punctuation or phrases."""

import os
from pathlib import Path
import subprocess
import sys

SKIP_FILES = {"tools/check_text.py"}
TEXT_SUFFIXES = {
    ".cfg", ".css", ".html", ".ini", ".js", ".json", ".md", ".py",
    ".rst", ".toml", ".txt", ".yaml", ".yml",
}
REPO_ROOT = Path(__file__).resolve().parents[1]

BANNED_PHRASES = [
    "comprehensive",
    "seamless",
    "robust",
    "leverage",
    "delve",
    "cutting-edge",
    "state-of-the-art",
    "game-changer",
    "unlock",
    "elevate",
    "effortless",
    "streamline",
    "harness",
    "empower",
    "revolutionize",
    "in today's",
    "it's important to note",
    "furthermore",
    "moreover",
]

FORBIDDEN_DASHES = {
    "\u2014": "em dash",
    "\u2013": "en dash",
}


def tracked_files():
    """Yield tracked textual files from this repository, never from CWD."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "-co", "--exclude-standard", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        for path in REPO_ROOT.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                relative = path.relative_to(REPO_ROOT).as_posix()
                if ".git" not in path.parts and "__pycache__" not in path.parts:
                    yield relative
        return
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        relative = os.fsdecode(item).replace("\\", "/")
        if Path(relative).suffix.lower() in TEXT_SUFFIXES:
            yield relative


def read_text(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if b"\0" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def check_file(path):
    text = read_text(path)
    if text is None:
        return []
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        for dash, label in FORBIDDEN_DASHES.items():
            column = line.find(dash)
            if column >= 0:
                problems.append(f"{path}:{number}:{column + 1}: {label}")
        lowered = line.lower()
        for phrase in BANNED_PHRASES:
            column = lowered.find(phrase)
            if column >= 0:
                problems.append(f"{path}:{number}:{column + 1}: banned phrase {phrase!r}")
    return problems


def main():
    problems = []
    for relative_path in tracked_files():
        normalized = relative_path.replace("\\", "/")
        path = REPO_ROOT / relative_path
        if normalized in SKIP_FILES or not path.is_file():
            continue
        problems.extend(check_file(str(path)))
    if problems:
        for problem in problems:
            print(problem)
        print(f"\n{len(problems)} text problem(s) found.")
        return 1
    print("Text check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

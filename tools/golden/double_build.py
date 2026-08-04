#!/usr/bin/env python3
"""Prove that a diorthosis build is byte-for-byte reproducible.

Run the same PDF build in two separate Python processes and compare every file
the builds produce. The output directories are managed by this script, so do
not pass ``-o`` or ``--out``.

Usage:
  python3 tools/golden/double_build.py PDF [BUILD_ARGS ...]

Example:
  python3 tools/golden/double_build.py /tmp/ldlt-balex.pdf --pages 82-84 \\
      --conspectus-page 54 --text-lang la
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def produced_files(root: Path) -> dict[Path, Path]:
  """Map relative output paths to their absolute paths."""
  return {path.relative_to(root): path for path in root.rglob("*") if path.is_file()}


def compare_outputs(first: Path, second: Path) -> bool:
  """Print one verdict per relative output path and return whether all match."""
  first_files = produced_files(first)
  second_files = produced_files(second)
  matched = True
  for relative in sorted(first_files.keys() | second_files.keys(), key=str):
    left = first_files.get(relative)
    right = second_files.get(relative)
    if left is None:
      print(f"DIFFER {relative}: produced only by build 2")
      matched = False
    elif right is None:
      print(f"DIFFER {relative}: produced only by build 1")
      matched = False
    elif left.read_bytes() == right.read_bytes():
      print(f"MATCH  {relative}")
    else:
      print(f"DIFFER {relative}: byte content differs")
      matched = False
  if not first_files and not second_files:
    print("DIFFER no output files were produced")
    return False
  return matched


def run_build(arguments: list[str], output: Path, number: int) -> bool:
  command = [sys.executable, "-m", "diorthosis.cli", "build", *arguments,
             "-o", str(output)]
  print(f"build {number}: {' '.join(command)}", flush=True)
  environment = os.environ.copy()
  environment.pop("PYTHONHASHSEED", None)
  result = subprocess.run(command, env=environment, check=False)
  if result.returncode != 0:
    print(f"build {number} failed with exit code {result.returncode}", file=sys.stderr)
    return False
  return True


def main(arguments: list[str] | None = None) -> int:
  arguments = list(sys.argv[1:] if arguments is None else arguments)
  if not arguments:
    print(__doc__.rstrip(), file=sys.stderr)
    return 2
  if "-o" in arguments or "--out" in arguments:
    print("error: output directories are managed by double_build.py; omit -o/--out",
          file=sys.stderr)
    return 2

  with tempfile.TemporaryDirectory(prefix="diorthosis-double-build-") as temporary:
    root = Path(temporary)
    first = root / "build-1"
    second = root / "build-2"
    if not run_build(arguments, first, 1):
      return 1
    if not run_build(arguments, second, 2):
      return 1
    if not compare_outputs(first, second):
      print("FAIL: build outputs are not byte-identical", file=sys.stderr)
      return 1

  print("PASS: both builds produced byte-identical files")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())

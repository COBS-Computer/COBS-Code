"""Invoke the FEBio executable on a .feb input file."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FebioRunResult:
    returncode: int
    log_path: Path | None
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def run_febio(
    input_file: str | Path,
    febio_executable: str | Path,
    log_file: str | Path | None = None,
    timeout: float | None = None,
) -> FebioRunResult:
    """Run FEBio on `input_file`, returning its exit code and captured output.

    A zero exit code does not by itself mean the analysis converged -- check
    the log with `check_normal_termination` for that.
    """
    args = [str(febio_executable), "-i", str(input_file)]
    if log_file is not None:
        args += ["-o", str(log_file)]

    completed = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    return FebioRunResult(
        returncode=completed.returncode,
        log_path=Path(log_file) if log_file is not None else None,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )

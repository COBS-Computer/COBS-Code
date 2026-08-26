"""Read results back out of an FEBio .log file."""

from __future__ import annotations

from pathlib import Path

NORMAL_TERMINATION_MARKER = "N O R M A L   T E R M I N A T I O N"


def check_normal_termination(log_file: str | Path) -> bool:
    """Whether the FEBio run in `log_file` finished normally (vs. erroring out)."""
    path = Path(log_file)
    with path.open("r") as f:
        f.seek(0, 2)  # end of file
        size = f.tell()
        f.seek(max(size - 2048, 0))
        tail = f.read()
    return NORMAL_TERMINATION_MARKER in tail


def read_final_step_positions(log_file: str | Path) -> dict[int, tuple[float, ...]]:
    """Parse the last "Step" data block of a log file into {node_id: values}.

    FEBio's data-record log output looks like:

        Step = 10
        Time = 1
        Data = x;y;z
        1  0.1  0.2  0.3
        2  0.4  0.5  0.6

    The header line count before the data rows isn't fixed (it depends on
    what's requested in the .feb file's LoadData section), so this scans
    forward from the last "Step" line to the first row that actually looks
    like data (an integer node id followed by numbers), then reads until a
    blank line or another non-data line.
    """
    lines = Path(log_file).read_text().splitlines()

    step_indices = [i for i, line in enumerate(lines) if line.strip().startswith("Step")]
    if not step_indices:
        raise ValueError(f"No 'Step' entries found in {log_file}")
    start = step_indices[-1]

    data_start = None
    for i in range(start, len(lines)):
        if _is_data_row(lines[i]):
            data_start = i
            break
    if data_start is None:
        raise ValueError(f"No data rows found after the last Step in {log_file}")

    positions: dict[int, tuple[float, ...]] = {}
    for line in lines[data_start:]:
        if not _is_data_row(line):
            break
        columns = line.split()
        node_id = int(columns[0])
        positions[node_id] = tuple(float(v) for v in columns[1:])

    return positions


def _is_data_row(line: str) -> bool:
    columns = line.split()
    if not columns:
        return False
    try:
        int(columns[0])
    except ValueError:
        return False
    return len(columns) > 1

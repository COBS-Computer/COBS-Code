from pathlib import Path
from unittest.mock import patch

from cobs.febio import run_febio


@patch("cobs.febio.run.subprocess.run")
def test_run_febio_builds_expected_args(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = "ok"
    mock_run.return_value.stderr = ""

    result = run_febio("model.feb", "febio4.exe", log_file="model.log")

    args, kwargs = mock_run.call_args
    assert args[0] == ["febio4.exe", "-i", "model.feb", "-o", "model.log"]
    assert kwargs["capture_output"] is True
    assert result.succeeded is True
    assert result.log_path == Path("model.log")


@patch("cobs.febio.run.subprocess.run")
def test_run_febio_without_log_file(mock_run):
    mock_run.return_value.returncode = 1
    mock_run.return_value.stdout = ""
    mock_run.return_value.stderr = "error"

    result = run_febio("model.feb", "febio4.exe")

    args, _ = mock_run.call_args
    assert args[0] == ["febio4.exe", "-i", "model.feb"]
    assert result.succeeded is False
    assert result.log_path is None

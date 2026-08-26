from pathlib import Path

import pytest

from cobs.febio import check_normal_termination, read_final_step_positions

FIXTURE = Path(__file__).parent / "fixtures" / "sample.log"


def test_check_normal_termination_true():
    assert check_normal_termination(FIXTURE) is True


def test_check_normal_termination_false(tmp_path):
    log = tmp_path / "failed.log"
    log.write_text("Step = 1\nsomething went wrong\n")
    assert check_normal_termination(log) is False


def test_read_final_step_positions():
    positions = read_final_step_positions(FIXTURE)
    assert positions == {
        1: (0.0, 0.0, 0.0),
        2: (1.1, 0.0, 0.0),
        3: (1.1, 1.1, 0.0),
        4: (0.0, 1.1, 0.0),
    }


def test_read_final_step_positions_uses_last_step(tmp_path):
    log = tmp_path / "two_steps.log"
    log.write_text(
        "Step = 1\nData = x;y;z\n\n1  0  0  0\n\n"
        "Step = 2\nData = x;y;z\n\n1  9  9  9\n"
    )
    assert read_final_step_positions(log) == {1: (9.0, 9.0, 9.0)}


def test_read_final_step_positions_no_step_raises(tmp_path):
    log = tmp_path / "empty.log"
    log.write_text("nothing here\n")
    with pytest.raises(ValueError):
        read_final_step_positions(log)

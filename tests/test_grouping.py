from pathlib import Path

import pytest

from cobs.febio import FebModel, group_by_material, group_by_part, ungrouped

FIXTURE = Path(__file__).parent / "fixtures" / "sample.feb"

POSITIONS = {
    1: (0.0, 0.0, 0.0),
    2: (1.0, 0.0, 0.0),
    3: (1.0, 1.0, 0.0),
    4: (0.0, 1.0, 0.0),
    5: (9.0, 9.0, 9.0),  # not part of Part1/Tissue -- should be excluded
}


@pytest.fixture
def model():
    return FebModel.from_file(FIXTURE)


def test_group_by_part(model):
    groups = group_by_part(model, POSITIONS, ["Part1"])
    assert set(groups["Part1"]) == {1, 2, 3, 4}


def test_group_by_material(model):
    groups = group_by_material(model, POSITIONS, ["Tissue"])
    assert set(groups["Tissue"]) == {1, 2, 3, 4}


def test_group_by_unknown_material_is_empty(model):
    groups = group_by_material(model, POSITIONS, ["Nonexistent"])
    assert groups["Nonexistent"] == {}


def test_ungrouped_default_label():
    assert ungrouped(POSITIONS) == {"All": POSITIONS}


def test_ungrouped_custom_label():
    assert ungrouped(POSITIONS, label="Everything") == {"Everything": POSITIONS}

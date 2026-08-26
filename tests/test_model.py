from pathlib import Path

import pytest

from cobs.febio import FebModel

FIXTURE = Path(__file__).parent / "fixtures" / "sample.feb"


@pytest.fixture
def model():
    return FebModel.from_file(FIXTURE)


def test_get_node_coordinates(model):
    assert model.get_node_coordinates(2) == (1.0, 0.0, 0.0)


def test_set_node_coordinates(model):
    model.set_node_coordinates(2, (5.0, 6.0, 7.0))
    assert model.get_node_coordinates(2) == (5.0, 6.0, 7.0)


def test_set_node_coordinates_bulk(model):
    model.set_node_coordinates_bulk({1: (9, 9, 9), 3: (8, 8, 8)})
    assert model.get_node_coordinates(1) == (9.0, 9.0, 9.0)
    assert model.get_node_coordinates(3) == (8.0, 8.0, 8.0)


def test_unknown_node_raises(model):
    with pytest.raises(KeyError):
        model.get_node_coordinates(999)


def test_get_nodeset_ids(model):
    assert model.get_nodeset_ids("FixedNodes") == [1, 4]


def test_get_part_node_ids(model):
    assert model.get_part_node_ids("Part1") == {1, 2, 3, 4}


def test_get_surface_node_ids(model):
    assert model.get_surface_node_ids("TopSurface") == {1, 2, 3, 4}


def test_get_parts_by_material(model):
    assert model.get_parts_by_material("Tissue") == ["Part1"]


def test_get_parts_by_material_no_match(model):
    assert model.get_parts_by_material("Nonexistent") == []


def test_get_and_set_material_property(model):
    assert model.get_material_property("Tissue", "E") == "1.0"
    model.set_material_property("Tissue", "E", 2.5)
    assert model.get_material_property("Tissue", "E") == "2.5"


def test_get_pressure_loads(model):
    assert model.get_pressure_loads() == {"TopSurface": 0.019}


def test_set_pressure_load_by_surface(model):
    model.set_pressure_load(0.05, surface_name="TopSurface")
    assert model.get_pressure_loads() == {"TopSurface": 0.05}


def test_set_pressure_load_unknown_surface_raises(model):
    with pytest.raises(KeyError):
        model.set_pressure_load(0.05, surface_name="NoSuchSurface")


def test_save_round_trips(model, tmp_path):
    model.set_node_coordinates(1, (1.5, 2.5, 3.5))
    out_path = tmp_path / "out.feb"
    model.save(out_path)

    reloaded = FebModel.from_file(out_path)
    assert reloaded.get_node_coordinates(1) == (1.5, 2.5, 3.5)

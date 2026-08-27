from pathlib import Path

import pytest

from cobs.abaqus import (
    hex8_free_surface_node_ids,
    list_part_names,
    read_part_elements,
    read_part_elset,
    read_part_nodes,
    read_part_nset,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample.inp"


def test_list_part_names():
    assert list_part_names(FIXTURE) == ["PartA", "PartB", "PartC"]


def test_read_part_nodes():
    nodes = read_part_nodes(FIXTURE, "PartA")
    assert nodes == {
        1: (0.0, 0.0, 0.0),
        2: (1.0, 0.0, 0.0),
        3: (1.0, 1.0, 0.0),
        4: (0.0, 1.0, 0.0),
        5: (0.5, 0.5, 1.0),
    }


def test_read_part_nodes_scoped_to_part():
    nodes = read_part_nodes(FIXTURE, "PartB")
    assert nodes == {10: (9.0, 9.0, 9.0), 11: (10.0, 9.0, 9.0)}


def test_read_part_nodes_unknown_part_raises():
    with pytest.raises(KeyError):
        read_part_nodes(FIXTURE, "NoSuchPart")


def test_read_part_nset_explicit():
    ids = read_part_nset(FIXTURE, "PartA", "Set-Explicit")
    assert ids == [1, 2, 3]


def test_read_part_nset_generate():
    ids = read_part_nset(FIXTURE, "PartA", "Set-Generate")
    assert ids == [1, 2, 3, 4, 5]


def test_read_part_nset_wrong_part_raises():
    with pytest.raises(KeyError):
        read_part_nset(FIXTURE, "PartB", "Set-Explicit")


def test_read_part_nset_unknown_name_raises():
    with pytest.raises(KeyError):
        read_part_nset(FIXTURE, "PartA", "NoSuchSet")


def test_read_part_elements():
    elements = read_part_elements(FIXTURE, "PartA")
    assert elements == {1: [1, 2, 3, 4], 2: [2, 3, 4, 5]}


def test_read_part_elements_handles_line_continuation():
    elements = read_part_elements(FIXTURE, "PartA")
    assert elements[2] == [2, 3, 4, 5]


def test_read_part_elset_explicit():
    assert read_part_elset(FIXTURE, "PartA", "Elset-Explicit") == [1]


def test_read_part_elset_generate():
    assert read_part_elset(FIXTURE, "PartA", "Elset-Generate") == [1, 2]


def test_hex8_free_surface_node_ids_excludes_interior_node():
    elements = read_part_elements(FIXTURE, "PartC")
    boundary = hex8_free_surface_node_ids(elements, elements.keys())
    assert 14 not in boundary
    assert boundary == set(range(1, 28)) - {14}

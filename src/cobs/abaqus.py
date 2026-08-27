"""Read node/element data and sets out of Abaqus .inp files.

This is not a general Abaqus keyword-file parser -- it only understands
*Part/*End Part scoping, *Node and *Element data blocks, and *Nset/*Elset
blocks (both explicit id lists and `generate` start/stop/step form), which
is what's needed to pull a part's geometry out for comparison against an
FEBio model, and to find the mesh-connectivity boundary between two named
regions of the same part.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

NodeMap = dict[int, tuple[float, float, float]]

# Local corner-index triples per face for an 8-node hex (C3D8/C3D8R), 0-indexed.
_HEX8_FACES = [
    (0, 1, 2, 3),
    (4, 7, 6, 5),
    (0, 4, 5, 1),
    (1, 5, 6, 2),
    (2, 6, 7, 3),
    (3, 7, 4, 0),
]


def hex8_free_surface_node_ids(
    elements: dict[int, list[int]], element_ids: Iterable[int]
) -> set[int]:
    """Nodes on the free surface of a set of 8-node hex (C3D8/C3D8R) elements.

    A "free" face is one used by exactly one element among `element_ids` --
    this is the boundary of that element subset, whether that's the body's
    true outer surface or a cut against a neighboring, differently-set region.
    `elements` is the full part connectivity from `read_part_elements`.
    """
    face_counts: dict[frozenset[int], int] = {}
    for eid in element_ids:
        nodes = elements[eid]
        for face in _HEX8_FACES:
            key = frozenset(nodes[i] for i in face)
            face_counts[key] = face_counts.get(key, 0) + 1

    boundary_nodes: set[int] = set()
    for face, count in face_counts.items():
        if count == 1:
            boundary_nodes.update(face)
    return boundary_nodes


def quad4_free_edge_node_ids(
    elements: dict[int, list[int]], element_ids: Iterable[int]
) -> set[int]:
    """Nodes on the free edge of a set of 4-node shell (S4/S4R) elements.

    A "free" edge is one used by exactly one element among `element_ids` --
    the shell-mesh analog of `hex8_free_surface_node_ids`.
    """
    edge_counts: dict[frozenset[int], int] = {}
    for eid in element_ids:
        nodes = elements[eid]
        for i in range(4):
            edge = frozenset((nodes[i], nodes[(i + 1) % 4]))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1

    boundary_nodes: set[int] = set()
    for edge, count in edge_counts.items():
        if count == 1:
            boundary_nodes.update(edge)
    return boundary_nodes


def _parse_keyword_line(line: str) -> tuple[str, dict[str, str], set[str]]:
    parts = [p.strip() for p in line.lstrip("*").split(",")]
    keyword = parts[0].upper()
    params: dict[str, str] = {}
    flags: set[str] = set()
    for p in parts[1:]:
        if "=" in p:
            key, value = p.split("=", 1)
            params[key.strip().upper()] = value.strip().strip('"')
        elif p:
            flags.add(p.upper())
    return keyword, params, flags


def list_part_names(inp_path: str | Path) -> list[str]:
    """Names of every *Part in the file, in file order."""
    names = []
    for raw_line in Path(inp_path).read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("*"):
            keyword, params, _ = _parse_keyword_line(line)
            if keyword == "PART" and "NAME" in params:
                names.append(params["NAME"])
    return names


def read_part_nodes(inp_path: str | Path, part_name: str) -> NodeMap:
    """Read the *Node block belonging to *Part, name=<part_name>."""
    nodes: NodeMap = {}
    in_target_part = False
    in_node_block = False

    for raw_line in Path(inp_path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("**"):
            continue

        if line.startswith("*"):
            keyword, params, _ = _parse_keyword_line(line)
            in_node_block = False
            if keyword == "PART":
                in_target_part = params.get("NAME") == part_name
            elif keyword == "END PART":
                in_target_part = False
            elif keyword == "NODE" and in_target_part:
                in_node_block = True
            continue

        if in_node_block:
            node_id, x, y, z = (v.strip() for v in line.split(",")[:4])
            nodes[int(node_id)] = (float(x), float(y), float(z))

    if not nodes:
        raise KeyError(f"No nodes found for part {part_name!r} in {inp_path}")
    return nodes


def _read_part_id_set(
    inp_path: str | Path, part_name: str, set_keyword: str, set_param: str, set_name: str
) -> list[int]:
    """Shared logic for *Nset and *Elset: both are id lists, explicit or `generate`."""
    ids: list[int] = []
    in_target_part = False
    in_target_set = False
    generate = False

    for raw_line in Path(inp_path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("**"):
            continue

        if line.startswith("*"):
            keyword, params, flags = _parse_keyword_line(line)
            in_target_set = False
            if keyword == "PART":
                in_target_part = params.get("NAME") == part_name
            elif keyword == "END PART":
                in_target_part = False
            elif keyword == set_keyword and in_target_part and params.get(set_param) == set_name:
                in_target_set = True
                generate = "GENERATE" in flags
            continue

        if in_target_set:
            values = [v.strip() for v in line.split(",") if v.strip()]
            if generate:
                start, stop, step = (int(v) for v in values[:3])
                ids.extend(range(start, stop + 1, step))
            else:
                ids.extend(int(v) for v in values)

    if not ids:
        raise KeyError(f"{set_keyword.title()} {set_name!r} not found in part {part_name!r} in {inp_path}")
    return ids


def read_part_nset(inp_path: str | Path, part_name: str, nset_name: str) -> list[int]:
    """Read a *Nset defined inside *Part, name=<part_name>."""
    return _read_part_id_set(inp_path, part_name, "NSET", "NSET", nset_name)


def read_part_elset(inp_path: str | Path, part_name: str, elset_name: str) -> list[int]:
    """Read an *Elset defined inside *Part, name=<part_name>."""
    return _read_part_id_set(inp_path, part_name, "ELSET", "ELSET", elset_name)


def read_part_elements(inp_path: str | Path, part_name: str) -> dict[int, list[int]]:
    """Read every *Element block's connectivity for a part: {elem_id: [node_ids]}.

    Handles Abaqus's trailing-comma line continuation for elements whose node
    list is split across multiple lines.
    """
    elements: dict[int, list[int]] = {}
    in_target_part = False
    in_element_block = False
    pending_id: int | None = None
    pending_nodes: list[int] = []

    for raw_line in Path(inp_path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("**"):
            continue

        if line.startswith("*"):
            keyword, params, _ = _parse_keyword_line(line)
            in_element_block = False
            if keyword == "PART":
                in_target_part = params.get("NAME") == part_name
            elif keyword == "END PART":
                in_target_part = False
            elif keyword == "ELEMENT" and in_target_part:
                in_element_block = True
            continue

        if not in_element_block:
            continue

        continues = line.endswith(",")
        values = [v.strip() for v in line.rstrip(",").split(",") if v.strip()]
        if pending_id is None:
            pending_id, values = int(values[0]), values[1:]
        pending_nodes.extend(int(v) for v in values)
        if not continues:
            elements[pending_id] = pending_nodes
            pending_id, pending_nodes = None, []

    if not elements:
        raise KeyError(f"No elements found for part {part_name!r} in {inp_path}")
    return elements

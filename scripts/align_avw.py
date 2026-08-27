"""Identify and (eventually) align the "end arc" of the AVW tissue between
the FEBio model and its Abaqus replacement.

The end arc is the boundary curve where the AVW tissue meets the perineal
body / perineal membrane -- a wide, thin, roughly semicircular edge. This
module finds it in each source:

- FEBio: the AVW shell (_PickedSet33 + _PickedSet34) has a free mesh edge
  loop; the portion of that loop closest to the perineal body (OPAL325_PBody-1)
  lies almost exactly on a single flat plane -- that flat-plane subset is
  the end arc.
- Abaqus: Set-AVW is a solid (hex8) region with no single flat cut face, so
  instead we take its free surface (via hex8_free_surface_node_ids) and keep
  the fraction closest to the perineal body region (Set-PeB) by projection.
"""

from __future__ import annotations

import numpy as np

from cobs.abaqus import hex8_free_surface_node_ids, read_part_elements, read_part_elset, read_part_nodes
from cobs.febio import FebModel

FEB_AVW_SHELL_PARTS = ["_PickedSet33", "_PickedSet34"]
FEB_PBODY_NODES_BLOCK = "OPAL325_PBody-1"
FEB_FLAT_TOLERANCE = 1e-3

INP_AVW_PART = "VW-PeB"
INP_AVW_ELSET = "Set-AVW"
INP_PEB_ELSET = "Set-PeB"
INP_END_ARC_FRACTION = 0.03


def febio_avw_end_arc(model: FebModel) -> dict[int, tuple[float, float, float]]:
    """Node id -> xyz for the flat end-arc boundary of the FEBio AVW shell."""
    all_nodes = model.get_all_node_coordinates()
    boundary_ids = list(model.get_shell_free_edge_node_ids(FEB_AVW_SHELL_PARTS))

    avw_ids = model.get_named_node_ids("OPAL325_AVW_v6-1")
    pbody_ids = model.get_named_node_ids(FEB_PBODY_NODES_BLOCK)
    avw_centroid = np.array([all_nodes[i] for i in avw_ids]).mean(axis=0)
    pbody_centroid = np.array([all_nodes[i] for i in pbody_ids]).mean(axis=0)
    direction = pbody_centroid - avw_centroid
    direction /= np.linalg.norm(direction)

    boundary_coords = np.array([all_nodes[i] for i in boundary_ids])
    proj = (boundary_coords - avw_centroid) @ direction

    # Take a generous slice nearest the perineal body to find which axis is
    # flat for this end cap (its own extent must be found from the *full*
    # boundary loop, since the cap is at that axis's global extreme).
    candidate_order = np.argsort(-proj)
    candidates = boundary_coords[candidate_order[: max(10, len(boundary_ids) // 5)]]
    flat_axis = int(np.argmin(candidates.var(axis=0)))

    axis_values = boundary_coords[:, flat_axis]
    extreme = axis_values.min() if direction[flat_axis] < 0 else axis_values.max()
    flat_ids = [
        bid
        for bid, v in zip(boundary_ids, axis_values)
        if abs(v - extreme) < FEB_FLAT_TOLERANCE
    ]
    return {i: all_nodes[i] for i in flat_ids}


def abaqus_avw_end_arc(inp_path: str) -> list[tuple[float, float, float]]:
    """xyz points for the end-arc region of the Abaqus AVW solid, nearest Set-PeB."""
    nodes = read_part_nodes(inp_path, INP_AVW_PART)
    elements = read_part_elements(inp_path, INP_AVW_PART)
    avw_elem_ids = read_part_elset(inp_path, INP_AVW_PART, INP_AVW_ELSET)
    peb_elem_ids = read_part_elset(inp_path, INP_AVW_PART, INP_PEB_ELSET)

    boundary_ids = list(hex8_free_surface_node_ids(elements, avw_elem_ids))

    avw_node_ids: set[int] = set()
    for eid in avw_elem_ids:
        avw_node_ids.update(elements[eid])
    peb_node_ids: set[int] = set()
    for eid in peb_elem_ids:
        peb_node_ids.update(elements[eid])

    avw_centroid = np.array([nodes[i] for i in avw_node_ids]).mean(axis=0)
    peb_centroid = np.array([nodes[i] for i in peb_node_ids]).mean(axis=0)
    direction = peb_centroid - avw_centroid
    direction /= np.linalg.norm(direction)

    boundary_coords = np.array([nodes[i] for i in boundary_ids])
    proj = (boundary_coords - avw_centroid) @ direction
    order = np.argsort(-proj)
    n = max(1, int(len(boundary_ids) * INP_END_ARC_FRACTION))
    selected = [boundary_ids[i] for i in order[:n]]
    return [nodes[i] for i in selected]

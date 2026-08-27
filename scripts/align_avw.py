"""Identify and (eventually) align the "half arc surface" used as the
registration guide between the FEBio model and its Abaqus replacement.

Per user confirmation, this is not a boundary of the AVW tissue itself --
it's the perineal membrane object each model represents separately:

- FEBio: the Nodes block "OPAL325_PM_mid-1" (392 nodes).
- Abaqus: the part "PM_Plane" (396 nodes) -- the near-matching node count
  is what confirms this is the same anatomical structure.
"""

from __future__ import annotations

from cobs.abaqus import read_part_nodes
from cobs.febio import FebModel

FEB_PM_NODES_BLOCK = "OPAL325_PM_mid-1"
INP_PM_PART = "PM_Plane"


def febio_pm_arc(model: FebModel) -> dict[int, tuple[float, float, float]]:
    """Node id -> xyz for the FEBio perineal membrane object."""
    all_nodes = model.get_all_node_coordinates()
    pm_ids = model.get_named_node_ids(FEB_PM_NODES_BLOCK)
    return {i: all_nodes[i] for i in pm_ids}


def abaqus_pm_arc(inp_path: str) -> list[tuple[float, float, float]]:
    """xyz points for the Abaqus perineal membrane part."""
    return list(read_part_nodes(inp_path, INP_PM_PART).values())

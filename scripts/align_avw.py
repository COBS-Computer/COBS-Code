"""Identify and align the "half arc surface" used as the registration guide
between the FEBio model and its Abaqus replacement.

Per user confirmation, this is not a boundary of the AVW tissue itself --
it's the perineal membrane object each model represents separately:

- FEBio: the Nodes block "OPAL325_PM_mid-1" (392 nodes).
- Abaqus: the part "PM_Plane" (396 nodes) -- the near-matching node count
  is what confirms this is the same anatomical structure.
"""

from __future__ import annotations

import numpy as np

from cobs.abaqus import (
    quad4_free_edge_node_ids,
    read_part_elements,
    read_part_nodes,
    read_part_nset,
)
from cobs.febio import FebModel

FEB_PM_NODES_BLOCK = "OPAL325_PM_mid-1"
FEB_PM_SHELL_PARTS = ["_PickedSet5(5)", "_PickedSet5(5)__2"]
FEB_AVW_NODES_BLOCK = "OPAL325_AVW_v6-1"
FEB_CL_LEFT_BLOCK = "CL Left editable mesh then export.stl"
FEB_CL_RIGHT_BLOCK = "CL Right editable mesh then export.stl"

INP_PM_PART = "PM_Plane"
INP_AVW_PART = "VW-PeB"
INP_AVW_NSET = "Set-AVW"
INP_CL_LEFT_PART = "CL_Left"
INP_CL_RIGHT_PART = "CL_Right"


def febio_pm_arc(model: FebModel) -> dict[int, tuple[float, float, float]]:
    """Node id -> xyz for the FEBio perineal membrane object."""
    all_nodes = model.get_all_node_coordinates()
    pm_ids = model.get_named_node_ids(FEB_PM_NODES_BLOCK)
    return {i: all_nodes[i] for i in pm_ids}


def abaqus_pm_arc(inp_path: str) -> list[tuple[float, float, float]]:
    """xyz points for the Abaqus perineal membrane part."""
    return list(read_part_nodes(inp_path, INP_PM_PART).values())


def febio_pm_boundary(model: FebModel) -> np.ndarray:
    """xyz points on the true free-edge rim of the FEBio perineal membrane shell."""
    all_nodes = model.get_all_node_coordinates()
    boundary_ids = model.get_shell_free_edge_node_ids(FEB_PM_SHELL_PARTS)
    return np.array([all_nodes[i] for i in boundary_ids])


def abaqus_pm_boundary(inp_path: str) -> np.ndarray:
    """xyz points on the true free-edge rim of the Abaqus perineal membrane shell."""
    nodes = read_part_nodes(inp_path, INP_PM_PART)
    elements = read_part_elements(inp_path, INP_PM_PART)
    boundary_ids = quad4_free_edge_node_ids(elements, elements.keys())
    return np.array([nodes[i] for i in boundary_ids])


def _principal_frame(centroid: np.ndarray, faces_toward: np.ndarray, rightward: np.ndarray) -> np.ndarray:
    """An orthonormal 3x3 frame (columns = basis vectors) for a membrane.

    Earlier attempts derived the in-plane rotation from the membrane's own
    shape (PCA variance, or a "find the straight edge" heuristic on its
    boundary) and kept getting it subtly wrong -- shape-based signals are
    fragile against mesh differences between the two models. This instead
    uses two directions with an unambiguous anatomical meaning in *both*
    models: `faces_toward` (a point on the AVW side, fixing the plane
    normal) and `rightward` (pointing from the CL_Left to the CL_Right
    landmark, fixing the in-plane rotation). Neither depends on the
    membrane's own geometry at all, so there's no shape-derived ambiguity
    left to get wrong.
    """
    e3 = faces_toward - centroid
    e3 /= np.linalg.norm(e3)

    u = rightward - np.dot(rightward, e3) * e3
    u /= np.linalg.norm(u)
    v = np.cross(e3, u)

    return np.column_stack([u, v, e3])


def compute_pm_rotation(model: FebModel, inp_path: str) -> tuple[np.ndarray, np.ndarray]:
    """Rotation (3x3) and pivot point that reorient the Abaqus model's
    perineal membrane to match the FEBio one's orientation, as a rigid
    rotation about the Abaqus PM centroid (no translation or scaling yet).

    Apply to any Abaqus-space point `p` as: pivot + rotation @ (p - pivot).
    """
    all_nodes = model.get_all_node_coordinates()
    feb_pm_centroid = febio_pm_boundary(model).mean(axis=0)
    feb_avw_ids = model.get_named_node_ids(FEB_AVW_NODES_BLOCK)
    feb_avw_centroid = np.array([all_nodes[i] for i in feb_avw_ids]).mean(axis=0)
    feb_cl_left_c = np.array(
        [all_nodes[i] for i in model.get_named_node_ids(FEB_CL_LEFT_BLOCK)]
    ).mean(axis=0)
    feb_cl_right_c = np.array(
        [all_nodes[i] for i in model.get_named_node_ids(FEB_CL_RIGHT_BLOCK)]
    ).mean(axis=0)

    inp_pm_centroid = np.array(abaqus_pm_arc(inp_path)).mean(axis=0)
    inp_nodes = read_part_nodes(inp_path, INP_AVW_PART)
    inp_avw_ids = read_part_nset(inp_path, INP_AVW_PART, INP_AVW_NSET)
    inp_avw_centroid = np.array([inp_nodes[i] for i in inp_avw_ids]).mean(axis=0)
    inp_cl_left_c = np.array(list(read_part_nodes(inp_path, INP_CL_LEFT_PART).values())).mean(axis=0)
    inp_cl_right_c = np.array(list(read_part_nodes(inp_path, INP_CL_RIGHT_PART).values())).mean(axis=0)

    feb_frame = _principal_frame(feb_pm_centroid, feb_avw_centroid, feb_cl_right_c - feb_cl_left_c)
    inp_frame = _principal_frame(inp_pm_centroid, inp_avw_centroid, inp_cl_right_c - inp_cl_left_c)

    rotation = feb_frame @ inp_frame.T
    return rotation, inp_pm_centroid


def apply_rotation(
    points: list[tuple[float, float, float]], rotation: np.ndarray, pivot: np.ndarray
) -> list[tuple[float, float, float]]:
    """Rigidly rotate `points` about `pivot` (a translation-free step)."""
    arr = np.array(points)
    rotated = pivot + (arr - pivot) @ rotation.T
    return [tuple(p) for p in rotated]

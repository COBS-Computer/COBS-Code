"""Identify and (eventually) align the "half arc surface" used as the
registration guide between the FEBio model and its Abaqus replacement.

Per user confirmation, this is not a boundary of the AVW tissue itself --
it's the perineal membrane object each model represents separately:

- FEBio: the Nodes block "OPAL325_PM_mid-1" (392 nodes).
- Abaqus: the part "PM_Plane" (396 nodes) -- the near-matching node count
  is what confirms this is the same anatomical structure.
"""

from __future__ import annotations

import numpy as np

from cobs.abaqus import read_part_nodes, read_part_nset
from cobs.febio import FebModel

FEB_PM_NODES_BLOCK = "OPAL325_PM_mid-1"
FEB_AVW_NODES_BLOCK = "OPAL325_AVW_v6-1"
INP_PM_PART = "PM_Plane"
INP_AVW_PART = "VW-PeB"
INP_AVW_NSET = "Set-AVW"


def febio_pm_arc(model: FebModel) -> dict[int, tuple[float, float, float]]:
    """Node id -> xyz for the FEBio perineal membrane object."""
    all_nodes = model.get_all_node_coordinates()
    pm_ids = model.get_named_node_ids(FEB_PM_NODES_BLOCK)
    return {i: all_nodes[i] for i in pm_ids}


def abaqus_pm_arc(inp_path: str) -> list[tuple[float, float, float]]:
    """xyz points for the Abaqus perineal membrane part."""
    return list(read_part_nodes(inp_path, INP_PM_PART).values())


def _principal_frame(points: np.ndarray, centroid: np.ndarray, faces_toward: np.ndarray) -> np.ndarray:
    """An orthonormal 3x3 frame (columns = basis vectors) fit to `points` by PCA.

    PCA alone only determines each axis up to a sign flip, which for a rigid
    registration would let the result come out mirrored or rotated 180
    degrees from what's anatomically correct. Two conventions fix that:
    the plane-normal axis (smallest-variance direction) is flipped to point
    from `centroid` toward `faces_toward` -- the AVW tissue this membrane
    borders, in both models -- and the long in-plane axis is flipped so the
    shape's skew along it is positive, since a perineal membrane isn't
    perfectly symmetric end to end.
    """
    centered = points - centroid
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(-eigvals)
    e1, e2, e3 = (eigvecs[:, i] for i in order)

    if np.dot(e3, faces_toward - centroid) < 0:
        e3 = -e3

    if np.mean((centered @ e1) ** 3) < 0:
        e1 = -e1

    e2 = np.cross(e3, e1)
    e2 /= np.linalg.norm(e2)
    e1 = np.cross(e2, e3)

    return np.column_stack([e1, e2, e3])


def compute_pm_rotation(model: FebModel, inp_path: str) -> tuple[np.ndarray, np.ndarray]:
    """Rotation (3x3) and pivot point that reorient the Abaqus model's
    perineal membrane to match the FEBio one's orientation, as a rigid
    rotation about the Abaqus PM centroid (no translation or scaling yet).

    Apply to any Abaqus-space point `p` as: pivot + rotation @ (p - pivot).
    """
    all_nodes = model.get_all_node_coordinates()
    feb_pm = np.array(list(febio_pm_arc(model).values()))
    feb_pm_centroid = feb_pm.mean(axis=0)
    feb_avw_ids = model.get_named_node_ids(FEB_AVW_NODES_BLOCK)
    feb_avw_centroid = np.array([all_nodes[i] for i in feb_avw_ids]).mean(axis=0)

    inp_pm = np.array(abaqus_pm_arc(inp_path))
    inp_pm_centroid = inp_pm.mean(axis=0)
    inp_nodes = read_part_nodes(inp_path, INP_AVW_PART)
    inp_avw_ids = read_part_nset(inp_path, INP_AVW_PART, INP_AVW_NSET)
    inp_avw_centroid = np.array([inp_nodes[i] for i in inp_avw_ids]).mean(axis=0)

    feb_frame = _principal_frame(feb_pm, feb_pm_centroid, feb_avw_centroid)
    inp_frame = _principal_frame(inp_pm, inp_pm_centroid, inp_avw_centroid)

    rotation = feb_frame @ inp_frame.T
    return rotation, inp_pm_centroid


def apply_rotation(
    points: list[tuple[float, float, float]], rotation: np.ndarray, pivot: np.ndarray
) -> list[tuple[float, float, float]]:
    """Rigidly rotate `points` about `pivot` (a translation-free step)."""
    arr = np.array(points)
    rotated = pivot + (arr - pivot) @ rotation.T
    return [tuple(p) for p in rotated]

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


def _convex_hull_2d(points: np.ndarray) -> np.ndarray:
    """Andrew's monotone-chain convex hull. `points` is (N, 2); returns hull
    vertices in CCW order, no external dependency needed for this."""
    pts = sorted(map(tuple, points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return np.array(lower[:-1] + upper[:-1])


def _straight_edge_direction(
    points: np.ndarray, centroid: np.ndarray, plane_u: np.ndarray, plane_v: np.ndarray
) -> np.ndarray:
    """Unit 3D vector from `centroid` toward the shape's straight edge.

    The perineal membrane is D-shaped: one side is a nearly-straight cut
    edge, the rest is a curved arch. Projected into its own plane, the
    straight edge shows up as the single longest edge of the point cloud's
    convex hull (the arch is curved, so it's made of many short hull edges
    instead). `plane_u`/`plane_v` only need to span the plane -- the result
    doesn't depend on their sign, since flipping both negates the 2D
    coordinates and the recovered 3D midpoint direction is unchanged.
    """
    centered = points - centroid
    coords_2d = np.column_stack([centered @ plane_u, centered @ plane_v])
    hull = _convex_hull_2d(coords_2d)
    n = len(hull)
    edge_lengths = np.linalg.norm(np.roll(hull, -1, axis=0) - hull, axis=1)
    longest = np.argmax(edge_lengths)
    midpoint_2d = (hull[longest] + hull[(longest + 1) % n]) / 2
    direction = midpoint_2d[0] * plane_u + midpoint_2d[1] * plane_v
    return direction / np.linalg.norm(direction)


def _principal_frame(points: np.ndarray, centroid: np.ndarray, faces_toward: np.ndarray) -> np.ndarray:
    """An orthonormal 3x3 frame (columns = basis vectors) fit to `points`.

    The plane normal comes from PCA (smallest-variance direction), flipped
    to point from `centroid` toward `faces_toward` -- the AVW tissue this
    membrane borders, in both models. The in-plane rotation is *not* taken
    from PCA's other two axes, since their sign is ambiguous in a way that
    can silently produce a result rotated 180 degrees from correct (arch
    pointing the wrong way): instead one in-plane axis is pinned directly
    to the straight-edge landmark (see `_straight_edge_direction`), which
    is basis-independent and leaves no remaining ambiguity.
    """
    centered = points - centroid
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(-eigvals)
    e1, e2, e3 = (eigvecs[:, i] for i in order)

    if np.dot(e3, faces_toward - centroid) < 0:
        e3 = -e3

    u = _straight_edge_direction(points, centroid, e1, e2)
    u = u - np.dot(u, e3) * e3  # re-orthogonalize against e3 for precision
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

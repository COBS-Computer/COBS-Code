"""Scatter-plot node positions produced by `cobs.febio.grouping`."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
import numpy as np

from .grouping import GroupedPositions

Plane = Literal["xy", "xz", "yz"]
_PLANE_AXES = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}


def _coords(positions) -> np.ndarray:
    return np.array([xyz[:3] for xyz in positions.values()]) if positions else np.empty((0, 3))


def plot_3d(groups: GroupedPositions, *, title: str | None = None, save_path: str | Path | None = None):
    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")

    plotted = False
    for name, positions in groups.items():
        coords = _coords(positions)
        if coords.size == 0:
            continue
        ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], label=name, s=10)
        plotted = True

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    if title:
        ax.set_title(title)
    if plotted:
        ax.legend()

    if save_path is not None:
        fig.savefig(save_path)
    return fig


def plot_2d(
    groups: GroupedPositions,
    plane: Plane = "xy",
    *,
    title: str | None = None,
    save_path: str | Path | None = None,
):
    if plane not in _PLANE_AXES:
        raise ValueError(f"plane must be one of {list(_PLANE_AXES)}, got {plane!r}")
    i, j = _PLANE_AXES[plane]

    fig, ax = plt.subplots()
    plotted = False
    for name, positions in groups.items():
        coords = _coords(positions)
        if coords.size == 0:
            continue
        ax.scatter(coords[:, i], coords[:, j], label=name, s=10)
        plotted = True

    ax.set_xlabel(plane[0].upper())
    ax.set_ylabel(plane[1].upper())
    ax.set_aspect("equal")
    if title:
        ax.set_title(title)
    if plotted:
        ax.legend()

    if save_path is not None:
        fig.savefig(save_path)
    return fig

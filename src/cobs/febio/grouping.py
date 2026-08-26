"""Group node positions (e.g. from `read_final_step_positions`) by part or material.

Every function here returns the same shape -- {group_name: {node_id: xyz}} --
so plotting code doesn't need to care whether the grouping was by part,
by material, or not grouped at all.
"""

from __future__ import annotations

from typing import Iterable

from .model import FebModel

PositionMap = dict[int, tuple[float, ...]]
GroupedPositions = dict[str, PositionMap]


def group_by_part(
    model: FebModel, positions: PositionMap, part_names: Iterable[str]
) -> GroupedPositions:
    groups: GroupedPositions = {}
    for part_name in part_names:
        node_ids = model.get_part_node_ids(part_name)
        groups[part_name] = {nid: xyz for nid, xyz in positions.items() if nid in node_ids}
    return groups


def group_by_material(
    model: FebModel, positions: PositionMap, material_names: Iterable[str]
) -> GroupedPositions:
    groups: GroupedPositions = {}
    for material_name in material_names:
        node_ids: set[int] = set()
        for part_name in model.get_parts_by_material(material_name):
            node_ids |= model.get_part_node_ids(part_name)
        groups[material_name] = {nid: xyz for nid, xyz in positions.items() if nid in node_ids}
    return groups


def ungrouped(positions: PositionMap, label: str = "All") -> GroupedPositions:
    """Wrap a flat position map so it can be passed to the plotting functions
    alongside actually-grouped data, or plotted as a single "everything" series.
    """
    return {label: positions}

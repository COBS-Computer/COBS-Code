"""Read node coordinates and node sets out of Abaqus .inp files.

This is not a general Abaqus keyword-file parser -- it only understands
*Part/*End Part scoping, *Node data blocks, and *Nset blocks (both explicit
id lists and `generate` start/stop/step form), which is what's needed to
pull a part's geometry out for comparison against an FEBio model.
"""

from __future__ import annotations

from pathlib import Path

NodeMap = dict[int, tuple[float, float, float]]


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


def read_part_nset(inp_path: str | Path, part_name: str, nset_name: str) -> list[int]:
    """Read a *Nset defined inside *Part, name=<part_name>."""
    ids: list[int] = []
    in_target_part = False
    in_target_nset = False
    generate = False

    for raw_line in Path(inp_path).read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("**"):
            continue

        if line.startswith("*"):
            keyword, params, flags = _parse_keyword_line(line)
            in_target_nset = False
            if keyword == "PART":
                in_target_part = params.get("NAME") == part_name
            elif keyword == "END PART":
                in_target_part = False
            elif keyword == "NSET" and in_target_part and params.get("NSET") == nset_name:
                in_target_nset = True
                generate = "GENERATE" in flags
            continue

        if in_target_nset:
            values = [v.strip() for v in line.split(",") if v.strip()]
            if generate:
                start, stop, step = (int(v) for v in values[:3])
                ids.extend(range(start, stop + 1, step))
            else:
                ids.extend(int(v) for v in values)

    if not ids:
        raise KeyError(f"Nset {nset_name!r} not found in part {part_name!r} in {inp_path}")
    return ids

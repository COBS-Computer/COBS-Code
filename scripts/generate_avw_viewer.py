"""Generate a self-contained, rotatable WebGL viewer comparing an FEBio
model's AVW tissue against a replacement AVW from an Abaqus .inp file,
plus each model's perineal membrane object as a registration reference.

Produces a single .html file with the point-cloud data embedded -- open it
directly in a browser, no server needed.

Usage:
    python scripts/generate_avw_viewer.py <feb_file> <inp_file> [out.html]
"""

import base64
import sys
from pathlib import Path

import numpy as np

from cobs.abaqus import list_part_names, read_part_nodes, read_part_nset
from cobs.febio import FebModel

from align_avw import abaqus_pm_arc, febio_pm_arc

FEB_AVW_NODES_BLOCK = "OPAL325_AVW_v6-1"
INP_AVW_PART = "VW-PeB"
INP_AVW_NSET = "Set-AVW"

TEMPLATE_PATH = Path(__file__).parent / "templates" / "avw_viewer_template.html"


def _b64(points: list[tuple[float, float, float]]) -> str:
    arr = np.array(points, dtype=np.float32)
    return base64.b64encode(arr.tobytes()).decode("ascii")


def main(feb_path: str, inp_path: str, out_path: str = "avw_viewer.html") -> None:
    model = FebModel.from_file(feb_path)
    avw_ids = model.get_named_node_ids(FEB_AVW_NODES_BLOCK)
    all_nodes = model.get_all_node_coordinates()
    rest_of_model = [xyz for nid, xyz in all_nodes.items() if nid not in avw_ids]
    old_avw = [all_nodes[nid] for nid in avw_ids]

    new_avw: list[tuple[float, float, float]] = []
    rest_of_abaqus: list[tuple[float, float, float]] = []
    for part_name in list_part_names(inp_path):
        part_nodes = read_part_nodes(inp_path, part_name)
        if part_name == INP_AVW_PART:
            avw_node_ids = set(read_part_nset(inp_path, part_name, INP_AVW_NSET))
            new_avw.extend(part_nodes[nid] for nid in avw_node_ids)
            rest_of_abaqus.extend(
                xyz for nid, xyz in part_nodes.items() if nid not in avw_node_ids
            )
        else:
            rest_of_abaqus.extend(part_nodes.values())

    feb_arc = list(febio_pm_arc(model).values())
    inp_arc = abaqus_pm_arc(inp_path)

    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("__REST_B64__", _b64(rest_of_model))
    html = html.replace("__ABQ_B64__", _b64(rest_of_abaqus))
    html = html.replace("__OLD_B64__", _b64(old_avw))
    html = html.replace("__NEW_B64__", _b64(new_avw))
    html = html.replace("__FEBARC_B64__", _b64(feb_arc))
    html = html.replace("__INPARC_B64__", _b64(inp_arc))
    html = html.replace("__REST_COUNT__", str(len(rest_of_model)))
    html = html.replace("__ABQ_COUNT__", str(len(rest_of_abaqus)))
    html = html.replace("__OLD_COUNT__", str(len(old_avw)))
    html = html.replace("__NEW_COUNT__", str(len(new_avw)))
    html = html.replace("__FEBARC_COUNT__", str(len(feb_arc)))
    html = html.replace("__INPARC_COUNT__", str(len(inp_arc)))

    Path(out_path).write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"FEBio model (without AVW):  {len(rest_of_model)} nodes")
    print(f"Abaqus model (without AVW): {len(rest_of_abaqus)} nodes")
    print(f"Old AVW (FEBio):            {len(old_avw)} nodes")
    print(f"New AVW (Abaqus):           {len(new_avw)} nodes")
    print(f"Perineal membrane (FEBio):  {len(feb_arc)} nodes")
    print(f"Perineal membrane (Abaqus): {len(inp_arc)} nodes")


if __name__ == "__main__":
    main(*sys.argv[1:])

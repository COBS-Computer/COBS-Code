"""Plot an FEBio model's non-AVW nodes against the old and new AVW point
clouds (old = current FEBio tissue, new = from an Abaqus .inp file), to
sanity-check alignment before swapping the tissue in.

Usage:
    python scripts/compare_avw_pointclouds.py <feb_file> <inp_file> [out.png]
"""

import sys

import matplotlib.pyplot as plt

from cobs.abaqus import read_part_nodes, read_part_nset
from cobs.febio import FebModel

FEB_AVW_NODES_BLOCK = "OPAL325_AVW_v6-1"
INP_AVW_PART = "VW-PeB"
INP_AVW_NSET = "Set-AVW"


def main(feb_path: str, inp_path: str, out_path: str = "avw_comparison.png") -> None:
    model = FebModel.from_file(feb_path)
    avw_ids = model.get_named_node_ids(FEB_AVW_NODES_BLOCK)
    all_nodes = model.get_all_node_coordinates()
    rest_of_model = [xyz for nid, xyz in all_nodes.items() if nid not in avw_ids]
    old_avw = [all_nodes[nid] for nid in avw_ids]

    inp_nodes = read_part_nodes(inp_path, INP_AVW_PART)
    inp_avw_ids = read_part_nset(inp_path, INP_AVW_PART, INP_AVW_NSET)
    new_avw = [inp_nodes[nid] for nid in inp_avw_ids]

    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(projection="3d")

    def scatter(points, **kwargs):
        xs, ys, zs = zip(*points)
        ax.scatter(xs, ys, zs, **kwargs)

    scatter(rest_of_model, label="Model (without AVW)", s=3, alpha=0.15, color="tab:blue")
    scatter(old_avw, label="Old AVW (current FEBio tissue)", s=6, alpha=0.6, color="tab:red")
    scatter(new_avw, label="New AVW (from Abaqus)", s=10, alpha=0.9, color="tab:orange")

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    ax.set_title("FEBio model vs. old and new AVW")
    ax.legend()
    fig.savefig(out_path, dpi=150)

    print(f"Saved {out_path}")
    print(f"Model (without AVW): {len(rest_of_model)} nodes")
    print(f"Old AVW (FEBio):     {len(old_avw)} nodes")
    print(f"New AVW (Abaqus):    {len(new_avw)} nodes")


if __name__ == "__main__":
    main(*sys.argv[1:])

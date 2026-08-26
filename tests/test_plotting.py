import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from cobs.febio.plotting import plot_2d, plot_3d

GROUPS = {
    "Part1": {1: (0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0)},
    "Part2": {3: (1.0, 1.0, 0.0), 4: (0.0, 1.0, 0.0)},
}


def test_plot_3d_saves_file(tmp_path):
    out = tmp_path / "out3d.png"
    fig = plot_3d(GROUPS, title="test", save_path=out)
    try:
        assert out.exists()
    finally:
        plt.close(fig)


def test_plot_2d_saves_file(tmp_path):
    out = tmp_path / "out2d.png"
    fig = plot_2d(GROUPS, plane="xy", save_path=out)
    try:
        assert out.exists()
    finally:
        plt.close(fig)


def test_plot_2d_invalid_plane_raises():
    with pytest.raises(ValueError):
        plot_2d(GROUPS, plane="bogus")


def test_plot_handles_empty_group(tmp_path):
    out = tmp_path / "empty.png"
    fig = plot_3d({"Empty": {}}, save_path=out)
    try:
        assert out.exists()
    finally:
        plt.close(fig)

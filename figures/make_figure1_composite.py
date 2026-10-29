"""Render Figure 1: an illustrative 3D cell state and constraint-checked loop.

Panel a is a conceptual 3D diagram of the abstract state variables used by the
synthetic discrete-event benchmark. It is not a physical robot model, collision
model, or a result-producing simulation panel. Panel b maps those variables to
the implemented verification and recovery interfaces.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from audit_panel_alignment import require_matplotlib_panel_alignment


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures" / "publication"

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
    }
)

INK = "#0f172a"
EDGE = "#475569"
PALE_BLUE = "#dbeafe"
PALE_GREEN = "#dcfce7"
PALE_YELLOW = "#fef3c7"
ACCENT = "#2563eb"


def cuboid(ax: plt.Axes, origin: tuple[float, float, float], size: tuple[float, float, float], color: str, alpha: float = 1.0) -> None:
    x, y, z = origin
    dx, dy, dz = size
    vertices = np.array(
        [
            [x, y, z], [x + dx, y, z], [x + dx, y + dy, z], [x, y + dy, z],
            [x, y, z + dz], [x + dx, y, z + dz], [x + dx, y + dy, z + dz], [x, y + dy, z + dz],
        ]
    )
    faces = [
        [vertices[i] for i in [0, 1, 2, 3]],
        [vertices[i] for i in [4, 5, 6, 7]],
        [vertices[i] for i in [0, 1, 5, 4]],
        [vertices[i] for i in [1, 2, 6, 5]],
        [vertices[i] for i in [2, 3, 7, 6]],
        [vertices[i] for i in [3, 0, 4, 7]],
    ]
    ax.add_collection3d(Poly3DCollection(faces, facecolors=color, edgecolors=EDGE, linewidths=0.35, alpha=alpha))


def draw_3d_cell(ax: plt.Axes) -> None:
    # Table and stateful elements are illustrative only; coordinates have no
    # physical unit and are not consumed by the experiment engine.
    cuboid(ax, (0.0, 0.0, -0.25), (9.5, 6.0, 0.25), "#e2e8f0")
    cuboid(ax, (4.35, 2.35, 0.0), (1.2, 1.2, 0.34), "#94a3b8")
    cuboid(ax, (4.62, 2.64, 0.34), (0.66, 0.58, 0.18), "#22c55e")
    cuboid(ax, (7.4, 4.25, 0.0), (1.25, 0.95, 0.55), "#f59e0b")
    cuboid(ax, (1.0, 4.15, 0.0), (0.35, 0.35, 2.1), "#a855f7")
    cuboid(ax, (0.65, 3.75, 2.1), (1.05, 0.65, 0.28), "#c4b5fd")

    base = np.array([1.8, 1.55, 0.20])
    shoulder = np.array([2.25, 1.85, 1.55])
    elbow = np.array([3.35, 2.38, 1.35])
    wrist = np.array([4.15, 2.62, 0.74])
    gripper = np.array([4.55, 2.70, 0.59])
    cuboid(ax, (1.35, 1.1, 0.0), (0.9, 0.9, 0.35), "#2563eb")
    arm = np.vstack([base, shoulder, elbow, wrist, gripper])
    ax.plot(arm[:, 0], arm[:, 1], arm[:, 2], color="#2563eb", linewidth=5.6, solid_capstyle="round", zorder=5)
    ax.scatter(arm[:, 0], arm[:, 1], arm[:, 2], color="#1d4ed8", s=22, depthshade=False, zorder=6)
    ax.plot([4.55, 4.72], [2.70, 2.53], [0.59, 0.50], color=INK, linewidth=1.6)
    ax.plot([4.55, 4.72], [2.70, 2.87], [0.59, 0.50], color=INK, linewidth=1.6)
    ax.quiver(4.55, 2.70, 0.62, 0.25, 0.0, -0.10, length=1.0, normalize=False, color=ACCENT, arrow_length_ratio=0.18, linewidth=0.8)

    ax.text2D(0.12, 0.985, "Abstract cell state (illustrative)", transform=ax.transAxes, fontsize=6.5, color=INK, va="top")
    ax.set_xlim(0, 9.5)
    ax.set_ylim(0, 6.0)
    ax.set_zlim(-0.25, 2.8)
    ax.view_init(elev=26, azim=-58)
    ax.set_axis_off()


def box(ax: plt.Axes, xy: tuple[float, float], width: float, height: float, title: str, subtitle: str, fill: str, accent: bool = False) -> None:
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.014,rounding_size=0.025",
        linewidth=1.15 if accent else 0.75,
        edgecolor=ACCENT if accent else EDGE,
        facecolor=fill,
    )
    ax.add_patch(patch)
    ax.text(
        x + width / 2,
        y + height * 0.64,
        title,
        ha="center",
        va="center",
        fontsize=5.7,
        linespacing=1.12,
        color=INK,
    )
    ax.text(
        x + width / 2,
        y + height * 0.28,
        subtitle,
        ha="center",
        va="center",
        fontsize=5.1,
        linespacing=1.08,
        color=EDGE,
    )


def arrow(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str = EDGE,
    connectionstyle: str = "arc3",
) -> None:
    """Draw a connector entirely in the whitespace between workflow boxes."""

    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=8,
            linewidth=0.85,
            color=color,
            connectionstyle=connectionstyle,
            shrinkA=0,
            shrinkB=0,
            zorder=0,
        )
    )


def draw_loop(ax: plt.Axes) -> None:
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.12, 0.985, "Constraint-checked decision loop", fontsize=6.5, color=INK, va="top")
    # The top row is the candidate-to-verifier path. The lower row returns from
    # execution through event recording and repair, leaving every connector in open space.
    top_y, top_h = 0.62, 0.17
    bottom_y, bottom_h = 0.25, 0.18
    top_x = (0.04, 0.285, 0.53, 0.775)
    top_w = 0.18
    bottom_x = (0.05, 0.37, 0.69)
    bottom_w = 0.26

    arrow(ax, (top_x[0] + top_w + 0.006, top_y + top_h / 2), (top_x[1] - 0.006, top_y + top_h / 2))
    arrow(ax, (top_x[1] + top_w + 0.006, top_y + top_h / 2), (top_x[2] - 0.006, top_y + top_h / 2))
    arrow(ax, (top_x[2] + top_w + 0.006, top_y + top_h / 2), (top_x[3] - 0.006, top_y + top_h / 2))
    arrow(ax, (top_x[3] + top_w / 2, top_y - 0.008), (bottom_x[2] + bottom_w / 2, bottom_y + bottom_h + 0.008))
    arrow(ax, (bottom_x[2] - 0.008, bottom_y + bottom_h / 2), (bottom_x[1] + bottom_w + 0.008, bottom_y + bottom_h / 2))
    arrow(ax, (bottom_x[1] - 0.008, bottom_y + bottom_h / 2), (bottom_x[0] + bottom_w + 0.008, bottom_y + bottom_h / 2))
    arrow(
        ax,
        (bottom_x[0] + bottom_w / 2, bottom_y + bottom_h + 0.008),
        (top_x[0] + top_w / 2, top_y - 0.008),
        color=ACCENT,
        connectionstyle="arc3,rad=-0.38",
    )

    box(ax, (top_x[0], top_y), top_w, top_h, "1. State\nabstraction", "typed predicates", PALE_BLUE)
    box(ax, (top_x[1], top_y), top_w, top_h, "2. Candidate\ngenerator", "structured token", PALE_BLUE)
    box(ax, (top_x[2], top_y), top_w, top_h, "3. Symbolic\ncompiler", "binds actions", PALE_BLUE)
    box(ax, (top_x[3], top_y), top_w, top_h, "4. Pre-dispatch\nchecker", "process, tool,\nquality", PALE_BLUE, accent=True)
    box(ax, (bottom_x[2], bottom_y), bottom_w, bottom_h, "5. Discrete-event\nexecutor", "synthetic cell", "#f8fafc")
    box(ax, (bottom_x[1], bottom_y), bottom_w, bottom_h, "6. Event logger +\nstate update", "emitted reason", "#f8fafc")
    box(ax, (bottom_x[0], bottom_y), bottom_w, bottom_h, "7. Verified suffix\nrepair", "modeled constraints", PALE_GREEN, accent=True)
    ax.text(0.02, 0.04, "The numbered modules update state before constrained repair.", fontsize=5.5, color=EDGE, va="bottom")


def export(fig: mpl.figure.Figure, axes: list[plt.Axes]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    require_matplotlib_panel_alignment(
        fig,
        axes=axes,
        panel_ids=["a", "b"],
        json_out=OUT / "fig1_architecture.alignment.json",
        overlay_svg=OUT / "fig1_architecture.alignment.svg",
        tolerance_pt=1.5,
        gutter_tolerance_pt=1.5,
        require_panel_labels=True,
        strict=True,
    )
    fig.savefig(OUT / "fig1_architecture.svg", dpi=600, facecolor="white")
    fig.savefig(OUT / "fig1_architecture.pdf", dpi=600, facecolor="white")
    fig.savefig(OUT / "fig1_architecture.png", dpi=600, facecolor="white")
    fig.savefig(OUT / "fig1_architecture.tiff", dpi=600, facecolor="white")
    plt.close(fig)


def main() -> None:
    fig = plt.figure(figsize=(7.2, 3.15))
    grid = fig.add_gridspec(1, 2, width_ratios=(1.03, 1.26), wspace=0.10)
    ax3d = fig.add_subplot(grid[0, 0], projection="3d")
    axloop = fig.add_subplot(grid[0, 1])
    draw_3d_cell(ax3d)
    draw_loop(axloop)
    ax3d.text2D(0.02, 0.985, "a", transform=ax3d.transAxes, fontweight="bold", fontsize=8, va="top")
    axloop.text(0.02, 0.985, "b", transform=axloop.transAxes, fontweight="bold", fontsize=8, va="top")
    fig.subplots_adjust(left=0.035, right=0.99, top=0.96, bottom=0.06)
    export(fig, [ax3d, axloop])
    print("Figure 1 written to", OUT)


if __name__ == "__main__":
    main()

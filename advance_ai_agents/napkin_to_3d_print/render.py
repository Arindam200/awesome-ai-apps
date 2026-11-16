"""Headless four-view renders of an STL, used both in the UI and as Kimi's "eyes".

Matplotlib keeps this dependency-free (no OpenGL), which matters because the
renders are generated inside a Streamlit server process.
"""

from __future__ import annotations

import io

import numpy as np
import trimesh
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

VIEWS = [
    ("Front", 0, -90, "ortho"),
    ("Right", 0, 0, "ortho"),
    ("Top", 90, -90, "ortho"),
    ("Isometric", 28, -55, "persp"),
]
BASE = np.array([0.96, 0.55, 0.20])  # PLA orange
LIGHT = np.array([0.35, -0.55, 0.75])


def render_views(stl_bytes: bytes, size_mm: list[float] | None = None) -> bytes:
    """Return a 2x2 PNG grid: front, right, top, isometric.

    Pass the coarse preview mesh; matplotlib slows down past ~30k triangles.
    """
    mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl", force="mesh")
    lo, hi = mesh.bounds
    center = (lo + hi) / 2
    span = float(max(hi - lo)) * 0.58 or 1.0

    # Matplotlib depth-sorts whole polygons (painter's algorithm), so long CAD
    # triangles sort wrongly. Small triangles plus back-face culling fix that.
    if len(mesh.faces) < 40000:
        mesh = mesh.subdivide_to_size(max_edge=span / 12, max_iter=6)
    tris = mesh.triangles
    normals = mesh.face_normals
    light = LIGHT / np.linalg.norm(LIGHT)
    shade = 0.35 + 0.65 * np.clip(normals @ light, 0, 1)
    colors = np.clip(BASE[None, :] * shade[:, None] + 0.04, 0, 1)

    fig = Figure(figsize=(10, 10), dpi=110, facecolor="white")
    FigureCanvasAgg(fig)
    for i, (name, elev, azim, proj) in enumerate(VIEWS):
        ax = fig.add_subplot(2, 2, i + 1, projection="3d")
        e, a = np.radians(elev), np.radians(azim)
        eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        front = normals @ eye > 1e-6
        # Edges drawn in the face colour hide the anti-aliasing seams between triangles.
        ax.add_collection3d(Poly3DCollection(tris[front], facecolors=colors[front], edgecolors=colors[front], linewidths=0.6))
        for setter, c in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), center):
            setter(c - span, c + span)
        ax.set_box_aspect((1, 1, 1))
        ax.set_proj_type(proj)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(name, fontsize=13, color="#333")

    if size_mm:
        w, d, h = size_mm
        fig.suptitle(f"W {w:.1f} × D {d:.1f} × H {h:.1f} mm  (X × Y × Z)", fontsize=14, color="#111")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=0.93, wspace=0, hspace=0.06)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    return buf.getvalue()


def mesh_report(stl_bytes: bytes) -> dict:
    mesh = trimesh.load(io.BytesIO(stl_bytes), file_type="stl", force="mesh")
    return {"watertight": bool(mesh.is_watertight), "triangles": int(len(mesh.faces))}

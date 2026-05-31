"""Write BVH files from a BvhData instance."""

from __future__ import annotations

from io import StringIO
import numpy as np

from bvh_reader import BvhData, BvhJoint


def write_bvh(data: BvhData, path: str) -> None:
    """Serialise *data* to a BVH file at *path*."""
    buf = StringIO()
    buf.write("HIERARCHY\n")
    _write_joint(buf, data, 0, indent=0)
    buf.write("MOTION\n")
    buf.write(f"Frames: {data.num_frames}\n")
    frame_time = 1.0 / data.fps if data.fps > 0 else 1.0 / 30.0
    buf.write(f"Frame Time: {frame_time:.8f}\n")
    for row in data.frames:
        buf.write(" ".join(f"{v:.6f}" for v in row) + "\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(buf.getvalue())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_joint(buf: StringIO, data: BvhData, idx: int, indent: int) -> None:
    jt = data.joints[idx]
    pad = "\t" * indent
    keyword = "ROOT" if jt.parent_idx == -1 else "JOINT"
    buf.write(f"{pad}{keyword} {jt.name}\n")
    buf.write(f"{pad}{{\n")
    o = jt.offset
    buf.write(f"{pad}\tOFFSET {o[0]:.6f} {o[1]:.6f} {o[2]:.6f}\n")
    ch_str = " ".join(jt.channels)
    buf.write(f"{pad}\tCHANNELS {len(jt.channels)} {ch_str}\n")
    for child_idx in jt.children:
        _write_joint(buf, data, child_idx, indent + 1)
    if not jt.children:
        buf.write(f"{pad}\tEnd Site\n")
        buf.write(f"{pad}\t{{\n")
        buf.write(f"{pad}\t\tOFFSET 0.000000 0.000000 0.000000\n")
        buf.write(f"{pad}\t}}\n")
    buf.write(f"{pad}}}\n")

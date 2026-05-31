"""Parse BVH files into an in-memory representation."""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass
class BvhJoint:
    name: str
    parent_idx: int          # -1 for root
    offset: np.ndarray       # (3,) local offset from parent in T-pose
    channels: list[str]      # e.g. ['Zrotation', 'Xrotation', 'Yrotation']
    channel_start: int = 0   # index into flat frame row
    children: list[int] = field(default_factory=list)


@dataclass
class BvhData:
    joints: list[BvhJoint]
    frames: np.ndarray   # (T, total_channels)  float32
    fps: float

    @property
    def num_frames(self) -> int:
        return len(self.frames)

    def get_joint(self, name: str) -> BvhJoint | None:
        lo = name.lower()
        for j in self.joints:
            if j.name.lower() == lo:
                return j
        return None

    def get_joint_idx(self, name: str) -> int:
        lo = name.lower()
        for i, j in enumerate(self.joints):
            if j.name.lower() == lo:
                return i
        return -1


def read_bvh(path: str) -> BvhData:
    """Read a BVH file and return a BvhData instance."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    hier_text, _, motion_text = content.partition("MOTION")
    joints = _parse_hierarchy(hier_text)
    frames, fps = _parse_motion(motion_text, sum(len(j.channels) for j in joints))
    return BvhData(joints=joints, frames=frames, fps=fps)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_hierarchy(text: str) -> list[BvhJoint]:
    joints: list[BvhJoint] = []
    parent_stack: list[int] = []
    in_end_site = False
    total_channels = 0

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue

        if s == "End Site":
            in_end_site = True
            continue

        if in_end_site:
            if s == "}":
                in_end_site = False
            continue  # skip everything inside End Site block

        if s.startswith(("ROOT", "JOINT")):
            name = s.split(None, 1)[1]
            parent_idx = parent_stack[-1] if parent_stack else -1
            jt = BvhJoint(
                name=name,
                parent_idx=parent_idx,
                offset=np.zeros(3),
                channels=[],
                channel_start=total_channels,
                children=[],
            )
            if parent_idx >= 0:
                joints[parent_idx].children.append(len(joints))
            joints.append(jt)

        elif s == "{":
            parent_stack.append(len(joints) - 1)

        elif s == "}":
            if parent_stack:
                parent_stack.pop()

        elif s.startswith("OFFSET"):
            parts = s.split()
            if joints:
                joints[-1].offset = np.array(
                    [float(parts[1]), float(parts[2]), float(parts[3])]
                )

        elif s.startswith("CHANNELS"):
            parts = s.split()
            n = int(parts[1])
            if joints:
                joints[-1].channels = parts[2 : 2 + n]
                joints[-1].channel_start = total_channels
                total_channels += n

    return joints


def _parse_motion(text: str, expected_cols: int) -> tuple[np.ndarray, float]:
    fps = 30.0
    rows: list[list[float]] = []

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith("Frame Time:"):
            ft = float(s.split(":")[1])
            fps = 1.0 / ft if ft > 0 else 30.0
        elif s.startswith("Frames:"):
            pass  # we infer count from actual rows
        elif s[0].isdigit() or s[0] in "-+":
            vals = list(map(float, s.split()))
            if len(vals) >= expected_cols:
                rows.append(vals[:expected_cols])

    frames = np.array(rows, dtype=np.float32) if rows else np.zeros((0, expected_cols), dtype=np.float32)
    return frames, fps

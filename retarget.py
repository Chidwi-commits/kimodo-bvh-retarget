"""Retarget Kimodo SOMA BVH animations onto Mixamo joint naming.

Algorithm
---------
Both SOMA and Mixamo use a standard T-pose with identity world rotations,
so local rotations transfer directly between skeletons.  The only
corrections needed are:

  1. Joint rename via SOMA_TO_MIXAMO.
  2. Root-position scale (Kimodo outputs metres; Mixamo FBX often uses cm).
  3. Optional yaw rotation applied to the root joint.

Joints not present in the mapping are kept with their original names.
"""

from __future__ import annotations

import copy
import math

import numpy as np
from scipy.spatial.transform import Rotation as R

from bvh_reader import BvhData, BvhJoint


# ---------------------------------------------------------------------------
# Bone-name mapping: SOMA (lowercase key) → Mixamo (output name)
# ---------------------------------------------------------------------------

SOMA_TO_MIXAMO: dict[str, str] = {
    # Root & Spine
    "hips":            "mixamorig:Hips",
    "spine1":          "mixamorig:Spine",
    "spine2":          "mixamorig:Spine1",
    "chest":           "mixamorig:Spine2",
    # Neck & Head
    "neck1":           "mixamorig:Neck",
    "head":            "mixamorig:Head",
    # Left Arm
    "leftshoulder":    "mixamorig:LeftShoulder",
    "leftarm":         "mixamorig:LeftArm",
    "leftforearm":     "mixamorig:LeftForeArm",
    "lefthand":        "mixamorig:LeftHand",
    # Right Arm
    "rightshoulder":   "mixamorig:RightShoulder",
    "rightarm":        "mixamorig:RightArm",
    "rightforearm":    "mixamorig:RightForeArm",
    "righthand":       "mixamorig:RightHand",
    # Left Leg
    "leftleg":         "mixamorig:LeftUpLeg",
    "leftshin":        "mixamorig:LeftLeg",
    "leftfoot":        "mixamorig:LeftFoot",
    "lefttoebase":     "mixamorig:LeftToeBase",
    # Right Leg
    "rightleg":        "mixamorig:RightUpLeg",
    "rightshin":       "mixamorig:RightLeg",
    "rightfoot":       "mixamorig:RightFoot",
    "righttoebase":    "mixamorig:RightToeBase",
    # Left fingers
    "lefthandthumb1":   "mixamorig:LeftHandThumb1",
    "lefthandthumb2":   "mixamorig:LeftHandThumb2",
    "lefthandthumb3":   "mixamorig:LeftHandThumb3",
    "lefthandindex1":   "mixamorig:LeftHandIndex1",
    "lefthandindex2":   "mixamorig:LeftHandIndex2",
    "lefthandindex3":   "mixamorig:LeftHandIndex3",
    "lefthandindex4":   "mixamorig:LeftHandIndex4",
    "lefthandmiddle1":  "mixamorig:LeftHandMiddle1",
    "lefthandmiddle2":  "mixamorig:LeftHandMiddle2",
    "lefthandmiddle3":  "mixamorig:LeftHandMiddle3",
    "lefthandmiddle4":  "mixamorig:LeftHandMiddle4",
    "lefthandring1":    "mixamorig:LeftHandRing1",
    "lefthandring2":    "mixamorig:LeftHandRing2",
    "lefthandring3":    "mixamorig:LeftHandRing3",
    "lefthandring4":    "mixamorig:LeftHandRing4",
    "lefthandpinky1":   "mixamorig:LeftHandPinky1",
    "lefthandpinky2":   "mixamorig:LeftHandPinky2",
    "lefthandpinky3":   "mixamorig:LeftHandPinky3",
    "lefthandpinky4":   "mixamorig:LeftHandPinky4",
    # Right fingers
    "righthandthumb1":  "mixamorig:RightHandThumb1",
    "righthandthumb2":  "mixamorig:RightHandThumb2",
    "righthandthumb3":  "mixamorig:RightHandThumb3",
    "righthandindex1":  "mixamorig:RightHandIndex1",
    "righthandindex2":  "mixamorig:RightHandIndex2",
    "righthandindex3":  "mixamorig:RightHandIndex3",
    "righthandindex4":  "mixamorig:RightHandIndex4",
    "righthandmiddle1": "mixamorig:RightHandMiddle1",
    "righthandmiddle2": "mixamorig:RightHandMiddle2",
    "righthandmiddle3": "mixamorig:RightHandMiddle3",
    "righthandmiddle4": "mixamorig:RightHandMiddle4",
    "righthandring1":   "mixamorig:RightHandRing1",
    "righthandring2":   "mixamorig:RightHandRing2",
    "righthandring3":   "mixamorig:RightHandRing3",
    "righthandring4":   "mixamorig:RightHandRing4",
    "righthandpinky1":  "mixamorig:RightHandPinky1",
    "righthandpinky2":  "mixamorig:RightHandPinky2",
    "righthandpinky3":  "mixamorig:RightHandPinky3",
    "righthandpinky4":  "mixamorig:RightHandPinky4",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def retarget(
    src: BvhData,
    scale: float = 1.0,
    yaw_deg: float = 0.0,
    strip_namespace: bool = False,
    log=None,
) -> tuple[BvhData, dict]:
    """Return a new BvhData with Mixamo joint names.

    Parameters
    ----------
    src:             Parsed Kimodo/SOMA BVH.
    scale:           Multiply root position and all offsets by this value.
                     Use 100 to convert metres → centimetres.
    yaw_deg:         Rotate the root orientation around Y by this many degrees.
    strip_namespace: If True, remove the 'mixamorig:' prefix from joint names
                     (useful for software that chokes on colons).
    log:             Optional callable(str) for progress messages.

    Returns
    -------
    (retargeted BvhData, stats_dict)
    """
    _log = log or (lambda msg: None)

    _log(f"Source joints : {len(src.joints)}")
    _log(f"Source frames : {src.num_frames}  @  {src.fps:.2f} fps")
    _log(f"Scale         : {scale}")
    _log(f"Yaw offset    : {yaw_deg}°")

    # --- Build new joint list (deep-copy with renamed names + scaled offsets) ---
    new_joints: list[BvhJoint] = []
    name_remap: dict[str, str] = {}  # old name → new name
    matched = 0
    unmatched = []

    for jt in src.joints:
        new_jt = copy.deepcopy(jt)
        mapped = SOMA_TO_MIXAMO.get(jt.name.lower())
        if mapped:
            new_name = mapped.split(":")[-1] if strip_namespace else mapped
            matched += 1
        else:
            new_name = jt.name
            unmatched.append(jt.name)
        name_remap[jt.name] = new_name
        new_jt.name = new_name
        new_jt.offset = jt.offset * scale
        new_joints.append(new_jt)

    _log(f"Mapped joints : {matched}/{len(src.joints)}")
    if unmatched:
        _log(f"Unmapped (kept as-is): {unmatched}")

    # --- Build new frame array ---
    frames = src.frames.copy()

    # Find root joint (parent_idx == -1)
    root_idx = next((i for i, j in enumerate(src.joints) if j.parent_idx == -1), 0)
    root_jt = src.joints[root_idx]

    # Scale root position channels
    if scale != 1.0:
        for ch_offset, ch_name in enumerate(root_jt.channels):
            if ch_name.lower().endswith("position"):
                col = root_jt.channel_start + ch_offset
                frames[:, col] *= scale

    # Apply yaw rotation to root if requested
    if yaw_deg != 0.0:
        _apply_yaw_to_root(frames, root_jt, yaw_deg)

    result = BvhData(joints=new_joints, frames=frames, fps=src.fps)

    stats = {
        "matched": matched,
        "total": len(src.joints),
        "unmatched": unmatched,
        "frames": src.num_frames,
        "fps": src.fps,
    }
    return result, stats


# ---------------------------------------------------------------------------
# Yaw correction
# ---------------------------------------------------------------------------

def _rotation_channel_indices(jt: BvhJoint) -> tuple[list[int], str]:
    """Return (col_indices, euler_order) for the rotation channels of *jt*."""
    rot_cols = []
    order_chars = []
    for i, ch in enumerate(jt.channels):
        ch_lo = ch.lower()
        if ch_lo.endswith("rotation"):
            rot_cols.append(jt.channel_start + i)
            order_chars.append(ch_lo[0])  # 'x', 'y', or 'z'
    return rot_cols, "".join(order_chars)


def _apply_yaw_to_root(frames: np.ndarray, root_jt: BvhJoint, yaw_deg: float) -> None:
    """Rotate every frame's root orientation around world Y by *yaw_deg*."""
    cols, order = _rotation_channel_indices(root_jt)
    if not cols:
        return

    yaw_rot = R.from_euler("y", yaw_deg, degrees=True)

    for row in frames:
        angles = [row[c] for c in cols]
        local_rot = R.from_euler(order, angles, degrees=True)
        rotated = yaw_rot * local_rot
        new_angles = rotated.as_euler(order, degrees=True)
        for c, a in zip(cols, new_angles):
            row[c] = a

    # Also rotate root XZ translation if present
    pos_idx: dict[str, int] = {}
    for i, ch in enumerate(root_jt.channels):
        ch_lo = ch.lower()
        if ch_lo == "xposition":
            pos_idx["x"] = root_jt.channel_start + i
        elif ch_lo == "zposition":
            pos_idx["z"] = root_jt.channel_start + i

    if "x" in pos_idx and "z" in pos_idx:
        rad = math.radians(yaw_deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        cx, cz = pos_idx["x"], pos_idx["z"]
        x = frames[:, cx].copy()
        z = frames[:, cz].copy()
        frames[:, cx] = cos_a * x - sin_a * z
        frames[:, cz] = sin_a * x + cos_a * z

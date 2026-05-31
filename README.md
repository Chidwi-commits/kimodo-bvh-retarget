# kimodo-bvh-retarget

Converts Kimodo motion-capture animations (SOMA skeleton, BVH format) to
Mixamo joint naming so they can be applied directly to any Mixamo-rigged
character in Blender, Maya, MotionBuilder, or similar DCC tools.

---

## Purpose

[Kimodo](https://github.com/jtydhr88/ComfyUI-Kimodo) generates human
animation via the SOMA body model and exports it as BVH files.  Mixamo
characters use a different joint-naming convention (`mixamorig:Hips`,
`mixamorig:LeftArm`, etc.).  This tool bridges the gap by:

1. Parsing the Kimodo BVH hierarchy and motion data.
2. Renaming every SOMA joint to its Mixamo equivalent (60 bones, including
   full finger chains).
3. Optionally scaling root-position channels (e.g. metres → centimetres).
4. Optionally rotating the character around the Y axis (yaw offset).
5. Writing a new BVH that any Mixamo-aware importer can consume directly.

No FBX SDK is required — only **numpy** and **scipy**.

---

## How it works

```
Kimodo BVH  ──► bvh_reader  ──► retarget  ──► bvh_writer  ──► output BVH
(SOMA names)    (parse)         (rename +      (serialise)     (Mixamo names)
                                 scale/yaw)
```

### SOMA → Mixamo mapping highlights

| SOMA joint  | Mixamo joint             | Note                          |
|-------------|--------------------------|-------------------------------|
| `hips`      | `mixamorig:Hips`         | root                          |
| `spine1`    | `mixamorig:Spine`        |                               |
| `chest`     | `mixamorig:Spine2`       |                               |
| `leftleg`   | `mixamorig:LeftUpLeg`    | SOMA "leg" = upper leg/thigh  |
| `leftshin`  | `mixamorig:LeftLeg`      | SOMA "shin" = lower leg       |

Both skeletons share a standard T-pose with identity world rotations, so
local rotations transfer without any rest-pose correction.

---

## File architecture

```
kimodo-bvh-retarget/
├── bvh_reader.py      Parse a BVH file into BvhData / BvhJoint dataclasses.
│                      Handles arbitrary channel orders, End Site blocks,
│                      and UTF-8 files with BOM.
│
├── bvh_writer.py      Serialise a BvhData instance back to a valid BVH file.
│                      Reconstructs the HIERARCHY block recursively and writes
│                      all MOTION frames as space-separated floats.
│
├── retarget.py        Core retarget logic.
│                      • SOMA_TO_MIXAMO dict — single source of truth for the
│                        60-bone name mapping.
│                      • retarget() — renames joints, scales positions/offsets,
│                        applies optional yaw rotation to the root.
│                      • _apply_yaw_to_root() — rotates root Euler angles and
│                        XZ translation per-frame using scipy Rotation.
│
├── gui.py             Tkinter GUI (App class, tk.Tk subclass).
│                      File pickers, scale/yaw/strip-namespace controls,
│                      indeterminate progress bar, dark-background log widget.
│                      Runs the pipeline on a daemon thread so the UI stays
│                      responsive.
│
├── __main__.py        Entry point.
│                      • No CLI args → opens GUI.
│                      • With args → argparse CLI mode.
│                      Adds the package directory to sys.path so sibling
│                      modules resolve whether run as a script or with -m.
│
├── run.bat            One-click Windows launcher.
│                      Double-click to open the GUI without a terminal.
│                      If Python is not found the console window stays open.
│
└── requirements.txt   numpy>=1.24, scipy>=1.10
```

---

## Usage

### GUI

**Windows — one click:**
Double-click `run.bat`.

**Terminal:**
```bash
python3 __main__.py
```

### CLI

```bash
python3 __main__.py input.bvh output_mixamo.bvh [--scale 1.0] [--yaw 0] [--strip]
```

| Flag        | Default | Description                                         |
|-------------|---------|-----------------------------------------------------|
| `--scale`   | `1.0`   | Multiply root position and all offsets.             |
|             |         | Use `100` to convert metres → centimetres.          |
| `--yaw`     | `0`     | Rotate character around Y axis (degrees).           |
| `--strip`   | off     | Remove `mixamorig:` prefix from output joint names. |

---

## Blender workflow (after retarget)

1. **File → Import → FBX** — import the Mixamo character (mesh + armature).
2. **File → Import → BVH** — import the retargeted BVH.
3. Because joint names now match, use Blender's
   **Pose → Motion Paths** or **Action Constraints** to bind the animation
   to the Mixamo armature.  Auto-Rig Pro's "Remap" feature also detects
   names automatically.

---

## Dependencies

| Package | Minimum | Role                              |
|---------|---------|-----------------------------------|
| numpy   | 1.24    | array math for frame data         |
| scipy   | 1.10    | `Rotation` for yaw correction     |

> **Note on FBX SDK:** `fbxsdkpy` segfaults on Python 3.12 (ABI mismatch).
> BVH output is therefore the primary format.  FBX support can be added
> once an SDK compatible with Python 3.12+ is available.

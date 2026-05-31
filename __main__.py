"""Entry point: GUI if no arguments, CLI if arguments are given.

CLI usage:
    python -m kimodo_retarget  input.bvh  output.bvh  [--scale 1.0]  [--yaw 0]  [--strip]
    python  __main__.py        input.bvh  output.bvh  [--scale 1.0]  [--yaw 0]  [--strip]
"""

from __future__ import annotations

import argparse
import os
import sys


def _cli(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Retarget Kimodo/SOMA BVH animations to Mixamo joint names."
    )
    parser.add_argument("input",  help="Input BVH file (Kimodo/SOMA skeleton)")
    parser.add_argument("output", help="Output BVH file (Mixamo joint names)")
    parser.add_argument(
        "--scale", type=float, default=1.0,
        help="Scale factor for positions and offsets (default 1.0; use 100 for m→cm)",
    )
    parser.add_argument(
        "--yaw", type=float, default=0.0,
        help="Rotate root around Y axis by this many degrees (default 0)",
    )
    parser.add_argument(
        "--strip", action="store_true",
        help='Remove "mixamorig:" namespace prefix from joint names',
    )
    ns = parser.parse_args(args)

    from bvh_reader import read_bvh
    from bvh_writer import write_bvh
    from retarget import retarget as do_retarget

    print(f"Reading  {ns.input}")
    bvh = read_bvh(ns.input)
    print(f"  Joints : {len(bvh.joints)}")
    print(f"  Frames : {bvh.num_frames}  @  {bvh.fps:.2f} fps")

    print("Retargeting…")
    result, stats = do_retarget(
        bvh,
        scale=ns.scale,
        yaw_deg=ns.yaw,
        strip_namespace=ns.strip,
        log=print,
    )

    print(f"Writing  {ns.output}")
    write_bvh(result, ns.output)

    size_kb = os.path.getsize(ns.output) / 1024
    print(
        f"\nDone ✓  {stats['matched']}/{stats['total']} joints mapped"
        f"  →  {ns.output}  ({size_kb:.1f} KB)"
    )
    if stats["unmatched"]:
        print(f"Unmapped joints (kept as-is): {stats['unmatched']}")


def _gui() -> None:
    # Make sure our package directory is on the path when running as a script
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    from gui import App
    app = App()
    app.mainloop()


if __name__ == "__main__":
    # Add the directory containing this file to sys.path so sibling modules resolve
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    if len(sys.argv) > 1:
        _cli(sys.argv[1:])
    else:
        _gui()

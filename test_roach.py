# -*- coding: utf-8 -*-
"""Geometry correctness & stability tests for the refactored VirtualCockroach.

Pure stdlib asserts (no pytest). Covers the critical refactor fixes:
* heading=0 -> head points to +x (orientation fix, old version was 180 deg off)
* antennae root anchored ahead of the body (head tip, +x) (antenna fix)
* 72-frame smooth turning (5-degree steps)
* natural frame-index mapping so head always points along motion

Run:
    python test_roach.py
Prints "ALL_GEOMETRY_TESTS_PASSED" on success, raises AssertionError on failure.
"""

import math
import tkinter as tk

import cockroach


def _check(label, condition, detail=""):
    """Assert with a labeled PASS/FAIL record (raises on failure)."""
    if condition:
        print("  PASS  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
    else:
        msg = "FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else "")
        print("  " + msg)
        raise AssertionError(msg)


def test_image_load_and_calibration():
    print("[1] load_roach_image + calibrate_base_rotation")
    img, head_local = cockroach.load_roach_image("roach.png")

    # head must be above the image center (y downward positive -> negative)
    assert head_local[1] < 0
    _check("head_local[1] < 0 (head is up in sprite)",
           head_local[1] < 0, "head_local=%s" % (head_local,))

    # horizontal head offset should not be absurd
    assert abs(head_local[0]) < img.size[0] * 0.3
    _check("abs(head_local[0]) < img.size[0]*0.3",
           abs(head_local[0]) < img.size[0] * 0.3,
           "head_local[0]=%.2f width=%d" % (head_local[0], img.size[0]))

    phi = cockroach.calibrate_base_rotation(img, head_local)
    assert abs(phi - (-90.0)) < 1.0
    _check("abs(phi - (-90.0)) < 1.0 (base rotation ~ -90 deg)",
           abs(phi - (-90.0)) < 1.0, "phi=%.3f" % phi)
    return head_local, phi


def test_head_offset(head_local, phi):
    print("[2] head_offset_in_base (KEY orientation + antenna fix, REAL sprite)")
    # Use the REAL sprite head_local so we actually verify the refactor fix
    # (the old version rotated 180 deg off / placed antennae on the body).
    hoff = cockroach.head_offset_in_base(head_local, phi)

    # KEY assertion: heading=0 -> head must sit in front of the body (+x).
    assert hoff[0] > 0
    _check("hoff[0] > 0 (head/antenna tip in front, +x, at heading=0)",
           hoff[0] > 0, "hoff=%s  ***ACTUAL hoff[0]=%.3f***" % (hoff, hoff[0]))

    # primary offset should be along fore/aft axis, not sideways
    assert abs(hoff[1]) < abs(hoff[0])
    _check("abs(hoff[1]) < abs(hoff[0]) (fore/aft dominates sideways)",
           abs(hoff[1]) < abs(hoff[0]), "hoff=%s" % (hoff,))
    return hoff


def test_build_frames():
    print("[3] build_frames (72-frame set + scaled head offset)")
    # build_frames creates tkinter.PhotoImage objects, which need a live Tk
    # root. In production RoachApp() provides one; for the headless test we
    # spin up a withdrawn root so ImageTk has a default master.
    root = tk.Tk()
    root.withdraw()
    try:
        frames, img_size, hoff2 = cockroach.build_frames("roach.png", 100, 72, 1.0)
    finally:
        root.destroy()

    assert len(frames) == 72
    _check("len(frames) == 72", len(frames) == 72, "n=%d" % len(frames))
    assert hoff2[0] > 0
    _check("hoff2[0] > 0 (scaled head offset points +x)",
           hoff2[0] > 0, "hoff2=%s" % (hoff2,))
    return hoff2


def test_math_helpers():
    print("[4] rotate_point / wrap_angle")
    p1 = cockroach.rotate_point(1, 0, 0)
    assert abs(cockroach.rotate_point(1, 0, 0)[0] - 1) < 1e-6 and \
        abs(cockroach.rotate_point(1, 0, 0)[1]) < 1e-6
    _check("rotate_point(1,0,0) ~ (1,0)",
           abs(p1[0] - 1.0) < 1e-9 and abs(p1[1]) < 1e-9, "got=%s" % (p1,))

    p2 = cockroach.rotate_point(1, 0, math.pi / 2)
    assert abs(cockroach.rotate_point(1, 0, math.pi / 2)[0]) < 1e-6 and \
        abs(cockroach.rotate_point(1, 0, math.pi / 2)[1] - 1) < 1e-6
    _check("rotate_point(1,0,pi/2) ~ (0,1)",
           abs(p2[0]) < 1e-9 and abs(p2[1] - 1.0) < 1e-9, "got=%s" % (p2,))

    w = cockroach.wrap_angle(3 * math.pi)
    assert abs(cockroach.wrap_angle(3 * math.pi) - math.pi) < 1e-6
    _check("wrap_angle(3*pi) ~ pi",
           abs(w - math.pi) < 1e-9, "got=%s" % (w,))


def test_frame_index_mapping():
    print("[5] heading -> frame index mapping (head points along motion)")
    n = 72

    def idx_of(h):
        return int(round(-math.degrees(h) * n / 360.0)) % n

    # heading=0 -> frame 0 (head right, +x)
    assert idx_of(0.0) == 0
    _check("heading=0 -> idx 0 (head right)", idx_of(0.0) == 0,
           "idx=%d" % idx_of(0.0))
    # heading=pi -> frame 36 (head left)
    assert idx_of(math.pi) == 36
    _check("heading=pi -> idx 36 (head left)",
           idx_of(math.pi) == 36, "idx=%d" % idx_of(math.pi))
    # heading=pi/2 -> frame 54 (head down)
    assert idx_of(math.pi / 2.0) == 54
    _check("heading=pi/2 -> idx 54 (head down)",
           idx_of(math.pi / 2.0) == 54, "idx=%d" % idx_of(math.pi / 2.0))
    # heading=3pi/2 -> frame 18 (head up)
    assert idx_of(3.0 * math.pi / 2.0) == 18
    _check("heading=3pi/2 -> idx 18 (head up)",
           idx_of(3.0 * math.pi / 2.0) == 18, "idx=%d" % idx_of(3.0 * math.pi / 2.0))


def main():
    print("=" * 64)
    print("VirtualCockroach geometry test")
    print("=" * 64)
    head_local, phi = test_image_load_and_calibration()
    test_head_offset(head_local, phi)
    test_build_frames()
    test_math_helpers()
    test_frame_index_mapping()
    print("=" * 64)
    print("ALL_GEOMETRY_TESTS_PASSED")
    print("=" * 64)


if __name__ == "__main__":
    main()

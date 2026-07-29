# -*- coding: utf-8 -*-
"""Geometry & species correctness tests for VirtualCockroach (dog + roach).

Pure stdlib asserts (no pytest). Validates that BOTH species -- and every dog
pose -- satisfy the critical orientation invariant (heading=0 -> head points
to +x, i.e. ``head_offset_in_base`` returns hoff_x > 0), that the 72-frame set
is built correctly, and that the shared heading -> frame-index mapping points
the head along the direction of motion in all four cardinal directions.

Run:
    python test_pet.py
Prints "ALL_PET_TESTS_PASSED" on success, raises AssertionError on failure.
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


def _idx_of(h, n=72):
    """Mirror of Pet._choose_frame's heading -> index mapping."""
    return int(round(-math.degrees(h) * n / 360.0)) % n


def test_dog_poses():
    print("[1] every dog pose: sprite load + calibrate + head up")
    root = tk.Tk()
    root.withdraw()
    try:
        for state in cockroach.DOG_STATES:
            img = cockroach.get_dog_sprite(state)
            assert img.mode == "RGBA"
            _check("dog[%s] sprite is RGBA" % state, img.mode == "RGBA")

            limg, head_local = cockroach.load_roach_image(img)
            assert head_local[1] < 0, "head must be above center"
            _check("dog[%s] head_local[1] < 0 (head up)" % state,
                   head_local[1] < 0, "head_local=%s" % (head_local,))
            assert abs(head_local[0]) < img.size[0] * 0.3
            _check("dog[%s] abs(head_local[0]) < w*0.3" % state,
                   abs(head_local[0]) < img.size[0] * 0.3,
                   "head_local[0]=%.2f" % head_local[0])

            phi = cockroach.calibrate_base_rotation(limg, head_local)
            # The line dog is drawn as a SIDE PROFILE (intentionally asymmetric:
            # legs/feet live on the right, ear/back on the left), so the discrete
            # calibration may land on -92.5 or -95 instead of exactly -90.0 (a
            # few-deg rounding artifact driven by the head being slightly off the
            # vertical axis).  What matters is the head ends up pointing +x
            # (verified robustly by hoff[0] > 0 below).  Allow up to 7 deg.
            assert abs(phi - (-90.0)) < 7.0
            _check("dog[%s] abs(phi+90) < 7.0" % state,
                   abs(phi - (-90.0)) < 7.0, "phi=%.3f" % phi)

            hoff = cockroach.head_offset_in_base(head_local, phi)
            # KEY assertion for every pose: heading=0 -> head in front (+x).
            assert hoff[0] > 0, "head must point forward at heading=0"
            _check("dog[%s] hoff[0] > 0 (head forward)" % state,
                   hoff[0] > 0,
                   "***ACTUAL hoff[0]=%.3f***" % hoff[0])
            assert abs(hoff[1]) < abs(hoff[0])
            _check("dog[%s] fore/aft dominates sideways" % state,
                   abs(hoff[1]) < abs(hoff[0]), "hoff=%s" % (hoff,))
    finally:
        root.destroy()


def test_roach_head_offset():
    print("[2] roach head_offset_in_base (hoff_x > 0, REAL sprite)")
    img, head_local = cockroach.load_roach_image("roach.png")
    assert head_local[1] < 0
    _check("roach head_local[1] < 0 (head is up in sprite)",
           head_local[1] < 0, "head_local=%s" % (head_local,))

    phi = cockroach.calibrate_base_rotation(img, head_local)
    assert abs(phi - (-90.0)) < 1.0
    _check("roach abs(phi+90) < 1.0 (base rotation ~ -90 deg)",
           abs(phi - (-90.0)) < 1.0, "phi=%.3f" % phi)

    hoff = cockroach.head_offset_in_base(head_local, phi)
    assert hoff[0] > 0
    _check("roach hoff[0] > 0 (head/antenna tip in front, +x)",
           hoff[0] > 0, "hoff=%s" % (hoff,))
    assert abs(hoff[1]) < abs(hoff[0])
    _check("roach abs(hoff[1]) < abs(hoff[0]) (fore/aft dominates)",
           abs(hoff[1]) < abs(hoff[0]), "hoff=%s" % (hoff,))


def test_build_frames_both():
    print("[3] build_frames (72-frame set + scaled head offset)")
    root = tk.Tk()
    root.withdraw()
    try:
        for state in cockroach.DOG_STATES:
            frames, size, hoff = cockroach.build_frames(
                cockroach.get_dog_sprite(state),
                cockroach.DOG_TARGET_HEIGHT, 72, 1.0)
            assert len(frames) == 72
            _check("dog[%s] len(frames) == 72" % state,
                   len(frames) == 72, "n=%d" % len(frames))
            assert hoff[0] > 0
            _check("dog[%s] hoff[0] > 0 (scaled head offset +x)" % state,
                   hoff[0] > 0, "hoff=%s" % (hoff,))

        roach_frames, roach_size, roach_hoff = cockroach.build_frames(
            "roach.png", 100, 72, 1.0)
        assert len(roach_frames) == 72
        _check("roach len(frames) == 72",
               len(roach_frames) == 72, "n=%d" % len(roach_frames))
        assert roach_hoff[0] > 0
        _check("roach hoff[0] > 0 (scaled head offset +x)",
               roach_hoff[0] > 0, "hoff=%s" % (roach_hoff,))
    finally:
        root.destroy()


def test_math_helpers():
    print("[4] rotate_point / wrap_angle")
    p1 = cockroach.rotate_point(1, 0, 0)
    _check("rotate_point(1,0,0) ~ (1,0)",
           abs(p1[0] - 1.0) < 1e-9 and abs(p1[1]) < 1e-9, "got=%s" % (p1,))
    p2 = cockroach.rotate_point(1, 0, math.pi / 2)
    _check("rotate_point(1,0,pi/2) ~ (0,1)",
           abs(p2[0]) < 1e-9 and abs(p2[1] - 1.0) < 1e-9, "got=%s" % (p2,))
    w = cockroach.wrap_angle(3 * math.pi)
    _check("wrap_angle(3*pi) ~ pi", abs(w - math.pi) < 1e-9, "got=%s" % (w,))


def test_frame_index_mapping():
    print("[5] heading -> frame index mapping (head points along motion)")
    n = 72
    assert _idx_of(0.0, n) == 0
    _check("heading=0 -> idx 0 (head right)", _idx_of(0.0, n) == 0,
           "idx=%d" % _idx_of(0.0, n))
    assert _idx_of(math.pi, n) == 36
    _check("heading=pi -> idx 36 (head left)", _idx_of(math.pi, n) == 36,
           "idx=%d" % _idx_of(math.pi, n))
    assert _idx_of(math.pi / 2.0, n) == 54
    _check("heading=pi/2 -> idx 54 (head down)", _idx_of(math.pi / 2.0, n) == 54,
           "idx=%d" % _idx_of(math.pi / 2.0, n))
    assert _idx_of(3.0 * math.pi / 2.0, n) == 18
    _check("heading=3pi/2 -> idx 18 (head up)",
           _idx_of(3.0 * math.pi / 2.0, n) == 18,
           "idx=%d" % _idx_of(3.0 * math.pi / 2.0, n))


def test_get_global_mouse_signature():
    print("[6] get_global_mouse returns a 2-tuple of ints (cross-platform)")
    mx, my = cockroach.get_global_mouse()
    _check("get_global_mouse() -> (int, int)",
           isinstance(mx, int) and isinstance(my, int),
           "(%r, %r)" % (mx, my))


def main():
    print("=" * 64)
    print("VirtualCockroach pet test (dog poses + roach)")
    print("=" * 64)
    test_dog_poses()
    test_roach_head_offset()
    test_build_frames_both()
    test_math_helpers()
    test_frame_index_mapping()
    test_get_global_mouse_signature()
    print("=" * 64)
    print("ALL_PET_TESTS_PASSED")
    print("=" * 64)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""Behavior verification for the line-art dog (multi-pose) + burst.

In-process (no GUI window): builds a dog pet on a withdrawn Tk canvas
and asserts:
  * the dog eventually CHASES a moving cursor,
  * the dog NEVER flees (flee is a roach-only behavior),
  * clicking the dog invokes on_burst (-> roaches appear),
  * a roach still flees from a close cursor (original logic intact).

Run:  python qa_dog_check.py
Prints "QA_DOG_OK" on success.
"""

import math
import random
import tkinter as tk

import cockroach as c


def _build_framesets():
    dog_img = c.get_dog_sprite("walk")
    _, hl = c.load_roach_image(dog_img)
    dog_base = c.calibrate_base_rotation(dog_img, hl)
    dog_sets = {
        st: c.build_frames(c.get_dog_sprite(st), c.DOG_TARGET_HEIGHT,
                         c.N_FRAMES, 1.0, dog_base)
        for st in c.DOG_STATES
    }
    roach_frames, rs, rh = c.build_frames(
        "roach.png", c.TARGET_HEIGHT, c.N_FRAMES, 1.0)
    return {"dog": dog_sets, "roach": (roach_frames, rs, rh)}


def main():
    # Seed the RNG so the pose state machine is fully deterministic.  The
    # chase branch is probabilistic (needs timer expiry + rand()<0.55 while
    # awake), so an unseeded run could occasionally skip chase within the
    # window.  A fixed seed makes the QA run repeatable and flake-free.
    random.seed(20240722)

    root = tk.Tk()
    root.withdraw()
    cv = tk.Canvas(root)
    cv.pack()

    fs = _build_framesets()
    W, H = 1920, 1080

    kill = {"n": 0}
    pet = c.Pet(cv, fs, W, H, on_kill=lambda: kill.__setitem__("n", 1),
              species="dog", init_x=W / 2.0, init_y=H / 2.0)

    # 1) Dog chases a moving cursor and never flees.
    chases = 0
    ever_flee = False
    poses_seen = set()
    MOVE_TICKS = 3000      # ~48s of a moving cursor -> reliably enters chase
    STILL_TICKS = 1200     # ~19s parked -> settles into calm poses
    for i in range(MOVE_TICKS + STILL_TICKS):
        if i < MOVE_TICKS:
            # Cursor orbits the dog's start; a larger, faster orbit keeps the
            # per-tick movement well above the chase threshold (>3px) so the
            # only gate is the (now deterministic) pose timer + rand() roll.
            mx = W / 2.0 + 320.0 * math.cos(i * 0.10)
            my = H / 2.0 + 320.0 * math.sin(i * 0.10)
        else:
            mx, my = W / 2.0, H / 2.0
        pet.update(0.016, mx, my)
        poses_seen.add(pet.dog_state)
        if pet.dog_state == "chase":
            chases += 1
        if pet.state == "flee":
            ever_flee = True

    assert chases > 0, "dog never entered chase while cursor moved"
    assert not ever_flee, "BUG: dog fled (flee must be roach-only)"
    # Expect several distinct poses over time (not just one).
    assert len(poses_seen) >= 3, "dog did not cycle through poses: %s" % poses_seen
    print("  PASS  dog chases moving cursor (chase ticks=%d, poses=%s)"
          % (chases, sorted(poses_seen)))
    print("  PASS  dog never flees (roach-only behavior preserved)")

    # 2) Clicking the dog bursts the roaches (on_burst invoked).
    burst = {"n": 0}
    pet2 = c.Pet(cv, fs, W, H, on_kill=lambda: None,
               species="dog", init_x=100.0, init_y=100.0,
               on_burst=lambda x, y, p: burst.__setitem__("n", burst["n"] + 1))
    pet2._on_click(None)
    assert burst["n"] == 1, "clicking dog did not call on_burst"
    print("  PASS  click dog -> on_burst invoked (-> 5 roaches)")

    # 3) A roach still flees from a close cursor (original logic intact).
    r = c.Pet(cv, fs, W, H, on_kill=lambda: None,
             species="roach", init_x=W / 2.0, init_y=H / 2.0)
    roach_fled = False
    for i in range(120):
        # cursor parked right on top of the roach
        r.update(0.016, W / 2.0 + 2.0, H / 2.0 + 2.0)
        if r.state == "flee":
            roach_fled = True
            break
    assert roach_fled, "roach no longer flees from close cursor"
    print("  PASS  roach still flees from a close cursor (logic intact)")

    root.destroy()
    print("=" * 64)
    print("QA_DOG_OK")
    print("=" * 64)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""In-process behavior verification for VirtualCockroach burst logic.

Avoids popping a real GUI by neutralizing Tk.mainloop; uses a real (withdrawn)
Tk root so PIL ImageTk still works. Constructs RoachApp, then verifies:
  1. starts with exactly ONE dog, target_speed ~= DOG_WALK_SPEED (26)
  2. dog ignores the cursor over many ticks (never enters flee / hidden)
  3. clicking the dog bursts 5 roaches in a radial distribution with the
     classic SIZE_SCALES sizes, each with original roach logic
  4. a roach flees when the cursor comes near

Run:
    python qa_behavior_check.py
Prints "QA_BEHAVIOR_CHECK_PASSED" on success.
"""
import math
import tkinter as tk

# Neutralize the blocking mainloop so __init__ returns and we can inspect state.
_orig_mainloop = tk.Tk.mainloop
tk.Tk.mainloop = lambda self, *a, **k: None

import cockroach

results = []


def check(label, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print("  %s  %s%s" % (status, label, ("  [%s]" % detail) if detail else ""))
    results.append((label, cond, detail))
    return cond


app = cockroach.RoachApp()

# --- 1. single slow dog ----------------------------------------------------
n = len(app.pets)
check("starts with exactly 1 pet", n == 1, "n=%d" % n)
dog = app.pets[0]
check("the pet is a dog", dog.species == "dog", "species=%s" % dog.species)
check("dog target_speed == DOG_WALK_SPEED (26)",
      abs(dog.target_speed - cockroach.DOG_WALK_SPEED) < 1e-6,
      "target_speed=%.3f (DOG_WALK_SPEED=%.1f)" %
      (dog.target_speed, cockroach.DOG_WALK_SPEED))
check("dog frame height ~ TARGET_HEIGHT (scale 1.0)",
      abs(dog.img_h - cockroach.TARGET_HEIGHT) < 1.0,
      "img_h=%.2f target=%d" % (dog.img_h, cockroach.TARGET_HEIGHT))

# --- 2. dog ignores cursor over many ticks --------------------------------
# Mouse parked 5px from the dog for 300 ticks (~15s sim time).
fled = False
start_state = dog.state
for _ in range(300):
    dog.update(0.05, dog.x + 4.0, dog.y + 3.0)
    if dog.state == "flee" or dog.state == "hidden":
        fled = True
        break
check("dog never flees with cursor in its face", not fled,
      "final state=%s" % dog.state)
check("dog still a dog after cursor proximity", dog.species == "dog")

# --- 3. click dog -> burst of 5 roaches -----------------------------------
cx, cy = dog.x, dog.y
dog.on_burst(cx, cy, dog)   # equivalent to app._burst_roaches_at(cx, cy, dog)
roaches = [p for p in app.pets if p.species == "roach"]
check("burst produced exactly 5 roaches", len(roaches) == 5,
      "count=%d" % len(roaches))
check("original dog removed from pet list", dog not in app.pets)

# classic SIZE_SCALES sizes reflected in frame heights
expected_scales = cockroach.SIZE_SCALES[:5]
heights = sorted(round(r.img_h) for r in roaches)
exp_heights = sorted(round(cockroach.TARGET_HEIGHT * s) for s in expected_scales)
check("roach heights match classic SIZE_SCALES", heights == exp_heights,
      "heights=%s expected=%s" % (heights, exp_heights))

# radial distribution: small offset from center + outward (radial) heading
radial_ok = True
worst = 0.0
for r in roaches:
    offx, offy = r.x - cx, r.y - cy
    off_dist = math.hypot(offx, offy)
    if not (6.0 <= off_dist <= 23.0):
        radial_ok = False
    pos_ang = math.atan2(offy, offx)
    err = abs(cockroach.wrap_angle(r.heading - pos_ang))
    worst = max(worst, err)
    if err > 0.3:
        radial_ok = False
check("roaches on small radial offset with outward headings", radial_ok,
      "worst_heading_err=%.3f" % worst)

# --- 4. roach flees near cursor -------------------------------------------
r0 = roaches[0]
r0.state = "walk"   # start from a non-flee walk state
r0.update(0.05, r0.x + 2.0, r0.y + 2.0)   # cursor ~2.8px away -> panic
check("roach enters flee when cursor is close", r0.state == "flee",
      "state=%s" % r0.state)

# --- cleanup --------------------------------------------------------------
try:
    app.root.destroy()
except Exception:
    pass
tk.Tk.mainloop = _orig_mainloop

failed = [r for r in results if not r[1]]
print("=" * 64)
if not failed:
    print("QA_BEHAVIOR_CHECK_PASSED  (%d assertions, all PASS)" % len(results))
else:
    print("QA_BEHAVIOR_CHECK_FAILED  (%d of %d failed)" %
          (len(failed), len(results)))
    for label, _, detail in failed:
        print("  FAIL  %s  %s" % (label, detail))
print("=" * 64)

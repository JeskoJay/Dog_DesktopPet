# -*- coding: utf-8 -*-
"""High-res ASCII verification of the rotated (in-game) dog face.

Replicates build_frames' transform (rotate(-90, expand=True)) at 3x scale, then
dumps a tight crop of the HEAD/face so we can confirm eyes + nose + w mouth.
"""
import sys
from PIL import Image

sys.path.insert(0, "C:/Users/SXF-Admin/WorkBuddy/2026-07-22-15-22-35")
import cockroach as C

SCALE = 3


def to_ascii(img, cols=100, rows=50, threshold=40):
    w, h = img.size
    px = img.load()
    out = []
    for r in range(rows):
        line = []
        for c in range(cols):
            sx = int((c + 0.5) / cols * w)
            sy = int((r + 0.5) / rows * h)
            a = px[sx, sy][3]
            if a < threshold:
                line.append(" ")
                continue
            lum = sum(px[sx, sy][:3]) / 3.0
            if lum < 90:
                line.append("#")      # dark detail
            elif lum < 230:
                line.append("O")      # outline
            else:
                line.append(".")      # white fill
        out.append("".join(line))
    return "\n".join(out)


def main():
    state = sys.argv[1] if len(sys.argv) > 1 else "walk"
    dog = C.draw_dog_state(state)
    # upscale for crisp ASCII
    dog = dog.resize((dog.width * SCALE, dog.height * SCALE), Image.LANCZOS)
    rot = dog.rotate(C.BASE_ROTATION_DEG, expand=True, resample=Image.BICUBIC)
    w, h = rot.size
    # head sits in the RIGHT portion after rotation
    head = rot.crop((int(w * 0.55), 0, w, h))
    hw, hh = head.size
    print("rotated size:", rot.size, " head crop:", head.size)
    # tight bbox of the head crop, then trim top/bottom empty
    bb = head.getbbox()
    if bb:
        head = head.crop(bb)
    print("=== HEAD (in-game; ears up-ish, face below) ===")
    print(to_ascii(head, cols=90, rows=54))

    # focus face: middle band where eyes/nose/mouth live
    fw, fh = head.size
    face = head.crop((0, int(fh * 0.20), fw, int(fh * 0.72)))
    print("\n=== FACE ZOOM ===")
    print(to_ascii(face, cols=90, rows=48))


if __name__ == "__main__":
    main()

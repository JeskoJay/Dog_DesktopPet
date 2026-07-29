# -*- coding: utf-8 -*-
"""Render every dog pose side by side for visual review.

Row 1: in-game size (sprite cropped to bbox, scaled to DOG_TARGET_HEIGHT).
Row 2: 2x zoom of the same, for detail inspection.
Saves dog_preview.png next to this script.
"""

import cockroach
from PIL import Image, ImageDraw

POSES = list(cockroach.DOG_STATES)
BG = (125, 125, 125)
LABEL = (255, 255, 0)


def _disp(sprite, target_h):
    bbox = sprite.getbbox()
    crop = sprite.crop(bbox)
    w, h = crop.size
    s = target_h / h
    return crop.resize((max(1, int(round(w * s))), target_h), Image.LANCZOS)


def main():
    row1 = [(st, _disp(cockroach.get_dog_sprite(st), 160)) for st in POSES]
    row2 = [(st, _disp(cockroach.get_dog_sprite(st), 320)) for st in POSES]

    pad = 26
    label_h = 22
    w1 = sum(im.width for _, im in row1) + pad * (len(row1) + 1)
    w2 = sum(im.width for _, im in row2) + pad * (len(row2) + 1)
    W = max(w1, w2)
    H = pad + 160 + label_h + pad + 320 + label_h + pad

    out = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(out)

    x = pad
    for st, im in row1:
        out.paste(im, (x, pad), im)
        d.text((x + 4, pad + 160 + 4), st, fill=LABEL)
        x += im.width + pad

    y2 = pad + 160 + label_h + pad
    x = pad
    for st, im in row2:
        out.paste(im, (x, y2), im)
        d.text((x + 4, y2 + 320 + 4), st, fill=LABEL)
        x += im.width + pad

    out.save("dog_preview.png")
    print("saved dog_preview.png", out.size)


if __name__ == "__main__":
    main()

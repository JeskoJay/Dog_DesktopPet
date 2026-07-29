# -*- coding: utf-8 -*-
"""Dump each dog pose as ASCII silhouette so the shape can be inspected
without viewing the PNG (this environment can't render images to me).

'#' = opaque silhouette, ' ' = transparent.  Aspect ratio is preserved.
"""

import cockroach


def ascii_pose(st, cols=30):
    img = cockroach.get_dog_sprite(st).convert("L")
    bbox = img.getbbox()
    img = img.crop(bbox)
    w, h = img.size
    rows = max(8, int(round(cols * h / w * 0.5)))  # 0.5 ~ char aspect
    out = []
    px = img.load()
    for ry in range(rows):
        line = []
        for rx in range(cols):
            x0 = int(rx * w / cols)
            x1 = max(x0 + 1, int((rx + 1) * w / cols))
            y0 = int(ry * h / rows)
            y1 = max(y0 + 1, int((ry + 1) * h / rows))
            on = False
            for yy in range(y0, y1):
                for xx in range(x0, x1):
                    if px[xx, yy] > 40:
                        on = True
                        break
                if on:
                    break
            line.append('#' if on else ' ')
        out.append(''.join(line))
    return out


def main():
    for st in cockroach.DOG_STATES:
        print("=== %s ===" % st)
        for line in ascii_pose(st):
            print(line)
        print()


if __name__ == "__main__":
    main()

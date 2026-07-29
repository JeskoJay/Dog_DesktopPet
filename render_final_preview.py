# -*- coding: utf-8 -*-
"""Contact sheet of the 6 line-dog poses in their IN-GAME orientation
(nose pointing right, legs down) so the result can be eyeballed in a PNG
viewer.  Built from the same draw_dog_state used by the app.
"""
import cockroach as C
from PIL import Image, ImageDraw

PAD = 24
CELL_W, CELL_H = 360, 300
TARGET_H = 170
COLS, ROWS = 3, 2
BG = (238, 238, 242, 255)

states = list(C.DOG_STATES)  # walk, sit, sleep, chase, stretch, look
sheet = Image.new("RGBA", (COLS * CELL_W, ROWS * CELL_H), BG)
sd = ImageDraw.Draw(sheet)


def rotated_pose(st):
    img = C.get_dog_sprite(st).convert("RGBA")
    rot = img.rotate(-90, expand=True, resample=C.Image.BICUBIC)
    bbox = rot.getbbox()
    rot = rot.crop(bbox)
    # scale to TARGET_H preserving aspect
    w, h = rot.size
    sc = TARGET_H / float(h)
    rot = rot.resize((max(1, int(w * sc)), TARGET_H), C.Image.LANCZOS)
    return rot


for idx, st in enumerate(states):
    r, c = divmod(idx, COLS)
    cx = c * CELL_W
    cy = r * CELL_H
    pose = rotated_pose(st)
    pw, ph = pose.size
    ox = cx + (CELL_W - pw) // 2
    oy = cy + (CELL_H - ph) // 2 - 10
    sheet.alpha_composite(pose, (ox, oy))
    sd.text((cx + PAD, cy + CELL_H - 34), st.upper(),
            fill=(40, 40, 48, 255), font=None)

out = "dog_preview.png"
sheet.convert("RGB").save(out)
print("wrote", out, sheet.size)

"""Probe how PIL rotate(-90, expand=True) maps the four edges of a sprite.

The pet pipeline draws the dog 'head up', then build_frames rotates it -90 so
the head points to +x (forward).  We need to know exactly where each edge
lands AFTER that rotation so we can orient the side-profile dog correctly:
  - nose must end up FORWARD (game +x, i.e. screen RIGHT)
  - legs must end up DOWN (screen +y)
  - spine must end up UP (screen -y)
  - tail must end up BACKWARD (game -x, screen LEFT)
"""
from PIL import Image

W = H = 200
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = img.load()

# top marker (head/nose) - red
for x in range(90, 110):
    for y in range(5, 25):
        d[x, y] = (255, 0, 0, 255)
# right marker (green)
for x in range(175, 195):
    for y in range(90, 110):
        d[x, y] = (0, 255, 0, 255)
# bottom marker (tail) - blue
for x in range(90, 110):
    for y in range(175, 195):
        d[x, y] = (0, 0, 255, 255)
# left marker (spine) - yellow
for x in range(5, 25):
    for y in range(90, 110):
        d[x, y] = (255, 255, 0, 255)

rot = img.rotate(-90, expand=True, resample=Image.BICUBIC)
rw, rh = rot.size
rp = rot.load()


def centroid(color):
    sx = sy = n = 0
    for y in range(rh):
        for x in range(rw):
            if rp[x, y][:3] == color:
                sx += x
                sy += y
                n += 1
    return (sx / n, sy / n) if n else None


print("rotated size:", rot.size)
# Convert to directional hint relative to rotated center
cxc, cyc = rw / 2.0, rh / 2.0


def where(name, color):
    c = centroid(color)
    if not c:
        print(name, "MISSING")
        return
    dx, dy = c[0] - cxc, c[1] - cyc
    hint = []
    if dx > 10:
        hint.append("RIGHT/+x")
    elif dx < -10:
        hint.append("LEFT/-x")
    if dy > 10:
        hint.append("DOWN/+y")
    elif dy < -10:
        hint.append("UP/-y")
    print(f"{name:6s} -> ({dx:6.1f}, {dy:6.1f})  => {', '.join(hint) or 'center'}")


where("TOP", (255, 0, 0))
where("RIGHT", (0, 255, 0))
where("BOTTOM", (0, 0, 255))
where("LEFT", (255, 255, 0))

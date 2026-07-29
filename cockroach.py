# -*- coding: utf-8 -*-
"""VirtualCockroach v7 - Cross-platform desktop pet (dog + roach).

A borderless transparent fullscreen tkinter app that runs in the background.
A small population of pets roams the desktop, avoids the cursor with
flee/panic behavior, hides off-screen and crawls back, and can be dismissed
by clicking any pet or pressing the global hotkey.

Species:
* dog  : default pet, drawn procedurally with PIL (no image asset). Head points
         "up" in the sprite; ears and tail are animated overlays.
* roach: the classic cockroach loaded from roach.png; antennae are animated
         overlays (original behavior preserved unchanged).

Click behavior (burst):
* The app starts with exactly one slow dog that ignores the mouse entirely.
* click the dog  -> it is removed and bursts into the classic 5 roaches
  (radiating outward from the dog's position) which keep full roach behavior.
* click a roach -> the program exits (on_kill).
* global hotkey (Ctrl+Shift+Q on Windows/Linux, Cmd+Shift+Q on macOS) exits.

Cross-platform notes:
* Mouse position is read with pynput (no Windows-only ctypes / user32).
* The exit hotkey is registered with pynput.keyboard.GlobalHotKeys in a
  background thread. On macOS the global hotkey requires "Accessibility"
  permission; if it is not granted the click-to-exit still works.

Key geometry fixes (unchanged from v6):
* Heading/frame alignment is corrected so the head always points in the
  direction of motion (heading=0 -> head points to +x).
* Antennae/ears/tail are anchored at the actual head tip / rear and drawn
  above the body. ``head_offset_in_base`` returns hoff_x > 0 for both species.
* Frame count is 72 (5 degree steps) for smooth turning.
* Movement uses smooth heading interpolation, continuous wander drift, and
  smooth boundary avoidance.
"""

import math
import os
import random
import sys
import threading
import time
import tkinter as tk
from typing import Dict, List, Optional, Tuple, Union

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageTk

# pynput provides cross-platform global input access (mouse position + hotkey).
from pynput import mouse as _pynput_mouse
from pynput.keyboard import GlobalHotKeys

# A single global controller is enough for reading the cursor position.
_MOUSE = _pynput_mouse.Controller()

# ---------------------------------------------------------------------------
# Top-level configuration
# ---------------------------------------------------------------------------
BG_COLOR = "#010101"
N_ROACHES = 5
TICK_MS = 16
N_FRAMES = 72
TARGET_HEIGHT = 100

# --- Roach / antennae appearance -------------------------------------------
ANTENNA_COLOR = "#2a1408"
ANTENNA_WIDTH = 2.5
ANTENNA_SEGMENTS = 6
ANTENNA_LENGTH_RATIO = 1.45

# --- Dog appearance (colored cartoon corgi) -------------------------------
# The dog is now a cheerful side-profile corgi: tan coat, cream muzzle/chest/
# belly/inner ears, big upright ears, large dark eyes, a big brown nose, pink
# tongue and a yellow collar.  Exterior parts are built as silhouette masks
# (tan fill + bold dark outline); interior cream patches are filled without an
# outline so they blend softly into the tan coat.
LINE_DOG_COLOR = "#333333"
LINE_DOG_FILL = "#ffffff"
LINE_DOG_W = 4
LINE_DOG_HALO = "#ffffff"
LINE_DOG_HALO_W = 2
DOG_NOSE = "#2d231e"          # nose / closed-eye dot
TAIL_SEGMENTS = 6
# Corgi palette
_CORGI_TAN = (232, 162, 82, 255)
_CORGI_CREAM = (255, 247, 224, 255)
_CORGI_NOSE = (92, 56, 40, 255)
_CORGI_EYE = (42, 42, 42, 255)
_CORGI_TONGUE = (255, 126, 148, 255)
_CORGI_COLLAR = (255, 214, 58, 255)

# On-screen body height of the dog (noticeably larger than the roach's 100).
DOG_TARGET_HEIGHT = 160

# Visual poses.  Each pose gets its own pre-rotated frame set; every pose is
# drawn head-up so head_offset_in_base yields hoff_x > 0 for all of them.
DOG_STATES = ("walk", "sit", "sleep", "chase", "stretch", "look")
# Poses during which the dog stays put (used to pick target speed = 0).
DOG_STILL_POSES = ("sit", "sleep")

# Size distribution: shuffled per run so the population is always mixed.
SIZE_SCALES = [1.0, 0.85, 0.7, 0.55, 0.9]

# Mouse evasion parameters (pixels / seconds).
ALERT_RADIUS = 200.0
PANIC_RADIUS = 90.0
FLEE_SPEED = 280.0
PANIC_SPEED = 420.0
NORMAL_SPEED = (90.0, 160.0)

# Dog walking speed: a perky stroll. The dog IGNORES the mouse for evasion
# (it never flees) but WILL happily chase the cursor when it moves.
DOG_WALK_SPEED = 58.0
DOG_CHASE_SPEED = 155.0
# How long each behavioral pose tends to last before switching (kept short
# so the dog is visibly lively and cycles poses often).
DOG_POSE_TIME = (0.6, 1.5)
DOG_SLEEP_TIME = (1.2, 2.6)
DOG_CHASE_TIME = (0.8, 1.8)
HIDE_TIME = (0.8, 2.5)
IDLE_TIME = (3.0, 8.0)
PAUSE_TIME = (0.3, 1.5)
WALK_TIME = (1.5, 4.5)

# Rotation that aligns the original "head up" sprite with "head points to +x".
# Verified by a temporary marker experiment (see calibrate_base_rotation()).
BASE_ROTATION_DEG = -90.0

# Heading smoothing (radians per second interpolation factor).  Higher = the
# dog snaps toward its target heading faster, so chasing the cursor feels
# lively and responsive.
TURN_RATE = 9.0
TURN_RATE_FLEE = 8.0

# Wander / natural curved movement.
WANDER_AMPS = (0.25, 0.20, 0.15)
WANDER_FREQS = (0.12, 0.23, 0.41)

# Boundary avoidance: start turning when within 12% of screen width/height.
EDGE_MARGIN_RATIO = 0.12
EDGE_STRENGTH = 2.5

# Body bob (perpendicular to heading, amplitude grows with speed).
BOB_FREQ = 14.0
BOB_AMP_SPEED_RATIO = 0.015
MAX_BOB_AMP = 2.5

# Type alias for a per-species pre-built frame set.
FrameSet = Tuple[List[ImageTk.PhotoImage], Tuple[int, int], Tuple[float, float]]


# ---------------------------------------------------------------------------
# Resource & OS helpers
# ---------------------------------------------------------------------------

def resource_path(name: str) -> str:
    """Return the path to a bundled or sibling resource file."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def get_global_mouse() -> Tuple[int, int]:
    """Return the global cursor position using pynput (cross-platform).

    pynput reports the cursor in screen coordinates with the origin at the
    top-left corner, which matches tkinter's coordinate system on both
    Windows and macOS, so no axis flipping is required.
    """
    return tuple(int(v) for v in _MOUSE.position)


# ---------------------------------------------------------------------------
# Pure geometry / calibration helpers (no tkinter dependency)
# ---------------------------------------------------------------------------

def _row_opacity_stats(img: Image.Image) -> List[Tuple[int, int, int]]:
    """Return per-row (opaque_count, min_x, max_x) for the image.

    A pixel is considered opaque when its alpha value is greater than 10.
    """
    width, height = img.size
    pixels = img.load()
    rows = []
    for y in range(height):
        count = 0
        min_x = width
        max_x = -1
        for x in range(width):
            if pixels[x, y][3] > 10:
                count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
        rows.append((count, min_x, max_x))
    return rows


def _symmetry_axis(rows: List[Tuple[int, int, int]]) -> float:
    """Estimate the vertical symmetry axis of the sprite.

    Uses the median horizontal center of rows that contain more than a few
    opaque pixels. This is more stable than the top row alone, which can be
    biased by one antenna.
    """
    centers = [(cmin + cmax) / 2.0 for count, cmin, cmax in rows if count > 5]
    if not centers:
        # Fallback: use the image center if the sprite is almost empty.
        return 0.0
    centers.sort()
    return centers[len(centers) // 2]


def load_roach_image(source: Union[str, Image.Image]
                     ) -> Tuple[Image.Image, Tuple[float, float]]:
    """Load a sprite and compute the head tip in local coordinates.

    Args:
        source: Either a path to a PNG sprite (head pointing toward the top of
            the image) or an already-loaded PIL ``Image.Image`` (e.g. the
            procedurally drawn dog). When an Image is supplied it is converted
            to RGBA in place of being opened from disk.

    Returns:
        A tuple of (cropped_image, head_local_offset).  head_local is
        (head_x - center_x, head_y - center_y) in the original (head-up)
        coordinate system.  The y component will be negative because the head
        is above the image center.
    """
    if isinstance(source, Image.Image):
        img = source.convert("RGBA")
    else:
        img = Image.open(source).convert("RGBA")

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    width, height = img.size
    rows = _row_opacity_stats(img)
    max_count = max(count for count, _, _ in rows)
    axis = _symmetry_axis(rows)

    # Threshold that excludes the thin antennae rows (which typically contain
    # only a handful of pixels) but catches the solid head/body.
    count_threshold = max(8, max_count // 12)
    axis_tolerance = max(15.0, width * 0.12)

    head_y = 0
    head_x = axis
    for y, (count, cmin, cmax) in enumerate(rows):
        if count >= count_threshold:
            row_center = (cmin + cmax) / 2.0
            if abs(row_center - axis) <= axis_tolerance:
                head_y = y
                break

    center_x = width / 2.0
    center_y = height / 2.0
    head_local = (head_x - center_x, head_y - center_y)
    return img, head_local


def calibrate_base_rotation(img: Image.Image,
                            head_local: Tuple[float, float] = None) -> float:
    """Empirically verify the rotation needed to make the head point to +x.

    The function paints a small marker at the head tip and evaluates a few
    candidate rotations, returning the one that places the marker farthest to
    the right of the rotated image center.  For the supplied sprites (both the
    roach.png and the procedurally drawn dog, which are "head up") this always
    yields -90 degrees (clockwise quarter turn).

    Args:
        img: The loaded (cropped) sprite.
        head_local: Optional head offset in the original coordinate system.
            If None, a default top-center estimate is used.

    Returns:
        The base rotation angle in degrees for PIL Image.rotate().
    """
    if head_local is None:
        head_local = (0.0, -img.size[1] * 0.25)

    width, height = img.size
    center_x, center_y = width / 2.0, height / 2.0
    head_x = int(round(center_x + head_local[0]))
    head_y = int(round(center_y + head_local[1]))

    marked = img.copy()
    pixels = marked.load()
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            x = head_x + dx
            y = head_y + dy
            if 0 <= x < width and 0 <= y < height:
                pixels[x, y] = (255, 0, 0, 255)

    best_angle = BASE_ROTATION_DEG
    best_score = -float("inf")
    candidates = [-95.0, -92.5, -90.0, -87.5, -85.0, 90.0, 180.0, 270.0]
    for deg in candidates:
        rotated = marked.rotate(deg, expand=True, resample=Image.BICUBIC)
        rpx = rotated.load()
        rw, rh = rotated.size
        rx_sum = ry_sum = n = 0
        for yy in range(rh):
            for xx in range(rw):
                if rpx[xx, yy][:3] == (255, 0, 0):
                    rx_sum += xx
                    ry_sum += yy
                    n += 1
        if n == 0:
            continue
        score = rx_sum / n - rw / 2.0
        if score > best_score:
            best_score = score
            best_angle = deg

    # Normalize to the [-180, 180) interval; equivalent angles collapse to
    # -90 degrees for the supplied sprite.
    while best_angle >= 180.0:
        best_angle -= 360.0
    while best_angle < -180.0:
        best_angle += 360.0
    return best_angle


def head_offset_in_base(head_local: Tuple[float, float],
                        base_deg: float = BASE_ROTATION_DEG) -> Tuple[float, float]:
    """Rotate the head-local offset into the heading=0 (head right) frame.

    Uses the PIL/screen coordinate convention where positive y points downward.
    The rotation matrix for angle theta is:
        x' =  x*cos(theta) + y*sin(theta)
        y' = -x*sin(theta) + y*cos(theta)

    For base_deg == -90 this simplifies to (x', y') = (-y, x), so a head above
    the image center (y < 0) ends up in front of the body (x' > 0).  This holds
    for both the roach sprite and the procedurally drawn dog, so both species
    satisfy hoff_x > 0.
    """
    theta = math.radians(base_deg)
    x, y = head_local
    rx = x * math.cos(theta) + y * math.sin(theta)
    ry = -x * math.sin(theta) + y * math.cos(theta)
    return rx, ry


def build_frames(source: Union[str, Image.Image], target_h: int, n_frames: int,
                 scale_factor: float,
                 base_deg: float = BASE_ROTATION_DEG
                 ) -> Tuple[List[ImageTk.PhotoImage], Tuple[int, int], Tuple[float, float]]:
    """Build a pre-rotated frame set and the scaled head offset.

    Args:
        source: Path to a PNG sprite or a PIL Image (e.g. the dog).
        target_h: Desired on-screen body height before scaling.
        n_frames: Number of evenly-spaced rotation frames.
        scale_factor: Additional per-pet size multiplier.
        base_deg: Base rotation (degrees) aligning head-up sprites to +x.

    Returns:
        (frames, (img_w, img_h), hoff) where hoff is the scaled head offset in
        the heading=0 coordinate system.
    """
    img, head_local = load_roach_image(source)
    width, height = img.size

    effective_height = target_h * scale_factor
    scale = effective_height / height
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    img = img.resize((new_w, new_h), Image.LANCZOS)

    scaled_head_local = (head_local[0] * scale, head_local[1] * scale)
    hoff = head_offset_in_base(scaled_head_local, base_deg)

    frames = []
    step = 360.0 / n_frames
    for i in range(n_frames):
        deg = base_deg + i * step
        rotated = img.rotate(deg, expand=True, resample=Image.BICUBIC)
        frames.append(ImageTk.PhotoImage(rotated))

    return frames, (new_w, new_h), hoff


# ---------------------------------------------------------------------------
# Procedural dog sprite (no external image asset)
# ---------------------------------------------------------------------------

_DOG_SPRITE_CACHE: Dict[str, Image.Image] = {}

# The "line dog" look (per the user's reference): closed white shapes with a
# bold dark outline.  Every body part is built as an L-mode silhouette mask
# (a union of ellipses and leaf polygons); the outline is the dilated mask
# minus the mask itself, so any composite blob gets a clean bold contour
# without hand-matching arc endpoints.
_LD_DARK = ImageColor.getrgb(LINE_DOG_COLOR) + (255,)
_LD_WHITE = ImageColor.getrgb(LINE_DOG_FILL) + (255,)
_LD_OUTLINE = 8           # main contour width, canvas px (bold hand-drawn)
_LD_DETAIL = 5            # inner feature stroke width (mouth / closed eyes)


def _ld_leaf(x0: float, y0: float, x1: float, y1: float,
             bulge: float, n: int = 16) -> List[Tuple[float, float]]:
    """Closed lens/leaf point list between two endpoints (ears, tail, legs)."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy) or 1.0
    px, py = -dy / length, dx / length
    pts = []
    for k in range(n + 1):
        t = k / n
        s = math.sin(t * math.pi)
        pts.append((x0 + dx * t + px * bulge * s,
                    y0 + dy * t + py * bulge * s))
    for k in range(n + 1):
        t = k / n
        s = math.sin(t * math.pi)
        pts.append((x1 - dx * t - px * bulge * s,
                    y1 - dy * t - py * bulge * s))
    return pts


def _ld_mask(size: Tuple[int, int]) -> Tuple[Image.Image, ImageDraw.Draw]:
    m = Image.new("L", size, 0)
    return m, ImageDraw.Draw(m)


def _ld_finish(mask: Image.Image,
               outline_w: int = _LD_OUTLINE) -> Image.Image:
    """Composite a silhouette mask into an RGBA layer: white fill wrapped in
    a bold dark outline that sits just outside the silhouette."""
    dilated = mask.filter(ImageFilter.MaxFilter(2 * outline_w + 1))
    edge = ImageChops.subtract(dilated, mask)
    layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    layer.paste(Image.new("RGBA", mask.size, _LD_DARK), (0, 0), edge)
    layer.paste(Image.new("RGBA", mask.size, _LD_WHITE), (0, 0), mask)
    return layer


def _ld_fill(mask: Image.Image,
             fill_color: Tuple[int, int, int, int]) -> Image.Image:
    """Composite a silhouette mask into an RGBA layer with a flat fill and
    no outline (used for interior color patches)."""
    layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    layer.paste(Image.new("RGBA", mask.size, fill_color), (0, 0), mask)
    return layer


def _ld_finish_color(mask: Image.Image,
                    fill_color: Tuple[int, int, int, int],
                    outline_w: int = _LD_OUTLINE) -> Image.Image:
    """Composite a silhouette mask into an RGBA layer: colored fill wrapped
    in a bold dark outline (used for exterior body parts)."""
    dilated = mask.filter(ImageFilter.MaxFilter(2 * outline_w + 1))
    edge = ImageChops.subtract(dilated, mask)
    layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    layer.paste(Image.new("RGBA", mask.size, _LD_DARK), (0, 0), edge)
    layer.paste(Image.new("RGBA", mask.size, fill_color), (0, 0), mask)
    return layer


def _draw_rotated_corgi_head(face_mode: Tuple[str, str],
                              HCX: float,
                              HEAD_CY: float,
                              NECK_Y: float) -> Tuple[Image.Image, Tuple[int, int]]:
    """Draw a cute front-facing corgi head upright, then rotate it 90° CCW.

    The global dog sprite is rotated -90° by ``build_frames`` (head-up in the
    source becomes head-right in the game).  A front-facing head drawn upright
    in the source would therefore appear tilted 90° clockwise in the game.
    We pre-rotate the head 90° counterclockwise here so it appears upright
    in the final view: ears up, eyes side by side, nose/mouth/tongue down.
    """
    hw, hh = 140, 160
    hc = hw / 2.0
    vc = hh / 2.0

    hbig = Image.new("L", (hw, hh), 0)
    hcream = Image.new("L", (hw, hh), 0)
    himg = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))

    hbd = ImageDraw.Draw(hbig)
    hcd = ImageDraw.Draw(hcream)
    hd = ImageDraw.Draw(himg)

    def ellipse(mask_d, bx, by, rx, ry=None):
        if ry is None:
            ry = rx
        mask_d.ellipse([bx - rx, by - ry, bx + rx, by + ry], fill=255)

    def leaf(mask_d, x0, y0, x1, y1, bulge):
        mask_d.polygon(_ld_leaf(x0, y0, x1, y1, bulge), fill=255)

    HEAD_RX = 50.0
    HEAD_RY = 46.0

    # round tan skull
    ellipse(hbd, hc, vc, HEAD_RX, HEAD_RY)

    # two big upright ears
    leaf(hbd, hc - 28, vc - 28, hc - 44, vc - 86, 22)
    leaf(hbd, hc + 28, vc - 28, hc + 44, vc - 86, 22)
    # cream inner ears
    leaf(hcd, hc - 26, vc - 32, hc - 40, vc - 78, 14)
    leaf(hcd, hc + 26, vc - 32, hc + 40, vc - 78, 14)

    # cream muzzle / cheek patch
    ellipse(hcd, hc, vc + 20, HEAD_RX - 20, HEAD_RY - 22)

    # colored head: tan outline+fill first, then cream patches (no outline)
    himg.alpha_composite(_ld_finish_color(hbig, _CORGI_TAN))
    himg.alpha_composite(_ld_fill(hcream, _CORGI_CREAM))

    # face details in canonical upright orientation
    EYE_L = (hc - 19, vc - 14)
    EYE_R = (hc + 19, vc - 14)
    if face_mode[0] == "closed":
        for (EX, EY) in (EYE_L, EYE_R):
            hd.arc([EX - 9, EY - 6, EX + 9, EY + 6],
                   180, 360, fill=_LD_DARK, width=_LD_DETAIL)
    else:
        for (EX, EY) in (EYE_L, EYE_R):
            hd.ellipse([EX - 10, EY - 13, EX + 10, EY + 13], fill=_CORGI_EYE)
            hd.ellipse([EX - 2, EY - 9, EX + 4, EY - 3],
                       fill=(255, 255, 255, 255))

    NOSE_Y = vc + 8
    hd.ellipse([hc - 9, NOSE_Y - 7, hc + 9, NOSE_Y + 7], fill=_CORGI_NOSE)

    mouth_y = NOSE_Y + 22
    hd.line([hc, NOSE_Y + 6, hc, mouth_y - 2],
            fill=_LD_DARK, width=_LD_DETAIL)
    hd.arc([hc - 14, mouth_y - 8, hc + 14, mouth_y + 10],
           20, 160, fill=_LD_DARK, width=_LD_DETAIL)

    if face_mode[0] == "open":
        tongue = Image.new("RGBA", (hw, hh), (0, 0, 0, 0))
        td = ImageDraw.Draw(tongue)
        poly = _ld_leaf(hc, mouth_y + 2, hc, mouth_y + 22, 13)
        td.polygon(poly, fill=_CORGI_TONGUE)
        td.line(poly, fill=_LD_DARK, width=3, joint="curve")
        td.line([hc, mouth_y + 4, hc, mouth_y + 18],
                fill=(220, 80, 110, 255), width=2)
        himg.alpha_composite(tongue)

    # rotate 90° counterclockwise (PIL positive angle = top -> left)
    rotated = himg.rotate(90, expand=True, resample=Image.NEAREST)

    # Center the rotated head at (HCX, HEAD_CY) in the canvas.  This keeps the
    # head near the top/center of the sprite so the auto-detection in
    # load_roach_image still finds it; the head overlaps the body slightly and
    # the neck is formed by the overlap region after the global -90° rotation.
    rcx = int(round(vc))
    rcy = int(round(hw - 1 - hc))
    left = int(round(HCX - rcx))
    top = int(round(HEAD_CY - rcy))
    return rotated, (left, top)


def draw_dog_state(state: str = "walk",
                   width: int = 240, height: int = 400) -> Image.Image:
    """Draw a colored cartoon corgi: SIDE-PROFILE body with a cute FRONT-FACING
    head, pre-rotated so it appears upright after the global -90° rotation.

    The shared geometry helpers (``load_roach_image`` / ``head_offset_in_base``)
    rotate the sprite -90 degrees so the body points to +x (forward).  For that
    rotation to turn this into a proper 2D side runner, the corgi body is drawn
    "lying on its right side" pointing UP:

        * torso neck/rump ........ TOP    -> forward (game +x)
        * spine / back ........... LEFT   -> up      (game -y)
        * belly + 4 legs ......... RIGHT  -> down    (game +y)
        * tail / rump ............ BOTTOM -> back    (game -x)

    The head is drawn separately in an upright front-facing pose, then rotated
    90° counterclockwise before being composited onto the body.  After the
    global -90° rotation the head therefore appears upright in the game:
    ears up, eyes side by side, nose/mouth/tongue down.
    Exterior body parts accumulate into the ``big`` tan mask (dark outline);
    cream patches go into ``cream`` and are composited on top without an
    outline so they read as soft markings.
    """
    size = (width, height)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    big = Image.new("L", size, 0)     # tan exterior silhouette
    cream = Image.new("L", size, 0)   # cream markings (no outline)
    bd = ImageDraw.Draw(big)
    cd = ImageDraw.Draw(cream)

    # --- side-profile skeleton (canvas frame) -------------------------------
    SPINE = 92.0          # left edge of torso  (-> up in game)
    BELLY = 168.0         # right edge of torso (-> down in game: legs live here)
    NECK_Y = 156.0
    BUTT_Y = 306.0
    HCX = (SPINE + BELLY) / 2.0     # horizontal center ~130
    TR = (BELLY - SPINE) / 2.0      # torso half-width ~38

    def ellipse(mask_d, bx, by, rx, ry=None):
        if ry is None:
            ry = rx
        mask_d.ellipse([bx - rx, by - ry, bx + rx, by + ry], fill=255)

    def leaf(mask_d, x0, y0, x1, y1, bulge):
        mask_d.polygon(_ld_leaf(x0, y0, x1, y1, bulge), fill=255)

    # torso: plump capsule (straight mid-section + round neck + round rump)
    bd.rectangle([SPINE, NECK_Y, BELLY, BUTT_Y], fill=255)
    ellipse(bd, HCX, NECK_Y, TR + 5)       # neck round (top)
    ellipse(bd, HCX, BUTT_Y, TR + 6)       # rump round (bottom)

    # ---- corgi head is drawn separately and rotated 90° CCW so it appears
    # upright after the global -90° rotation.  See _draw_rotated_corgi_head.
    HEAD_CY = 140.0

    # ----- legs / tail helpers ----------------------------------------------
    # legs are horizontal capsules on the BELLY side (canvas-right).
    def draw_legs(spec):
        for (lx, ly, llen) in spec:
            bd.rectangle([lx, ly - 14, lx + llen, ly + 14], fill=255)
            ellipse(bd, lx + llen, ly, 14)
            # cream paw tip
            ellipse(cd, lx + llen - 4, ly, 9)

    def draw_tail(curly=False):
        if curly:
            leaf(bd, HCX - 4, BUTT_Y, HCX + 24, BUTT_Y + 34, 14)
        else:
            leaf(bd, HCX, BUTT_Y, HCX + 8, BUTT_Y + 52, 14)
        ellipse(bd, HCX, BUTT_Y + 6, 14)

    # ---- poses --------------------------------------------------------------
    if state == "walk":
        draw_legs([(162, 180, 42), (162, 212, 42),
                   (154, 290, 40), (154, 320, 40)])
        draw_tail()
        face_mode = ("open", "w")
    elif state == "sit":
        draw_legs([(164, 174, 36), (164, 204, 36),
                   (154, 296, 20), (154, 316, 20)])
        ellipse(bd, BELLY - 4, 308, 22, 26)        # folded haunch
        draw_tail()
        face_mode = ("open", "w")
    elif state == "sleep":
        draw_legs([(162, 248, 16), (162, 268, 16),
                   (154, 298, 14), (154, 316, 14)])
        draw_tail(curly=True)
        face_mode = ("closed", "w")
    elif state == "chase":
        draw_legs([(164, 174, 48), (160, 218, 48),
                   (150, 294, 46), (154, 324, 46)])
        draw_tail(curly=True)
        face_mode = ("open", "w")
    elif state == "stretch":
        draw_legs([(166, 194, 54), (164, 222, 52),
                   (152, 294, 28), (154, 316, 28)])
        draw_tail()
        face_mode = ("open", "w")
    elif state == "look":
        draw_legs([(164, 180, 38), (164, 210, 38),
                   (154, 292, 36), (154, 320, 36)])
        draw_tail()
        face_mode = ("open", "w")
    else:
        raise ValueError("unknown dog state: %r" % state)

    # cream belly/chest patch on the lower-right side (down in game)
    ellipse(cd, HCX + 10, (NECK_Y + BUTT_Y) / 2 + 8, TR - 6,
            (BUTT_Y - NECK_Y) / 2 - 10)
    ellipse(cd, HCX + 14, NECK_Y + 26, TR - 10, 28)   # chest blaze

    # composite the colored body: tan outline+fill first, then cream patches
    img.alpha_composite(_ld_finish_color(big, _CORGI_TAN))
    img.alpha_composite(_ld_fill(cream, _CORGI_CREAM))

    # yellow collar around the neck (drawn before head so head covers the top)
    collar_y = NECK_Y - 2
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([SPINE + 18, collar_y - 9, BELLY - 18, collar_y + 9],
                        radius=7, fill=_CORGI_COLLAR, outline=_LD_DARK, width=3)
    d.line([SPINE + 22, collar_y - 4, BELLY - 22, collar_y - 4],
           fill=(255, 235, 130, 255), width=2)

    # composite the rotated front-facing head on top of the body
    head_buf, head_offset = _draw_rotated_corgi_head(face_mode, HCX, HEAD_CY, NECK_Y)
    img.alpha_composite(head_buf, head_offset)

    return img


def get_dog_sprite(state: str = "walk") -> Image.Image:
    """Return the cached line-art dog sprite for a pose (built once)."""
    global _DOG_SPRITE_CACHE
    if state not in _DOG_SPRITE_CACHE:
        _DOG_SPRITE_CACHE[state] = draw_dog_state(state)
    return _DOG_SPRITE_CACHE[state]


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def wrap_angle(delta: float) -> float:
    """Wrap an angle difference into the [-pi, pi] interval."""
    while delta > math.pi:
        delta -= 2.0 * math.pi
    while delta < -math.pi:
        delta += 2.0 * math.pi
    return delta


def rotate_point(x: float, y: float, angle: float) -> Tuple[float, float]:
    """Rotate a vector by angle using screen coordinates.

    Positive angle rotates clockwise visually (because y points down).  The
    matrix matches tkinter/PIL conventions:
        x' = x*cos(a) - y*sin(a)
        y' = x*sin(a) + y*cos(a)
    """
    return (x * math.cos(angle) - y * math.sin(angle),
            x * math.sin(angle) + y * math.cos(angle))


# ---------------------------------------------------------------------------
# Pet entity (shared movement/state machine for dog and roach)
# ---------------------------------------------------------------------------

class Pet:
    """A single desktop pet with stateful behavior and procedural extras.

    Both species share the exact same movement and finite-state-machine logic
    (wander, boundary avoidance, mouse evasion, hide/re-enter, bob).  They
    differ only in:
      * the sprite frames / head offset (``framesets[species]``),
      * the extra animated overlay (dog: ears + tail; roach: antennae),
      * the click action (dog: morph to roach; roach: quit).
    """

    def __init__(self, canvas: tk.Canvas, framesets: Dict[str, FrameSet],
                 screen_w: int, screen_h: int, on_kill, species: str = "dog",
                 on_burst=None, init_x: Optional[float] = None,
                 init_y: Optional[float] = None,
                 init_heading: Optional[float] = None,
                 init_speed: Optional[float] = None):
        self.canvas = canvas
        self.framesets = framesets
        self.sw = screen_w
        self.sh = screen_h
        self.on_kill = on_kill
        self.on_burst = on_burst
        self.species = species

        if species == "dog":
            self.dog_state = "walk"
            self._rendered_dog_state = "walk"
            frames, img_size, hoff = framesets["dog"]["walk"]
        else:
            frames, img_size, hoff = framesets[species]
        self.frames = frames
        self.img_w, self.img_h = img_size
        self.hoff = hoff
        self.body_len = float(self.img_h)
        self.body_w = float(self.img_w)

        # Position and kinematics (optionally seeded for burst spawns).
        margin = 120.0
        if init_x is not None and init_y is not None:
            self.x = float(init_x)
            self.y = float(init_y)
        else:
            self.x = random.uniform(margin, max(margin, screen_w - margin))
            self.y = random.uniform(margin, max(margin, screen_h - margin))
        if init_heading is not None:
            self.heading = float(init_heading)
        else:
            self.heading = random.uniform(0.0, 2.0 * math.pi)
        self.speed = 0.0
        if self.species == "dog":
            # Dogs stroll slowly and never react to the cursor.
            self.target_speed = DOG_WALK_SPEED
        elif init_speed is not None:
            self.target_speed = float(init_speed)
        else:
            self.target_speed = random.uniform(*NORMAL_SPEED)

        # State machine: walk, pause, idle, flee, hidden.
        self.state = "walk"
        self.state_timer = random.uniform(1.0, 4.0)
        self.panic = False
        self.entering = False
        self._exit_side = None

        # Dog behavioral pose + timer (initialized for both species so the
        # attribute always exists; only meaningful when species == "dog").
        self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)
        self._last_mx = None
        self._last_my = None

        # Timing and phase offsets.
        self.t = random.uniform(0.0, 100.0)
        self.gait_phase = random.uniform(0.0, 2.0 * math.pi)
        self.ant_phase = random.uniform(0.0, 2.0 * math.pi)

        # Wander baseline and per-component phases.
        self.base_heading = self.heading
        self.wander_phases = [random.uniform(0.0, 2.0 * math.pi)
                              for _ in WANDER_FREQS]

        # Canvas items: body first; extras are created and raised above it.
        self.body_item = canvas.create_image(self.x, self.y, image=frames[0])
        self.canvas.tag_bind(self.body_item, "<Button-1>", self._on_click)
        self._build_extra_items()
        self._last_frame_idx = 0

    # -----------------------------------------------------------------------
    # Extra overlay (ears+tail for dog, antennae for roach) management
    # -----------------------------------------------------------------------

    def _destroy_extra_items(self) -> None:
        """Delete every extra overlay canvas item."""
        for coll in (getattr(self, "antennae", []),
                     getattr(self, "ears", [])):
            for it in coll:
                try:
                    self.canvas.delete(it)
                except Exception:
                    pass
        tail = getattr(self, "tail", None)
        if tail is not None:
            try:
                self.canvas.delete(tail)
            except Exception:
                pass
        zzz = getattr(self, "zzz", None)
        if zzz is not None:
            try:
                self.canvas.delete(zzz)
            except Exception:
                pass

    def _build_extra_items(self) -> None:
        """(Re)create the species-appropriate overlay items above the body."""
        self._destroy_extra_items()
        if self.species == "roach":
            self.ears: List[int] = []
            self.tail = None
            self.antennae = [
                self.canvas.create_line(
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    fill=ANTENNA_COLOR,
                    width=ANTENNA_WIDTH,
                    capstyle="round",
                    smooth=True,
                    splinesteps=12,
                )
                for _ in range(2)
            ]
            items = self.antennae
        else:  # dog
            self.antennae: List[int] = []
            # Ears and tail are baked into the line-dog sprite itself; the
            # only remaining canvas overlay is the floating "z z z" text.
            self.ears = []
            self.tail = None
            self.zzz = self.canvas.create_text(
                0, 0, text="z z z", fill=LINE_DOG_COLOR,
                font=("Arial", max(10, int(self.img_h * 0.10)), "bold"),
                state="hidden",
            )
            items = [self.zzz]

        for it in items:
            self.canvas.tag_raise(it, self.body_item)
            self.canvas.tag_bind(it, "<Button-1>", self._on_click)

    def _set_extra_state(self, state: str) -> None:
        """Show or hide all extra overlay items."""
        for it in (self.antennae + self.ears + ([self.tail] if self.tail else [])):
            try:
                self.canvas.itemconfig(it, state=state)
            except Exception:
                pass

    def _show_extra(self) -> None:
        self._set_extra_state("normal")

    def _hide_extra(self) -> None:
        self._set_extra_state("hidden")

    def _apply_species(self, species: str, preserve: bool = True) -> None:
        """Swap this pet to another species, keeping shared state if asked."""
        self.species = species
        if species == "dog":
            self.dog_state = "walk"
            self._rendered_dog_state = "walk"
            frames, img_size, hoff = self.framesets["dog"]["walk"]
        else:
            frames, img_size, hoff = self.framesets[species]
        self.frames = frames
        self.img_w, self.img_h = img_size
        self.hoff = hoff
        self.body_len = float(self.img_h)
        self.body_w = float(self.img_w)
        self._build_extra_items()
        if preserve:
            idx = self._choose_frame()
            self.canvas.itemconfig(self.body_item, image=self.frames[idx],
                                   state="normal")
            self._last_frame_idx = idx
            self._show_extra()

    def _morph_to_roach(self) -> None:
        """Instantly become a roach, switching to the roach logic in place."""
        if self.species == "roach":
            return
        self._apply_species("roach", preserve=True)

    def _set_dog_state(self, state: str) -> None:
        """Switch the dog's visual pose (walk/sit/sleep/chase/stretch/look).

        Updates the active frame set to the pose's pre-rotated frames and
        toggles the sleep "Zzz" overlay.  No-op if already in that pose.
        """
        if self.species != "dog" or state == self.dog_state:
            return
        self.dog_state = state
        self._rendered_dog_state = state
        # framesets["dog"][state] is (frames, size, hoff); keep the list.
        self.frames = self.framesets["dog"][state][0]
        idx = self._choose_frame()
        self.canvas.itemconfig(self.body_item, image=self.frames[idx])
        self._last_frame_idx = idx
        # Show the "Zzz" marker only while sleeping.
        zzz = getattr(self, "zzz", None)
        if zzz is not None:
            self.canvas.itemconfig(
                zzz, state="normal" if state == "sleep" else "hidden")

    # -----------------------------------------------------------------------
    # Boundary / edge helpers
    # -----------------------------------------------------------------------

    def _offscreen(self) -> bool:
        """True when the pet has moved well outside the visible screen."""
        m = 80.0
        return (self.x < -m or self.x > self.sw + m or
                self.y < -m or self.y > self.sh + m)

    def _fully_onscreen(self) -> bool:
        """True when the pet is far enough from all edges to roam freely."""
        m = 80.0
        return (m < self.x < self.sw - m and
                m < self.y < self.sh - m)

    def _nearest_edge_heading(self) -> float:
        """Return the heading that points toward the nearest screen edge."""
        d_left = self.x
        d_right = self.sw - self.x
        d_top = self.y
        d_bottom = self.sh - self.y
        min_d = min(d_left, d_right, d_top, d_bottom)
        if min_d == d_left:
            return math.pi
        if min_d == d_right:
            return 0.0
        if min_d == d_top:
            return math.pi / 2.0
        return -math.pi / 2.0

    def _current_edge_side(self) -> str:
        """Return the edge the pet is currently closest to."""
        d_left = self.x
        d_right = self.sw - self.x
        d_top = self.y
        d_bottom = self.sh - self.y
        sides = {
            "left": d_left,
            "right": d_right,
            "top": d_top,
            "bottom": d_bottom,
        }
        return min(sides, key=sides.get)

    def _respawn(self, from_side: str = None):
        """Place the pet just outside a random screen edge and head inward."""
        margin = 60.0
        sides = ["left", "right", "top", "bottom"]
        if from_side and from_side in sides:
            # Prefer reappearing on the opposite side from where it exited.
            opposite = self._opposite_side(from_side)
            weights = [3.0 if s == opposite else 1.0 for s in sides]
            side = random.choices(sides, weights=weights)[0]
        else:
            side = random.choice(sides)

        if side == "left":
            self.x = -margin
            self.y = random.uniform(120.0, max(120.0, self.sh - 120.0))
            self.heading = random.uniform(-0.35, 0.35)
        elif side == "right":
            self.x = self.sw + margin
            self.y = random.uniform(120.0, max(120.0, self.sh - 120.0))
            self.heading = math.pi + random.uniform(-0.35, 0.35)
        elif side == "top":
            self.x = random.uniform(120.0, max(120.0, self.sw - 120.0))
            self.y = -margin
            self.heading = math.pi / 2.0 + random.uniform(-0.35, 0.35)
        else:  # bottom
            self.x = random.uniform(120.0, max(120.0, self.sw - 120.0))
            self.y = self.sh + margin
            self.heading = -math.pi / 2.0 + random.uniform(-0.35, 0.35)

        self.base_heading = self.heading
        self.speed = random.uniform(40.0, 70.0)
        self.target_speed = random.uniform(*NORMAL_SPEED)
        self.entering = True

    @staticmethod
    def _opposite_side(side: str) -> str:
        """Return the edge opposite to the given one."""
        opposites = {
            "left": "right",
            "right": "left",
            "top": "bottom",
            "bottom": "top",
        }
        return opposites.get(side, side)

    # -----------------------------------------------------------------------
    # Click handler (species-dependent morph / kill)
    # -----------------------------------------------------------------------

    def _on_click(self, _event) -> None:
        if self.species == "dog":
            # Clicking the lone dog bursts the 5 roaches at its position.
            if self.on_burst is not None:
                self.on_burst(self.x, self.y, self)
        else:
            # Clicking a roach quits the application.
            self.on_kill()

    # -----------------------------------------------------------------------
    # Movement & state machine (shared by both species)
    # -----------------------------------------------------------------------

    def _wander_offset(self) -> float:
        """Smooth continuous heading drift from a sum of sine waves."""
        offset = 0.0
        for amp, freq, phase in zip(WANDER_AMPS, WANDER_FREQS, self.wander_phases):
            offset += amp * math.sin(math.tau * freq * self.t + phase)
        return offset

    def _boundary_nudge(self, target: float) -> float:
        """Return a heading correction that steers the pet away from edges."""
        margin_x = self.sw * EDGE_MARGIN_RATIO
        margin_y = self.sh * EDGE_MARGIN_RATIO
        nudge = 0.0

        # Left edge -> steer right (heading 0).
        if self.x < margin_x:
            weight = (1.0 - self.x / margin_x) ** 2
            nudge += wrap_angle(0.0 - target) * weight * EDGE_STRENGTH
        # Right edge -> steer left (heading pi).
        if self.x > self.sw - margin_x:
            weight = (1.0 - (self.sw - self.x) / margin_x) ** 2
            nudge += wrap_angle(math.pi - target) * weight * EDGE_STRENGTH
        # Top edge -> steer down (heading pi/2).
        if self.y < margin_y:
            weight = (1.0 - self.y / margin_y) ** 2
            nudge += wrap_angle(math.pi / 2.0 - target) * weight * EDGE_STRENGTH
        # Bottom edge -> steer up (heading -pi/2).
        if self.y > self.sh - margin_y:
            weight = (1.0 - (self.sh - self.y) / margin_y) ** 2
            nudge += wrap_angle(-math.pi / 2.0 - target) * weight * EDGE_STRENGTH

        return nudge

    def _choose_frame(self) -> int:
        """Map the current heading to the pre-rotated frame index."""
        deg = math.degrees(self.heading)
        idx = int(round(-deg * N_FRAMES / 360.0)) % N_FRAMES
        return idx

    def _update_state(self, dt: float, mx: float, my: float, dist: float):
        """Advance the finite state machine based on mouse proximity."""
        if self.state == "hidden":
            self.state_timer -= dt
            if self.state_timer <= 0:
                self._respawn(from_side=self._exit_side)
                self.state = "walk"
                self.state_timer = random.uniform(*WALK_TIME)
                self.canvas.itemconfig(self.body_item, state="normal")
                self._show_extra()
            return

        if self.state in ("walk", "pause", "idle"):
            if self.species == "roach":
                if dist < PANIC_RADIUS and dist > 0.0:
                    # Panic: sprint to the nearest edge and hide.
                    self.state = "flee"
                    self.panic = True
                    self.target_speed = PANIC_SPEED
                    self.state_timer = 6.0
                elif dist < ALERT_RADIUS and dist > 0.0:
                    # Alert: flee directly away from the cursor.
                    self.state = "flee"
                    self.panic = False
                    self.target_speed = FLEE_SPEED
                    self.state_timer = random.uniform(1.5, 3.0)
                else:
                    self.state_timer -= dt
                    if self.state_timer <= 0:
                        self._cycle_walk_pause_idle(is_dog=False)
            else:
                # Dog: run the playful multi-pose behavior (chase / sit /
                # sleep / stretch / look / wander).  Dogs NEVER flee.
                self._update_dog_behavior(dt, mx, my, dist)

        elif self.state == "flee":
            self.state_timer -= dt
            if self.panic:
                self.target_speed = PANIC_SPEED
                if self._offscreen():
                    self.state = "hidden"
                    self.state_timer = random.uniform(*HIDE_TIME)
                    self._exit_side = self._current_edge_side()
                    self.canvas.itemconfig(self.body_item, state="hidden")
                    self._hide_extra()
                    return
            else:
                if dist < ALERT_RADIUS and dist > 0.0:
                    self.state_timer = max(self.state_timer, 0.5)
                if self._offscreen():
                    self.state = "hidden"
                    self.state_timer = random.uniform(*HIDE_TIME)
                    self._exit_side = self._current_edge_side()
                    self.canvas.itemconfig(self.body_item, state="hidden")
                    self._hide_extra()
                    return
                if self.state_timer <= 0 and dist > ALERT_RADIUS:
                    self.state = "walk"
                    self.state_timer = random.uniform(*WALK_TIME)
                    self.base_heading = self.heading
                    self.target_speed = random.uniform(*NORMAL_SPEED)

    def _update_dog_behavior(self, dt: float, mx: float, my: float,
                             dist: float) -> None:
        """Dog-only playful state machine: wander / sit / sleep / stretch /
        look / chase, with chase triggered by a moving cursor.

        The dog never flees (flee is a roach behavior).  A moving cursor in
        range makes the dog switch to ``chase`` and run happily toward the
        pointer; when the cursor stops (or the chase timer ends) it settles
        back into a calm pose.
        """
        # Detect cursor movement (pynput screen coords; None on first tick).
        if self._last_mx is None:
            self._last_mx, self._last_my = mx, my
        moved = math.hypot(mx - self._last_mx, my - self._last_my)
        self._last_mx, self._last_my = mx, my

        self.dog_pose_timer -= dt

        if self.dog_state == "chase":
            # Run toward the cursor.
            self.target_speed = DOG_CHASE_SPEED
            self.state = "walk"
            if self.dog_pose_timer <= 0 or moved < 1.5:
                # Lost interest: settle back into a calm roaming pose.
                self._set_dog_state("walk")
                self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)
            return

        # Calm / stationary poses.
        if self.dog_state in DOG_STILL_POSES:
            self.target_speed = 0.0
            self.state = "idle" if self.dog_state == "sit" else "pause"
        else:
            self.target_speed = DOG_WALK_SPEED
            self.state = "walk"

        if self.dog_pose_timer <= 0:
            if moved > 2.0 and random.random() < 0.9 \
                    and self.dog_state != "sleep":
                # Excited: chase the moving cursor.
                self._set_dog_state("chase")
                self.dog_pose_timer = random.uniform(*DOG_CHASE_TIME)
            elif self.dog_state == "sleep":
                self._set_dog_state(random.choice(
                    ["sit", "stretch", "look", "walk"]))
                self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)
            else:
                choice = random.random()
                if choice < 0.30:
                    self._set_dog_state("sleep")
                    self.dog_pose_timer = random.uniform(*DOG_SLEEP_TIME)
                elif choice < 0.55:
                    self._set_dog_state("sit")
                    self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)
                elif choice < 0.75:
                    self._set_dog_state("stretch")
                    self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)
                elif choice < 0.90:
                    self._set_dog_state("look")
                    self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)
                else:
                    self._set_dog_state("walk")
                    self.dog_pose_timer = random.uniform(*DOG_POSE_TIME)

    def _cycle_walk_pause_idle(self, is_dog: bool) -> None:
        """Shared walk/pause/idle transition used by both species.

        Dogs always return to a slow ``DOG_WALK_SPEED`` stroll; roaches use a
        randomized normal speed.  Roaches additionally enter flee from the
        mouse-driven branch of ``_update_state`` (not used by dogs).
        """
        if self.state == "walk":
            if random.random() < 0.20:
                self.state = "idle"
                self.state_timer = random.uniform(*IDLE_TIME)
                self.target_speed = 0.0
            else:
                self.state = "pause"
                self.state_timer = random.uniform(*PAUSE_TIME)
                self.target_speed = 0.0
        else:
            self.state = "walk"
            self.state_timer = random.uniform(*WALK_TIME)
            self.base_heading = self.heading
            self.wander_phases = [
                random.uniform(0.0, 2.0 * math.pi)
                for _ in WANDER_FREQS
            ]
            self.target_speed = (DOG_WALK_SPEED if is_dog
                                else random.uniform(*NORMAL_SPEED))

    def _update_heading(self, dt: float, mx: float, my: float, dist: float):
        """Compute the target heading and smoothly interpolate toward it."""
        if self.species == "dog" and self.dog_state == "chase":
            # Happy chase: head straight for the cursor.
            target = math.atan2(my - self.y, mx - self.x)
            target = wrap_angle(target + self._boundary_nudge(target) * dt)
            rate = TURN_RATE_FLEE
        elif self.state == "flee" and self.species == "roach":
            if self.panic:
                target = self._nearest_edge_heading()
            else:
                if dist > 0.0:
                    target = math.atan2(self.y - my, self.x - mx)
                else:
                    target = self.heading
            nudge = self._boundary_nudge(target)
            target = wrap_angle(target + nudge * dt)
            rate = TURN_RATE_FLEE
        elif self.state == "walk":
            target = wrap_angle(self.base_heading + self._wander_offset())
            target = wrap_angle(target + self._boundary_nudge(target) * dt)
            rate = TURN_RATE
        else:
            # pause / idle: keep current heading, only slow boundary correction.
            target = self.heading
            nudge = self._boundary_nudge(target)
            if abs(nudge) > 0.01:
                target = wrap_angle(target + nudge * dt)
            rate = TURN_RATE

        diff = wrap_angle(target - self.heading)
        self.heading += diff * min(1.0, dt * rate)
        self.heading = wrap_angle(self.heading)

    def _update_position(self, dt: float):
        """Apply speed smoothing and integrate velocity into position."""
        if self.state == "hidden":
            return

        accel = 5.0 if self.state == "flee" else 2.0
        self.speed += (self.target_speed - self.speed) * min(1.0, dt * accel)

        self.x += math.cos(self.heading) * self.speed * dt
        self.y += math.sin(self.heading) * self.speed * dt

        if self.entering and self._fully_onscreen():
            self.entering = False

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    def _draw(self, dt: float):
        """Update the body image, bobbing position, and extra overlays."""
        if self.state == "hidden":
            return

        # Body bob perpendicular to heading, stronger when moving fast.
        bob_amp = min(MAX_BOB_AMP, self.speed * BOB_AMP_SPEED_RATIO)
        if self.state in ("pause", "idle"):
            bob_amp = 0.0
        if self.state == "flee":
            bob_amp *= 1.3

        bob_val = math.sin(self.t * math.tau * BOB_FREQ + self.gait_phase)
        bob_x = -math.sin(self.heading) * bob_amp * bob_val
        bob_y = math.cos(self.heading) * bob_amp * bob_val

        bx = self.x + bob_x
        by = self.y + bob_y

        idx = self._choose_frame()
        if idx != self._last_frame_idx:
            self.canvas.itemconfig(self.body_item, image=self.frames[idx])
            self._last_frame_idx = idx
        self.canvas.coords(self.body_item, bx, by)

        # Head position in world coordinates (offset in the heading frame).
        hoff_x, hoff_y = self.hoff
        head_x = bx + hoff_x * math.cos(self.heading) - hoff_y * math.sin(self.heading)
        head_y = by + hoff_x * math.sin(self.heading) + hoff_y * math.cos(self.heading)

        # Rear of the body (tail root) is opposite the head offset.
        tail_x = bx - hoff_x * math.cos(self.heading) + hoff_y * math.sin(self.heading)
        tail_y = by - hoff_x * math.sin(self.heading) - hoff_y * math.cos(self.heading)

        self._draw_extra(head_x, head_y, tail_x, tail_y)

        # Floating "Zzz" marker above the head while the dog sleeps.
        if self.species == "dog":
            zzz = getattr(self, "zzz", None)
            if zzz is not None:
                if self.dog_state == "sleep":
                    float_y = head_y - self.img_h * 0.34 \
                        - 4.0 * math.sin(self.t * 2.0)
                    self.canvas.coords(
                        zzz, head_x + self.img_w * 0.20, float_y)
                else:
                    self.canvas.coords(zzz, head_x, head_y)

    def _draw_extra(self, head_x: float, head_y: float,
                    tail_x: float, tail_y: float) -> None:
        """Dispatch to the species-specific overlay renderer."""
        if self.species == "roach":
            self._draw_antennae(head_x, head_y)
        elif self.ears or self.tail:
            # The line-dog bakes ears/tail into the sprite; this only runs
            # for legacy frame sets that still provide the overlays.
            self._draw_ears_and_tail(head_x, head_y, tail_x, tail_y)

    def _draw_antennae(self, head_x: float, head_y: float):
        """Draw two animated antennae emerging from the head tip (roach)."""
        state = self.state
        t = self.t
        phase = self.ant_phase

        if state == "flee":
            # Laid back, high-frequency trembling.
            base_dir = self.heading + math.pi
            freq = 10.0
            base_spread = 0.18
            spread_sweep = 0.08
            amp = 9.0
            len_ratio = 1.2
        elif state == "idle":
            # Very slow, gentle exploration.
            base_dir = self.heading
            freq = 0.6
            base_spread = 0.22
            spread_sweep = 0.08
            amp = 2.5
            len_ratio = 1.3
        else:
            # Walk / pause: active scanning with a slow opening/closing rhythm.
            base_dir = self.heading
            freq = 2.0
            base_spread = 0.30
            spread_sweep = 0.28
            amp = 7.0
            len_ratio = ANTENNA_LENGTH_RATIO

        ant_len = self.body_len * len_ratio
        open_val = math.sin(t * 1.4 + phase)

        for side in (-1, 1):
            spread = base_spread + side * 0.05 + open_val * spread_sweep
            dir_ang = base_dir + side * spread

            # Slight lateral root offset so the two antennae diverge cleanly.
            perp_x = -math.sin(self.heading)
            perp_y = math.cos(self.heading)
            root_x = head_x + perp_x * side * 2.0
            root_y = head_y + perp_y * side * 2.0

            pts = []
            for k in range(ANTENNA_SEGMENTS):
                s = k / (ANTENNA_SEGMENTS - 1.0)
                # Base point along the antenna direction.
                px = root_x + math.cos(dir_ang) * ant_len * s
                py = root_y + math.sin(dir_ang) * ant_len * s

                # Length-wise sine wave; phase advances with s so the antenna
                # appears to whip rather than just pivot at the tip.
                wave_phase = (t * freq * math.tau +
                              phase +
                              side * 0.6 +
                              s * 2.0 * math.pi)
                wave = math.sin(wave_phase)

                # Amplitude grows toward the tip for a flexible feel.
                perp_dx = -math.sin(dir_ang)
                perp_dy = math.cos(dir_ang)
                px += perp_dx * wave * amp * s
                py += perp_dy * wave * amp * s

                pts.extend([px, py])

            index = 0 if side < 0 else 1
            self.canvas.coords(self.antennae[index], *pts)

    def _draw_ears_and_tail(self, head_x: float, head_y: float,
                            tail_x: float, tail_y: float):
        """Draw a swinging pair of ears and a wagging tail (dog)."""
        state = self.state
        t = self.t
        phase = self.ant_phase
        heading = self.heading
        fwd_x, fwd_y = math.cos(heading), math.sin(heading)
        perp_x, perp_y = -math.sin(heading), math.cos(heading)

        if state == "flee":
            # Ears laid back, fast tremble; tail tucked and whipping.
            ear_freq = 11.0
            ear_amp = 0.55
            tail_freq = 9.0
            tail_amp = 0.70
            ear_len = self.body_len * 0.20
            tail_len = self.body_len * 0.24
            ear_base = math.pi
        elif state == "idle":
            # Very slow, gentle ear/tail motion.
            ear_freq = 0.7
            ear_amp = 0.12
            tail_freq = 0.5
            tail_amp = 0.18
            ear_len = self.body_len * 0.24
            tail_len = self.body_len * 0.28
            ear_base = 0.0
        else:
            # Walk / pause: active ear scanning + steady tail wag.
            ear_freq = 2.0
            ear_amp = 0.32
            tail_freq = 2.5
            tail_amp = 0.42
            ear_len = self.body_len * 0.26
            tail_len = self.body_len * 0.30
            ear_base = 0.0

        ear_swing = math.sin(t * ear_freq + phase)
        ear_root = self.img_w * 0.18
        ear_fwd = self.img_w * 0.04
        thick = max(2.0, self.img_w * 0.10)
        half = ear_len * 0.55

        for side in (-1, 1):
            # Anchor at the head, offset to the side and slightly forward.
            ax = head_x + perp_x * side * ear_root + fwd_x * ear_fwd
            ay = head_y + perp_y * side * ear_root + fwd_y * ear_fwd
            ang = heading + ear_base + side * ear_amp * ear_swing
            ex = ax + math.cos(ang) * ear_len
            ey = ay + math.sin(ang) * ear_len
            mx = (ax + ex) / 2.0
            my = (ay + ey) / 2.0
            dx = math.cos(ang) * half
            dy = math.sin(ang) * half
            px = math.cos(ang + math.pi / 2.0) * thick / 2.0
            py = math.sin(ang + math.pi / 2.0) * thick / 2.0
            pts = [mx - dx - px, my - dy - py,
                   mx + dx + px, my + dy + py,
                   mx + dx - px, my + dy - py,
                   mx - dx + px, my - dy + py]
            self.canvas.coords(self.ears[0 if side < 0 else 1], *pts)

        # Tail: a wagging curve from the rear of the body.
        tail_swing = math.sin(t * tail_freq * math.tau + phase)
        pts = []
        for k in range(TAIL_SEGMENTS):
            s = k / (TAIL_SEGMENTS - 1.0)
            wag = tail_swing * tail_amp * math.sin(s * math.pi / 2.0 + 0.3)
            ang = heading + math.pi + wag
            px = tail_x + math.cos(ang) * tail_len * s
            py = tail_y + math.sin(ang) * tail_len * s
            pts.extend([px, py])
        self.canvas.coords(self.tail, *pts)

    def update(self, dt: float, mx: float, my: float):
        """Advance physics and redraw this pet."""
        self.t += dt

        dist = math.hypot(self.x - mx, self.y - my)
        self._update_state(dt, mx, my, dist)
        self._update_heading(dt, mx, my, dist)
        self._update_position(dt)
        self._draw(dt)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class RoachApp:
    """Transparent fullscreen window hosting the pets (dogs by default)."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG_COLOR)
        self.root.wm_attributes("-transparentcolor", BG_COLOR)

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{self.screen_w}x{self.screen_h}+0+0")

        self.canvas = tk.Canvas(
            self.root,
            width=self.screen_w,
            height=self.screen_h,
            bg=BG_COLOR,
            highlightthickness=0,
        )
        self.canvas.pack()

        # Procedural line-art dog sprite + empirical base-rotation verification.
        self._dog_img = get_dog_sprite("walk")
        dog_head_local = load_roach_image(self._dog_img)[1]
        dog_phi = calibrate_base_rotation(self._dog_img, dog_head_local)
        self._dog_base = (dog_phi if abs(dog_phi - BASE_ROTATION_DEG) < 5.0
                          else BASE_ROTATION_DEG)
        self._roach_path = resource_path("roach.png")
        # Classic 5-size roach spread, kept in original order for the burst.
        self._scales = SIZE_SCALES[:]

        self.pets = []
        # Start with exactly ONE slow dog (scale 1.0, near screen center).
        self.pets.append(
            self._spawn_pet(
                self.screen_w / 2.0,
                self.screen_h / 2.0,
                species="dog",
                scale=1.0,
            )
        )

        self._running = True
        self._last_time = None
        self._schedule()
        self._register_hotkey()
        self.root.mainloop()

    def _make_framesets(self, scale: float, species: str) -> Dict[str, FrameSet]:
        """Build the frame sets for a given per-pet scale and species.

        The dog gets one 72-frame set per visual pose (nested dict keyed by
        pose); the roach gets a single 72-frame set.
        """
        fs: Dict[str, FrameSet] = {}
        if species == "dog":
            dog_sets = {}
            for st in DOG_STATES:
                dog_sets[st] = build_frames(
                    get_dog_sprite(st), DOG_TARGET_HEIGHT, N_FRAMES,
                    scale, self._dog_base)
            fs["dog"] = dog_sets
            # The dog may morph to a roach on click -> ensure roach frames too.
            roach_frames, roach_size, roach_hoff = build_frames(
                self._roach_path, TARGET_HEIGHT, N_FRAMES, scale)
            fs["roach"] = (roach_frames, roach_size, roach_hoff)
        else:
            roach_frames, roach_size, roach_hoff = build_frames(
                self._roach_path, TARGET_HEIGHT, N_FRAMES, scale)
            fs["roach"] = (roach_frames, roach_size, roach_hoff)
        return fs

    def _spawn_pet(self, x: float, y: float, species: str, scale: float,
                   heading: Optional[float] = None,
                   speed: Optional[float] = None) -> "Pet":
        """Create a Pet at (x, y) with the given species/scale and return it."""
        framesets = self._make_framesets(scale, species)
        return Pet(
            self.canvas,
            framesets,
            self.screen_w,
            self.screen_h,
            self._kill,
            species=species,
            on_burst=self._burst_roaches_at,
            init_x=x,
            init_y=y,
            init_heading=heading,
            init_speed=speed,
        )

    def _burst_roaches_at(self, x: float, y: float, dog_pet: "Pet") -> None:
        """Replace the clicked dog with 5 roaches bursting out from its spot.

        The dog is removed from the canvas and the pet list, then 5 roaches are
        spawned at slightly offset positions with radial headings (classic
        ``SIZE_SCALES`` sizes, full original roach behavior preserved).
        """
        # Remove the dog's canvas items and drop it from the active list.
        try:
            self.canvas.delete(dog_pet.body_item)
        except Exception:
            pass
        dog_pet._destroy_extra_items()
        if dog_pet in self.pets:
            self.pets.remove(dog_pet)

        scales = self._scales[:5]
        n = len(scales)
        for i, scale in enumerate(scales):
            angle = (2.0 * math.pi * i / n) + random.uniform(-0.25, 0.25)
            off = random.uniform(6.0, 22.0)
            rx = x + math.cos(angle) * off
            ry = y + math.sin(angle) * off
            # Burst outward along the radial direction from the dog.
            speed = random.uniform(120.0, 200.0)
            self.pets.append(
                self._spawn_pet(rx, ry, "roach", scale,
                                heading=angle, speed=speed)
            )

    def _schedule(self):
        """Main loop called every TICK_MS milliseconds."""
        if not self._running:
            return

        now = time.perf_counter()
        if self._last_time is None:
            self._last_time = now
        dt = min(now - self._last_time, 0.05)
        self._last_time = now

        mx, my = get_global_mouse()
        for pet in self.pets:
            pet.update(dt, mx, my)

        self.root.after(TICK_MS, self._schedule)

    def _kill(self):
        """Begin application shutdown."""
        self._running = False
        self.root.after(10, self._quit)

    def _quit(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    def _register_hotkey(self):
        """Register the global exit hotkey in a background thread (pynput)."""
        combo = "<cmd>+<shift>+q" if sys.platform == "darwin" else "<ctrl>+<shift>+q"

        def worker():
            try:
                with GlobalHotKeys({combo: self._kill}) as hotkey:
                    hotkey.join()
            except Exception:
                # On macOS without Accessibility permission (or any platform
                # hiccup) the global hotkey simply will not fire; the
                # click-to-exit path still works, so we ignore the failure.
                pass

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    RoachApp()

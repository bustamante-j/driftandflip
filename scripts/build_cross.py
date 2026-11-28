"""
Turn the cross image in assets/cross/ into data for the hero's 3D cross.

  1. find the cross (alpha channel, or difference from a plain background)
  2. keep the biggest shape, fill its holes, trace the outline, simplify it
  3. write data/cross.json  (outline normalised to height 2, centred)
     + assets/generated/cross/cross-<hash>.webp  (grey detail map for the front face)

No image in the folder → data/cross.json says so and the site uses its built-in cross.

Run:  python scripts/build_cross.py
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps
# numpy / scipy / scikit-image are imported only when the cross image actually changed
# (their first import can be very slow on Windows)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cross"
OUT = ROOT / "assets" / "generated" / "cross"
DATA = ROOT / "data" / "cross.json"
EXTS = {".png", ".jpg", ".jpeg", ".webp"}
WORK = 640          # trace at this size (px, longest side)
MAX_POINTS = 360


def border_color(a):
    import numpy as np
    edge = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    return np.median(edge, axis=0)


def find_mask(im: Image.Image):
    import numpy as np
    if im.mode in ("RGBA", "LA") or "transparency" in im.info:
        alpha = np.asarray(im.convert("RGBA"))[..., 3]
        if alpha.min() < 250:
            return alpha > 127
    rgb = np.asarray(im.convert("RGB")).astype(np.int16)
    diff = np.abs(rgb - border_color(rgb)).max(axis=2)
    return diff > 40


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    files = sorted((f for f in SRC.iterdir() if f.suffix.lower() in EXTS and not f.name.startswith(".")),
                   key=lambda f: f.stat().st_mtime, reverse=True) if SRC.is_dir() else []
    poster_path = DATA.parent / "cross-poster.webp"   # flat cross shown instantly, before the 3D loads
    for old in OUT.glob("*.webp"):
        if not files:
            old.unlink()
    if not files:
        DATA.write_text(json.dumps({"shape": None}), encoding="utf-8")
        poster_path.unlink(missing_ok=True)
        print("Cross: no image in assets/cross/ -> built-in cross")
        return 0

    src = files[0]
    raw = src.read_bytes()
    digest = hashlib.sha1(raw).hexdigest()[:8]

    # unchanged since last build → nothing to do
    try:
        prev = json.loads(DATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        prev = {}
    if prev.get("hash") == digest and prev.get("detail") and (ROOT / prev["detail"]).exists() and poster_path.exists():
        print(f"Cross: {src.name} unchanged")
        return 0

    import numpy as np
    from scipy import ndimage
    from skimage import measure, morphology

    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    scale = WORK / max(im.size)
    small = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)

    mask = find_mask(small)
    mask = ndimage.binary_closing(mask, structure=morphology.disk(2))
    labels = measure.label(mask)
    if labels.max() == 0:
        print(f"Cross: couldn't find a shape in {src.name} (try a plainer background)")
        DATA.write_text(json.dumps({"shape": None}), encoding="utf-8")
        return 0
    biggest = max(measure.regionprops(labels), key=lambda r: r.area).label
    mask = ndimage.binary_fill_holes(labels == biggest)   # fill only holes enclosed by the cross

    padded = np.pad(mask, 2)
    contour = max(measure.find_contours(padded.astype(float), 0.5), key=len)
    tol = 0.6
    poly = measure.approximate_polygon(contour, tolerance=tol)
    while len(poly) > MAX_POINTS:
        tol *= 1.4
        poly = measure.approximate_polygon(contour, tolerance=tol)

    ys, xs = poly[:, 0] - 2, poly[:, 1] - 2           # (row, col) → pixel coords
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    h = y1 - y0
    pts = [[round((x - (x0 + x1) / 2) / h * 2, 4), round(-(y - (y0 + y1) / 2) / h * 2, 4)] for x, y in zip(xs, ys)]
    if pts[0] == pts[-1]:
        pts.pop()

    # detail map: the cross itself in grey, cropped to the outline, background black
    bx0, by0 = int(x0 / scale), int(y0 / scale)
    bx1, by1 = int(np.ceil(x1 / scale)), int(np.ceil(y1 / scale))
    crop = im.convert("L").crop((bx0, by0, bx1, by1))
    m = Image.fromarray((mask[int(y0):int(np.ceil(y1)), int(x0):int(np.ceil(x1))] * 255).astype(np.uint8)).resize(crop.size)
    detail = Image.composite(ImageOps.autocontrast(crop, cutoff=1), Image.new("L", crop.size, 0), m)
    detail.thumbnail((1024, 1024), Image.LANCZOS)
    tex = OUT / f"cross-{digest}.webp"
    for old in OUT.glob("*.webp"):
        if old != tex:
            old.unlink()
    detail.save(tex, "WEBP", quality=80, method=5)

    # poster: the cross itself with a transparent background, cropped to the outline
    poster = im.convert("RGBA").crop((bx0, by0, bx1, by1))
    has_alpha = np.asarray(im.convert("RGBA"))[..., 3].min() < 250
    if not has_alpha:
        poster.putalpha(m)
    poster.thumbnail((1000, 1000), Image.LANCZOS)
    poster.save(poster_path, "WEBP", quality=82, method=5)

    DATA.write_text(json.dumps({
        "source": src.name,
        "hash": digest,
        "aspect": round((x1 - x0) / h, 4),
        "shape": pts,
        "detail": tex.relative_to(ROOT).as_posix(),
    }, separators=(",", ":")), encoding="utf-8")
    print(f"Cross: traced {src.name} -> {len(pts)} points, detail map {tex.name}")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    # numpy/scipy can hang while Python shuts down on Windows — exit straight away
    import os
    os._exit(code)

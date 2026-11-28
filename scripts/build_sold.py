"""
Build the sold-out archive from photos in assets/products/sold-out/<category>/.

File name:  "Brand - Product name [Size] (2).jpg"
            brand + name required-ish, [Size] optional, (2) = extra photo of the same piece.

Outputs (both committed and served as static files):
  assets/generated/sold-out/*.webp   resized photos (600w + 1400w), EXIF/GPS stripped
  data/sold-out.json                 the list the site reads

Run:  python scripts/build_sold.py
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "products" / "sold-out"
OUT = ROOT / "assets" / "generated" / "sold-out"
DATA = ROOT / "data" / "sold-out.json"
CATS = ["shirts", "shorts", "hats"]
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
WIDTHS = [600, 1400]
BRAND_ALIASES = {
    "chrome hearts": "Chrome Hearts", "chromehearts": "Chrome Hearts", "ch": "Chrome Hearts",
    "stussy": "Stüssy", "stüssy": "Stüssy",
    "hellstar": "Hellstar",
    "bape": "BAPE", "a bathing ape": "BAPE",
}
CARD_RATIO = 4 / 5          # site cards are 4:5 (w:h)
COLLAGE_MIN = 1.6           # taller than this (h/w) = front+back stacked → split in two

NAME_RE = re.compile(r"^(?P<base>.*?)\s*(?:\[(?P<size>[^\]]+)\])?\s*(?:\((?P<n>\d+)\)|_(?P<u>\d+))?\s*$")


def tidy_brand(b: str) -> str:
    key = b.strip().lower()
    return BRAND_ALIASES.get(key, b.strip())


def parse(stem: str) -> tuple[str, str, str, int]:
    m = NAME_RE.match(stem.strip())
    base, size = m.group("base").strip(), (m.group("size") or "").strip()
    n = int(m.group("n") or m.group("u") or 1)
    if " - " in base:
        brand, name = base.split(" - ", 1)
        brand = tidy_brand(brand)
    else:
        brand, name = "", base
        low = base.lower()
        for alias, full in sorted(BRAND_ALIASES.items(), key=lambda kv: -len(kv[0])):
            if low.startswith(alias + " "):
                brand, name = full, base[len(alias):].strip()
                break
    name = re.sub(r"\s+", " ", name.replace("_", " ")).strip() or "Untitled"
    return brand, name, size, n


def slugify(s: str) -> str:
    s = s.lower().replace("ü", "u")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "item"


def border_color(im: Image.Image) -> tuple[int, int, int]:
    """Median colour of a thin frame around the photo — used to pad without visible seams."""
    w, h = im.size
    px = []
    for x in range(0, w, max(1, w // 64)):
        px += [im.getpixel((x, 2)), im.getpixel((x, h - 3))]
    for y in range(0, h, max(1, h // 64)):
        px += [im.getpixel((2, y)), im.getpixel((w - 3, y))]
    return tuple(sorted(c[i] for c in px)[len(px) // 2] for i in range(3))


def split_collage(im: Image.Image) -> list[Image.Image]:
    """A tall front-over-back collage becomes two photos: front (cover) and back (hover)."""
    if im.height / im.width < COLLAGE_MIN:
        return [im]
    half = im.height // 2
    return [im.crop((0, 0, im.width, half)), im.crop((0, half, im.width, im.height))]


def trim(im: Image.Image, margin: float = 0.04) -> Image.Image:
    """Cut away empty background around the piece so it fills more of the card."""
    bg = border_color(im)
    diff = ImageChops.difference(im, Image.new("RGB", im.size, bg)).convert("L")
    box = diff.point(lambda p: 255 if p > 28 else 0).getbbox()
    if not box:
        return im
    pad = round(max(im.size) * margin)
    l, t, r, b = box
    box = (max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad))
    return im.crop(box)


def pad_to_card(im: Image.Image) -> Image.Image:
    """Pad (never crop) to the 4:5 card shape using the photo's own background colour."""
    w, h = im.size
    if abs(w / h - CARD_RATIO) < 0.02:
        return im
    nw, nh = (w, round(w / CARD_RATIO)) if w / h > CARD_RATIO else (round(h * CARD_RATIO), h)
    canvas = Image.new("RGB", (nw, nh), border_color(im))
    canvas.paste(im, ((nw - w) // 2, (nh - h) // 2))
    return canvas


def encode(img: Image.Image, width: int, quality: int = 78) -> bytes:
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=quality, method=5)  # no exif= → metadata dropped
    return buf.getvalue()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    groups: dict[tuple, dict] = {}
    skipped: list[str] = []

    for cat in CATS:
        folder = SRC / cat
        if not folder.is_dir():
            continue
        for f in sorted(folder.iterdir()):
            if f.name.startswith(".") or not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext in {".heic", ".heif"}:
                skipped.append(f"{cat}/{f.name} (HEIC: export as JPG)")
                continue
            if ext not in EXTS:
                continue
            brand, name, size, n = parse(f.stem)
            key = (cat, brand.lower(), name.lower(), size.lower())
            g = groups.setdefault(key, {"cat": cat, "brand": brand, "name": name, "size": size, "files": [], "mtime": 0.0})
            g["files"].append((n, f))
            g["mtime"] = max(g["mtime"], f.stat().st_mtime)

    keep: set[str] = set()
    items = []
    for g in groups.values():
        slug = slugify(f"{g['brand']} {g['name']} {g['size']}")
        imgs = []
        rel = lambda p: p.relative_to(ROOT).as_posix()
        for i, (_, f) in enumerate(sorted(g["files"], key=lambda t: (t[0], t[1].name)), start=1):
            raw = f.read_bytes()
            digest = hashlib.sha1(raw).hexdigest()[:8]
            try:
                with Image.open(io.BytesIO(raw)) as src:
                    src = ImageOps.exif_transpose(src).convert("RGB")
                    for part, im in enumerate(split_collage(src), start=1):
                        im = pad_to_card(trim(im))
                        # every standard width smaller than the photo, plus the photo's own width (max 1400)
                        widths = sorted({w for w in WIDTHS if w < im.width} | {min(im.width, WIDTHS[-1])})
                        srcset = []
                        for w in widths:
                            out = OUT / f"{slug}-{i}{'abcd'[part - 1]}-{digest}-t-{w}.webp"   # "t" = trimmed framing
                            keep.add(out.name)
                            if not out.exists():
                                out.write_bytes(encode(im, w))
                            srcset.append((w, out))
                        tiny = encode(im, 16, quality=40)
                        imgs.append({
                            "url": rel(srcset[-1][1]),
                            "srcset": ", ".join(f"{rel(p)} {w}w" for w, p in srcset),
                            "lqip": "data:image/webp;base64," + base64.b64encode(tiny).decode(),
                        })
            except Exception as e:  # unreadable / corrupt file
                skipped.append(f"{g['cat']}/{f.name} ({e.__class__.__name__})")
                continue
        if not imgs:
            continue
        items.append({
            "id": f"sold-{slug}",
            "brand": g["brand"],
            "name": g["name"],
            "cat": g["cat"],
            "size": g["size"],
            "status": "sold",
            "created": datetime.fromtimestamp(g["mtime"], timezone.utc).isoformat(),
            "imgs": imgs,
        })

    # remove generated files whose source photo is gone or changed
    for old in OUT.glob("*.webp"):
        if old.name not in keep:
            old.unlink()

    items.sort(key=lambda it: it["created"], reverse=True)
    DATA.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Sold-out archive: {len(items)} piece(s), {sum(len(i['imgs']) for i in items)} photo(s) -> {DATA.relative_to(ROOT).as_posix()}")
    for s in skipped:
        print("  skipped:", s)
    return 0


if __name__ == "__main__":
    sys.exit(main())

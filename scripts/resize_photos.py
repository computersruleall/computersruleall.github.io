#!/usr/bin/env python3
"""
Generate thumb/ (300w) and med/ (1200w) variants of every photo referenced
in index.html's markersData block. Originals are left untouched.

Run from repo root: python3 scripts/resize_photos.py
"""

import os
import re
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
THUMB_DIR = ROOT / "thumb"
MED_DIR = ROOT / "med"

THUMB_WIDTH = 300
MED_WIDTH = 1200
THUMB_QUALITY = 78
MED_QUALITY = 82


def photos_from_markers():
    text = INDEX.read_text()
    return sorted(set(re.findall(r'image:\s*"([^"]+\.(?:jpg|jpeg|png|gif))"', text, re.IGNORECASE)))


def resize_one(src: Path, dst: Path, width: int, quality: int) -> None:
    # Photo content compresses far better as JPEG. Force JPEG output for all
    # variants (even for source PNGs) so we don't ship 2.5 MB PNG "thumbnails".
    if dst.suffix.lower() != ".jpg":
        dst = dst.with_suffix(".jpg")
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return
    with Image.open(src) as img:
        if img.mode not in ("RGB",):
            img = img.convert("RGB")
        w, h = img.size
        if w <= width:
            resized = img.copy()
        else:
            new_h = int(h * (width / w))
            resized = img.resize((width, new_h), Image.LANCZOS)
        resized.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)


def main() -> int:
    THUMB_DIR.mkdir(exist_ok=True)
    MED_DIR.mkdir(exist_ok=True)

    photos = photos_from_markers()
    if not photos:
        print("No photos found in markersData.", file=sys.stderr)
        return 1

    total_orig = 0
    total_thumb = 0
    total_med = 0

    for name in photos:
        src = ROOT / name
        if not src.exists():
            print(f"MISSING: {name}", file=sys.stderr)
            continue
        # All variants land as .jpg regardless of source extension.
        stem = Path(name).with_suffix(".jpg").name
        thumb = THUMB_DIR / stem
        med = MED_DIR / stem
        resize_one(src, thumb, THUMB_WIDTH, THUMB_QUALITY)
        resize_one(src, med, MED_WIDTH, MED_QUALITY)
        so, st, sm = src.stat().st_size, thumb.stat().st_size, med.stat().st_size
        total_orig += so
        total_thumb += st
        total_med += sm
        print(f"{name:30s}  orig {so//1024:>6d}KB  med {sm//1024:>5d}KB  thumb {st//1024:>4d}KB")

    def mb(n): return f"{n/1024/1024:.1f} MB"
    print()
    print(f"Total: orig {mb(total_orig)}  med {mb(total_med)}  thumb {mb(total_thumb)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

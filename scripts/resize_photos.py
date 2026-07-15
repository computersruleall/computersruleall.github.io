#!/usr/bin/env python3
"""
Photo variant generator for computersruleall.github.io.

For every image (.jpg / .jpeg / .png) sitting in the repo root, this script
produces two smaller siblings so the site never ships a multi-megabyte
original to a mobile visitor:

    thumb/<name>.jpg   ~300 px wide, ~15 - 30 KB   (used inline in info-boxes)
    med/<name>.jpg    ~1200 px wide, ~150 - 350 KB (used at high DPR / larger cards)

Full-resolution originals are still fetched — but ONLY when the user
clicks a thumbnail to open the full-screen viewer. index.html wires this
via a data-full attribute on each info-box <img>.

WHY the outputs are always .jpg
    PNG compresses photographic content very poorly (a 7 MB PNG can shrink
    to 300 KB as JPEG). Even if the source is a PNG, the derived variants
    are JPEG. The full-size original is left alone so PNG transparency,
    if it matters for a specific asset, is preserved for the enlarge view.

WHY auto-discover instead of parsing markersData
    Two failure modes to avoid for a contributor:
      1. Add a photo to the repo but forget to reference it — no variants
         are ever generated (previous behavior).
      2. Add the entry to markersData first, before uploading the image —
         script fails ("MISSING: foo.jpg").
    Auto-discovery means "drop the file into the repo and everything else
    is automatic." The GitHub Action leans on this.

WHY we prune orphan variants
    If a source image is removed, the previously-generated thumb/ and med/
    variants would linger forever. We delete any variant whose source is
    no longer present so the repo stays tidy.

WHY .gif is excluded
    Converting a GIF to JPEG flattens the animation down to a single frame,
    which is almost never what you want. If a GIF is used inline on a page,
    reference it at full size — this pipeline won't touch it.

Idempotent: if a variant already exists and its mtime is newer than the
source, we skip it. Safe to run on every push.
"""

import os
import sys
from pathlib import Path
from PIL import Image

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
THUMB_DIR = ROOT / "thumb"
MED_DIR = ROOT / "med"

# 300 px is enough for a 3x-DPR phone displaying an ~80vw info-box card;
# any larger and we waste bytes on the initial page load.
THUMB_WIDTH = 300

# 1200 px covers the info-box on desktop and a full-screen preview on
# a 3x-DPR phone before the user pinch-zooms. Beyond this, the user is
# clicking to enlarge and the original file is served instead.
MED_WIDTH = 1200

# Quality tuning — visually indistinguishable from higher settings at
# these resolutions but with substantially smaller files.
THUMB_QUALITY = 78
MED_QUALITY = 82

# Extensions considered "source photos" living at repo root.
SOURCE_EXTS = {".jpg", ".jpeg", ".png"}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def discover_sources() -> list:
    """
    Return every candidate source photo in the repo root, sorted so the
    per-run log output is stable (helpful when reading Actions logs).
    """
    sources = []
    for p in ROOT.iterdir():
        # Skip anything not a plain file (dirs like thumb/, med/, scripts/).
        if not p.is_file():
            continue
        if p.suffix.lower() in SOURCE_EXTS:
            sources.append(p)
    return sorted(sources, key=lambda x: x.name.lower())


def variant_path(src: Path, variant_dir: Path) -> Path:
    """
    Where should the resized copy of `src` live inside `variant_dir`?
    Regardless of source extension, output filename is `<stem>.jpg`.
    """
    return variant_dir / (src.stem + ".jpg")


def resize_one(src: Path, dst: Path, width: int, quality: int) -> bool:
    """
    Write a JPEG copy of `src` at `dst`, resized to `width` px wide (if the
    source is that wide; smaller sources are copied at original size to
    avoid upscaling artifacts). Returns True if the file was (re)written.
    """
    # If the destination is fresh (mtime >= source mtime), assume it's up
    # to date. Cheap idempotency: subsequent runs skip untouched photos.
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return False

    with Image.open(src) as img:
        # JPEG can't hold alpha channel — convert to RGB. PIL's default
        # mode conversion drops transparency to opaque black; that's fine
        # for typical photos (which are RGB anyway). If we ever ship a
        # PNG with meaningful transparency, we'd need to flatten to white
        # explicitly here.
        if img.mode != "RGB":
            img = img.convert("RGB")

        w, h = img.size
        if w <= width:
            # Don't upscale — a 250 px original stays 250 px.
            resized = img.copy()
        else:
            # Preserve aspect ratio. Lanczos is the highest-quality
            # downscaling filter PIL offers.
            new_h = int(h * (width / w))
            resized = img.resize((width, new_h), Image.LANCZOS)

        resized.save(
            dst,
            "JPEG",
            quality=quality,
            # optimize=True runs a second pass to squeeze out a bit more
            # (~5% smaller on average) at the cost of encode time — cheap
            # for one-shot batches like ours.
            optimize=True,
            # progressive=True yields a JPEG that renders top-down in
            # multiple passes on slow connections — feels faster on mobile
            # even though total bytes are similar.
            progressive=True,
        )
    return True


def prune_orphans(source_stems, variant_dir: Path) -> list:
    """
    Delete variants whose source photo no longer exists in the repo root.
    Returns a list of paths removed (for logging).
    """
    if not variant_dir.exists():
        return []
    removed = []
    for p in variant_dir.iterdir():
        if not p.is_file():
            continue
        # A variant's stem should match a source's stem. If not, orphan.
        if p.stem not in source_stems:
            p.unlink()
            removed.append(p)
    return removed


def human_size(n_bytes: int) -> str:
    """Format a byte count as a human string."""
    if n_bytes >= 1024 * 1024:
        return f"{n_bytes / 1024 / 1024:.1f} MB"
    return f"{n_bytes / 1024:.0f} KB"


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main() -> int:
    THUMB_DIR.mkdir(exist_ok=True)
    MED_DIR.mkdir(exist_ok=True)

    sources = discover_sources()
    if not sources:
        # Not an error — just nothing to do. The GitHub Action can then
        # short-circuit without failing.
        print("No source images at repo root.")
        return 0

    # Track running totals purely for the summary line.
    total_orig = 0
    total_thumb = 0
    total_med = 0
    generated = 0
    skipped = 0

    for src in sources:
        thumb = variant_path(src, THUMB_DIR)
        med = variant_path(src, MED_DIR)

        # resize_one returns True when it actually wrote a file; we count
        # generated vs. skipped so the summary shows how much work was done.
        wrote_t = resize_one(src, thumb, THUMB_WIDTH, THUMB_QUALITY)
        wrote_m = resize_one(src, med, MED_WIDTH, MED_QUALITY)
        if wrote_t or wrote_m:
            generated += 1
        else:
            skipped += 1

        so = src.stat().st_size
        st = thumb.stat().st_size
        sm = med.stat().st_size
        total_orig += so
        total_thumb += st
        total_med += sm

        tag = "GENERATED" if (wrote_t or wrote_m) else "up-to-date"
        print(
            f"{src.name:30s}  orig {so//1024:>6d}KB  "
            f"med {sm//1024:>5d}KB  thumb {st//1024:>4d}KB  [{tag}]"
        )

    # Cleanup: any variant whose source photo has been deleted.
    source_stems = {s.stem for s in sources}
    removed = prune_orphans(source_stems, THUMB_DIR)
    removed += prune_orphans(source_stems, MED_DIR)
    for p in removed:
        print(f"Pruned orphan variant: {p.relative_to(ROOT)}")

    print()
    print(
        f"Summary: {generated} regenerated, {skipped} up-to-date, "
        f"{len(removed)} orphans removed. "
        f"Total bytes: orig {human_size(total_orig)}  "
        f"med {human_size(total_med)}  "
        f"thumb {human_size(total_thumb)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

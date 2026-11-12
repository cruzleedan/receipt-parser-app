"""WORK-0009: unpack a receipt-photo archive, normalise to JPEG and drop duplicates.

  python -I bench/prepare_images.py ARCHIVE.zip OUT_DIR

Writes OUT_DIR/images/rNNN.jpg (long side at most 2000 px) and OUT_DIR/manifest.json
(id -> original name, plus every dropped duplicate and unreadable file with its reason).
Duplicates: identical bytes (SHA-256) only. A perceptual-hash pass was tried and removed: on
long white receipts photographed on the same background it matched different receipts (8 of 8
sampled pairs). Re-photographed receipts are found later from the models' answers
(same merchant, date and total; see consistency.py). Archive member paths are never used as
filesystem paths; members are read in memory.
"""

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # HEIC files are then reported as unreadable
    pass

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".bmp", ".tif", ".tiff"}
MAX_MEMBER = 60 * 1024 * 1024


def main(archive: str, out: str) -> int:
    out_dir = Path(out)
    img_dir = out_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    kept, dropped, seen_sha = [], [], {}
    with zipfile.ZipFile(archive) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        for m in sorted(members, key=lambda m: m.filename):
            ext = Path(m.filename).suffix.lower()
            if ext not in IMAGE_EXT:
                dropped.append({"name": m.filename, "reason": f"not an image ({ext or 'no extension'})"})
                continue
            if m.file_size > MAX_MEMBER:
                dropped.append({"name": m.filename, "reason": "larger than 60 MB"})
                continue
            data = z.read(m)
            sha = hashlib.sha256(data).hexdigest()
            if sha in seen_sha:
                dropped.append({"name": m.filename, "reason": f"same bytes as {seen_sha[sha]}"})
                continue
            seen_sha[sha] = m.filename
            try:
                img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
            except Exception as e:
                dropped.append({"name": m.filename, "reason": f"unreadable: {type(e).__name__}"})
                continue
            pixels = img.width * img.height
            img.thumbnail((2000, 2000))
            tmp = img_dir / f"tmp-{sha[:16]}.jpg"
            img.save(tmp, format="JPEG", quality=92)
            kept.append({"name": m.filename, "tmp": tmp, "pixels": pixels})
            img.close()

    unique = kept

    manifest = {"images": {}, "dropped": dropped}
    for i, u in enumerate(sorted(unique, key=lambda u: u["name"])):
        rid = f"r{i:03d}"
        u["tmp"].rename(img_dir / f"{rid}.jpg")
        manifest["images"][rid] = u["name"]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    reasons = {}
    for d in dropped:
        key = d["reason"].split(" as ")[0].split(":")[0]
        reasons[key] = reasons.get(key, 0) + 1
    print(f"members {len(members)}, unique images {len(unique)}, dropped {len(dropped)}: {reasons}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

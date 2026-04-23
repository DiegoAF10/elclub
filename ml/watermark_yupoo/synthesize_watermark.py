"""Generador sintético del watermark Yupoo sobre fotos limpias.

Produce pares (clean, watermarked) para training del U-Net especializado.
Usa el template PNG ya extraído en `erp/assets/watermark-template.png` y
aplica variaciones aleatorias de opacity/escala/rotación/spacing para
cubrir toda la distribución de watermarks vistos en el wild.

Usage:
    # Single image
    python synthesize_watermark.py --input clean.jpg --output pair/

    # Batch: procesa toda data/clean/ y escribe a data/pairs/
    python synthesize_watermark.py --batch --variations 5

Cada foto limpia genera N variaciones (default 5), cada una con:
  - opacity: 0.15-0.30
  - scale: 0.8-1.3
  - rotation: -20° a -10° (Yupoo es diagonal, rango estrecho)
  - spacing: 150-300 px entre tiles
  - offset: random para no siempre alinear igual
"""
import argparse
import os
import random
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT.parent.parent / "erp" / "assets" / "watermark-template.png"
CLEAN_DIR = ROOT / "data" / "clean"
PAIRS_DIR = ROOT / "data" / "pairs"


def _load_template():
    if not TEMPLATE_PATH.exists():
        print(f"[FATAL] Template no existe en {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)
    tpl = Image.open(TEMPLATE_PATH).convert("RGBA")
    return tpl


def apply_watermark(
    clean_img: Image.Image,
    template: Image.Image,
    opacity: float = None,
    scale: float = None,
    rotation: float = None,
    spacing: int = None,
    offset_x: int = None,
    offset_y: int = None,
    seed: int = None,
) -> Image.Image:
    """Aplica el watermark Yupoo tileado diagonal sobre clean_img.

    Todos los parámetros son random por default dentro de rangos empíricos
    observados en fotos reales de Yupoo. Pasalos explícitos para reproducibility
    en testing.
    """
    if seed is not None:
        random.seed(seed)
    opacity = opacity if opacity is not None else random.uniform(0.15, 0.30)
    scale = scale if scale is not None else random.uniform(0.8, 1.3)
    rotation = rotation if rotation is not None else random.uniform(-20, -10)
    spacing = spacing if spacing is not None else random.randint(150, 300)
    offset_x = offset_x if offset_x is not None else random.randint(0, spacing)
    offset_y = offset_y if offset_y is not None else random.randint(0, spacing)

    clean = clean_img.convert("RGBA")
    W, H = clean.size

    # Escalar template
    tw = int(template.width * scale)
    th = int(template.height * scale)
    tile = template.resize((tw, th), Image.LANCZOS)

    # Aplicar opacity al alpha del tile
    alpha = tile.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity * 3.5)  # factor empírico
    tile.putalpha(alpha)

    # Overlay layer con tiles rotados
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Rotate tile
    rotated = tile.rotate(rotation, resample=Image.BICUBIC, expand=True)
    rw, rh = rotated.size

    # Tile diagonal: pasos en X e Y con spacing
    x_step = spacing
    y_step = spacing

    # Cobertura: empezar fuera del canvas para cubrir bordes
    for y in range(-rh + offset_y, H + rh, y_step):
        for x in range(-rw + offset_x, W + rw, x_step):
            overlay.alpha_composite(rotated, (x, y))

    # Compose
    result = Image.alpha_composite(clean, overlay).convert("RGB")
    return result


def batch_synthesize(variations: int = 5, limit: int = None):
    """Procesa todas las imágenes en data/clean/, genera N variations por cada
    una, escribe pares a data/pairs/."""
    template = _load_template()
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)

    clean_files = sorted([
        p for p in CLEAN_DIR.iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    ])
    if limit:
        clean_files = clean_files[:limit]

    if not clean_files:
        print(f"[WARN] data/clean/ vacía. Llená {CLEAN_DIR} con fotos limpias "
              f"(ver DATA_COLLECTION.md)")
        return

    total = len(clean_files) * variations
    done = 0
    for clean_path in clean_files:
        try:
            clean_img = Image.open(clean_path).convert("RGB")
        except Exception as e:
            print(f"[SKIP] {clean_path.name}: {e}")
            continue

        base_id = clean_path.stem
        for v in range(variations):
            wm_img = apply_watermark(clean_img, template)
            pair_dir = PAIRS_DIR / f"{base_id}_v{v}"
            pair_dir.mkdir(exist_ok=True)
            clean_img.save(pair_dir / "clean.jpg", quality=92)
            wm_img.save(pair_dir / "wm.jpg", quality=92)
            done += 1
            if done % 50 == 0:
                print(f"[{done}/{total}] {base_id}_v{v}")

    print(f"DONE: {done} pairs escritos a {PAIRS_DIR}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=str, help="Single clean image path")
    ap.add_argument("--output", type=str, default=".", help="Output dir")
    ap.add_argument("--batch", action="store_true",
                    help="Batch mode: procesa todo data/clean/")
    ap.add_argument("--variations", type=int, default=5,
                    help="Pares sintéticos por foto limpia (default 5)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Max fotos clean a procesar (smoke test)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    if args.batch:
        batch_synthesize(variations=args.variations, limit=args.limit)
        return

    if not args.input:
        ap.error("--input o --batch requerido")

    template = _load_template()
    clean_img = Image.open(args.input).convert("RGB")
    wm_img = apply_watermark(clean_img, template, seed=args.seed)

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem
    clean_img.save(out_dir / f"{stem}_clean.jpg", quality=92)
    wm_img.save(out_dir / f"{stem}_wm.jpg", quality=92)
    print(f"OK: {stem}_clean.jpg + {stem}_wm.jpg en {out_dir}")


if __name__ == "__main__":
    main()

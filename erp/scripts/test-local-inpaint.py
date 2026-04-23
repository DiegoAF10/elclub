"""Ops s14o — test local de watermark removal con IOPaint (LaMa) + EasyOCR."""
import os
# Fix cp1252 crash en Windows al printear progress bars de easyocr
os.environ["PYTHONIOENCODING"] = "utf-8"
import sys
if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import cv2
import numpy as np
import requests
import subprocess
from pathlib import Path

OUT = Path("C:/Users/Diego/local-inpaint-test")
OUT.mkdir(parents=True, exist_ok=True)

# Fotos de test — una con watermark clarito
TEST_URLS = [
    ("arg-v-fs-idx3", "https://img.elclub.club/families/argentina-2026-away/m2/04.jpg"),
    ("arg-v-ps-idx5", "https://img.elclub.club/families/argentina-2026-away/m1/06.jpg"),
    ("arg-v-w-idx4", "https://img.elclub.club/families/argentina-2026-away/m3/05.jpg"),
]

WATERMARK_KEYWORDS = ("minkang", "yupoo", "com", "x.", ".x.")


def download(url, path):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    path.write_bytes(r.content)


def _merge_horizontal_line(boxes, y_tolerance=30):
    """Agrupa boxes por línea horizontal (y_center similar) y retorna 1 rect
    unificado por grupo que cubre desde x_min del primero hasta x_max del último.
    Eso rellena gaps entre palabras (ej. el 'x.' entre 'minkang' y 'yupoo' que
    EasyOCR a veces no detecta por ser chars aislados).
    """
    if not boxes:
        return []
    # Sort por y_center
    sorted_boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    groups = [[sorted_boxes[0]]]
    for b in sorted_boxes[1:]:
        y_center = (b[1] + b[3]) / 2
        last_group_y = sum((bb[1] + bb[3]) / 2 for bb in groups[-1]) / len(groups[-1])
        if abs(y_center - last_group_y) < y_tolerance:
            groups[-1].append(b)
        else:
            groups.append([b])
    # Unificar cada grupo en 1 rect
    unified = []
    for g in groups:
        x_min = min(b[0] for b in g)
        y_min = min(b[1] for b in g)
        x_max = max(b[2] for b in g)
        y_max = max(b[3] for b in g)
        unified.append((x_min, y_min, x_max, y_max, len(g)))
    return unified


def detect_watermark_mask(img_path, reader, dilate_x=20, dilate_y=4):
    """Corre EasyOCR, filtra boxes con keywords watermark, y agrupa por línea
    horizontal para generar mask que cubre el watermark completo (incluido
    'x.' y separadores que EasyOCR puede saltar).

    Dilate asimétrico: +20px horizontal (cubre edges + gaps entre palabras) +
    4px vertical (suficiente para edges de text pero NO toca logos/texto
    adjacente como '°CLIMACOOL' arriba del watermark)."""
    img = cv2.imread(str(img_path))
    h, w = img.shape[:2]

    results = reader.readtext(str(img_path))
    raw_boxes = []  # (x_min, y_min, x_max, y_max)
    matched_info = []
    for bbox, text, conf in results:
        txt_lower = text.lower()
        if any(kw in txt_lower for kw in WATERMARK_KEYWORDS):
            pts = np.array(bbox, dtype=np.int32)
            x_min = int(pts[:, 0].min())
            y_min = int(pts[:, 1].min())
            x_max = int(pts[:, 0].max())
            y_max = int(pts[:, 1].max())
            raw_boxes.append((x_min, y_min, x_max, y_max))
            matched_info.append((text, conf, (x_min, y_min, x_max, y_max)))

    # Unificar boxes en misma línea horizontal → cubre el "x." entre palabras
    merged = _merge_horizontal_line(raw_boxes, y_tolerance=30)

    mask = np.zeros((h, w), dtype=np.uint8)
    for x_min, y_min, x_max, y_max, n_words in merged:
        # Dilate asimétrico
        x_min = max(0, x_min - dilate_x)
        y_min = max(0, y_min - dilate_y)
        x_max = min(w, x_max + dilate_x)
        y_max = min(h, y_max + dilate_y)
        cv2.rectangle(mask, (x_min, y_min), (x_max, y_max), 255, -1)

    return mask, matched_info, merged


_LAMA_MODEL = None


def _run_lama(img_path, mask_path):
    """Run LaMa inpainting via iopaint Python API. Lazy-init del modelo."""
    global _LAMA_MODEL
    import numpy as np
    from PIL import Image
    if _LAMA_MODEL is None:
        from iopaint.model_manager import ModelManager
        from iopaint.schema import ApiConfig, ModelInfo
        print("  Loading LaMa model to GPU (first run only)...")
        _LAMA_MODEL = ModelManager(name="lama", device="cuda")

    # Load img as RGB numpy
    img = np.array(Image.open(str(img_path)).convert("RGB"))
    # Load mask as grayscale
    mask = np.array(Image.open(str(mask_path)).convert("L"))

    # Build request
    from iopaint.schema import InpaintRequest
    req = InpaintRequest()
    result = _LAMA_MODEL(img, mask, req)
    # result is numpy BGR per iopaint convention; convert to BGR for cv2.imwrite
    # Actually iopaint's ModelManager returns numpy array in BGR
    return result


def main():
    import easyocr
    print("Loading EasyOCR (first run descarga modelos ~500MB)...")
    reader = easyocr.Reader(["en"], gpu=True)  # English suffices for "minkang.x.yupoo.com"
    print("OCR ready.\n")

    for name, url in TEST_URLS:
        print(f"=== {name} ===")
        in_path = OUT / f"{name}-input.jpg"
        mask_path = OUT / f"{name}-mask.png"
        try:
            download(url, in_path)
            print(f"  Downloaded {in_path.stat().st_size // 1024}KB")
        except Exception as e:
            print(f"  DL fail: {e}")
            continue

        mask, boxes, merged = detect_watermark_mask(in_path, reader)
        print(f"  OCR matched {len(boxes)} watermark fragments → {len(merged)} line groups:")
        for text, conf, bbox in boxes:
            print(f"    text='{text}' conf={conf:.2f} bbox={bbox}")
        for x_min, y_min, x_max, y_max, n in merged:
            print(f"    merged rect {n} words: ({x_min},{y_min})-({x_max},{y_max}) w={x_max-x_min} h={y_max-y_min}")
        if not boxes:
            print("  ⚠️ no watermark text detected — mask vacía, skip LaMa")
            cv2.imwrite(str(mask_path), mask)
            continue
        cv2.imwrite(str(mask_path), mask)
        print(f"  Mask saved: {mask_path}")

        # LaMa inpainting vía Python API (subprocess con CLI tenía encoding issues
        # en stderr Windows cp1252 → capture fallaba con UnicodeDecodeError).
        out_path = OUT / f"{name}-lama-out.png"
        import time
        t0 = time.time()
        try:
            result_img = _run_lama(in_path, mask_path)
            cv2.imwrite(str(out_path), result_img)
            print(f"  LaMa OK ({time.time()-t0:.1f}s) → {out_path}")
        except Exception as e:
            print(f"  LaMa FAIL: {type(e).__name__}: {e}")
            continue

        print()

    print(f"\nDone. Open {OUT} y compará {{name}}-input.jpg vs {{name}}-lama-out.png")


if __name__ == "__main__":
    main()

"""Local watermark inpaint pipeline — EasyOCR (detect) + IOPaint LaMa (fill).

Drop-in replacement para audit_enrich.gemini_regen_image(prompt_variant='watermark').
Ventajas vs Gemini:
- $0 per foto (local, no API)
- 0.7s post-model-load en GPU (10x más rápido que Gemini ~10-15s)
- Determinístico (mismo input → mismo output)
- Preserva el resto de la imagen (LaMa solo fill bajo la mask; Gemini re-genera todo)

Singleton pattern: EasyOCR + LaMa models se cargan una vez y se mantienen en GPU.

Usage:
    from local_inpaint import watermark_inpaint_bytes, local_inpaint_available
    if local_inpaint_available():
        r = watermark_inpaint_bytes(image_bytes)
        if r["ok"] and not r.get("skipped"):
            # r["image_bytes"] tiene la imagen limpia
            ...
"""
import cv2
import numpy as np
from PIL import Image
import io

_LAMA = None
_OCR = None

# Keywords del watermark Yupoo del proveedor "minkang.x.yupoo.com"
WATERMARK_KEYWORDS = ("minkang", "yupoo", "com", "x.", ".x.")


def local_inpaint_available():
    """True si torch+CUDA funcionan + modelos necesarios disponibles."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False
    except ImportError:
        return False
    try:
        import easyocr  # noqa: F401
        from iopaint.model_manager import ModelManager  # noqa: F401
    except ImportError:
        return False
    return True


def _get_ocr():
    global _OCR
    if _OCR is None:
        import easyocr
        _OCR = easyocr.Reader(["en"], gpu=True, verbose=False)
    return _OCR


def _get_lama():
    global _LAMA
    if _LAMA is None:
        from iopaint.model_manager import ModelManager
        _LAMA = ModelManager(name="lama", device="cuda")
    return _LAMA


def _merge_horizontal_line(boxes, y_tolerance=30):
    """Agrupa boxes por línea horizontal y unifica en 1 rect por grupo.
    Cubre gaps entre palabras detectadas (ej. 'x.' entre 'minkang' y 'yupoo')."""
    if not boxes:
        return []
    sorted_boxes = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)
    groups = [[sorted_boxes[0]]]
    for b in sorted_boxes[1:]:
        y_center = (b[1] + b[3]) / 2
        last_y = sum((bb[1] + bb[3]) / 2 for bb in groups[-1]) / len(groups[-1])
        if abs(y_center - last_y) < y_tolerance:
            groups[-1].append(b)
        else:
            groups.append([b])
    unified = []
    for g in groups:
        unified.append((
            min(b[0] for b in g),
            min(b[1] for b in g),
            max(b[2] for b in g),
            max(b[3] for b in g),
        ))
    return unified


def _detect_watermark_mask(img_bgr, dilate_x=20, dilate_y=4):
    """Retorna (mask_uint8, matched_info_list). mask es None si no hay watermark.

    Dilate asimétrico: +20px horizontal cubre edges + gap 'x.', +4px vertical
    evita tocar texto adjacente como '°CLIMACOOL' arriba del watermark."""
    h, w = img_bgr.shape[:2]
    reader = _get_ocr()
    # easyocr acepta numpy array BGR directamente
    results = reader.readtext(img_bgr)

    raw_boxes = []
    matched = []
    for bbox, text, conf in results:
        txt_lower = text.lower()
        if any(kw in txt_lower for kw in WATERMARK_KEYWORDS):
            pts = np.array(bbox, dtype=np.int32)
            x_min = int(pts[:, 0].min())
            y_min = int(pts[:, 1].min())
            x_max = int(pts[:, 0].max())
            y_max = int(pts[:, 1].max())
            raw_boxes.append((x_min, y_min, x_max, y_max))
            matched.append({"text": text, "conf": float(conf),
                            "bbox": (x_min, y_min, x_max, y_max)})

    if not raw_boxes:
        return None, []

    merged = _merge_horizontal_line(raw_boxes, y_tolerance=30)
    mask = np.zeros((h, w), dtype=np.uint8)
    for x_min, y_min, x_max, y_max in merged:
        x_min = max(0, x_min - dilate_x)
        y_min = max(0, y_min - dilate_y)
        x_max = min(w, x_max + dilate_x)
        y_max = min(h, y_max + dilate_y)
        cv2.rectangle(mask, (x_min, y_min), (x_max, y_max), 255, -1)

    return mask, matched


def force_inpaint_center_bytes(image_bytes, mime_type="image/jpeg",
                                 width_ratio=0.66, height_ratio=0.09,
                                 y_center_ratio=0.54,
                                 family_id=None, photo_index=None):
    """Override manual: aplica LaMa con mask HARDCODED centrada horizontalmente,
    posición vertical configurable. Usar cuando OCR no detecta el watermark
    pero Diego sabe que está (tipo 'Forzar inpaint').

    Watermark Yupoo estándar:
      - width ≈ 66% del image width (configurable)
      - height ≈ 9% del image height (configurable)
      - horizontally centered
      - vertically ~54% (slightly below middle) — configurable via y_center_ratio

    Returns: mismo interface que watermark_inpaint_bytes.
    """
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return {"ok": False, "error": "invalid image bytes"}
    except Exception as e:
        return {"ok": False, "error": f"decode: {type(e).__name__}: {e}"}

    h, w = img_bgr.shape[:2]
    mask_w = int(w * width_ratio)
    mask_h = int(h * height_ratio)
    cx = w // 2
    cy = int(h * y_center_ratio)
    x_min = max(0, cx - mask_w // 2)
    y_min = max(0, cy - mask_h // 2)
    x_max = min(w, cx + mask_w // 2)
    y_max = min(h, cy + mask_h // 2)

    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (x_min, y_min), (x_max, y_max), 255, -1)

    try:
        lama = _get_lama()
        from iopaint.schema import InpaintRequest
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        result = lama(img_rgb, mask, InpaintRequest())
        if result.dtype != np.uint8:
            result = np.clip(result, 0, 255).astype(np.uint8)
    except Exception as e:
        return {"ok": False, "error": f"LaMa: {type(e).__name__}: {e}"}

    try:
        success, encoded = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not success:
            return {"ok": False, "error": "JPEG encode failed"}
    except Exception as e:
        return {"ok": False, "error": f"encode: {type(e).__name__}: {e}"}

    return {
        "ok": True,
        "image_bytes": bytes(encoded),
        "mime_type": "image/jpeg",
        "forced_mask": {"x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max},
    }


def watermark_inpaint_bytes(image_bytes, mime_type="image/jpeg",
                              prompt_variant="watermark",
                              family_id=None, photo_index=None):
    """Drop-in replacement de audit_enrich.gemini_regen_image para watermark.

    Returns:
      {
        "ok": bool,
        "image_bytes": bytes (PNG/JPG limpio, o el original si skipped),
        "mime_type": str,
        "skipped": optional str ("no_watermark_detected"),
        "matched_fragments": list[dict] (OCR detections),
        "error": optional str,
      }

    `prompt_variant` se ignora (LaMa solo hace inpaint, no quality regen).
    `family_id` + `photo_index` usados solo para logging.
    """
    # Decode bytes → BGR numpy
    try:
        img_array = np.frombuffer(image_bytes, np.uint8)
        img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return {"ok": False, "error": "invalid image bytes (decode failed)"}
    except Exception as e:
        return {"ok": False, "error": f"decode: {type(e).__name__}: {e}"}

    # Detect watermark
    try:
        mask, matched = _detect_watermark_mask(img_bgr)
    except Exception as e:
        return {"ok": False, "error": f"OCR: {type(e).__name__}: {e}"}

    if mask is None:
        # No watermark detected — return original
        return {
            "ok": True,
            "image_bytes": image_bytes,
            "mime_type": mime_type,
            "skipped": "no_watermark_detected",
            "matched_fragments": [],
        }

    # Run LaMa inpaint
    try:
        lama = _get_lama()
        from iopaint.schema import InpaintRequest
        # LaMa espera RGB
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        result = lama(img_rgb, mask, InpaintRequest())
        # IOPaint retorna BGR per convention
        result_bgr = result
        if result_bgr.dtype != np.uint8:
            result_bgr = np.clip(result_bgr, 0, 255).astype(np.uint8)
    except Exception as e:
        return {"ok": False, "error": f"LaMa: {type(e).__name__}: {e}"}

    # Encode back to JPEG (preserva format original, reduce filesize vs PNG)
    try:
        success, encoded = cv2.imencode(".jpg", result_bgr,
                                         [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not success:
            return {"ok": False, "error": "JPEG encode failed"}
        out_bytes = bytes(encoded)
    except Exception as e:
        return {"ok": False, "error": f"encode: {type(e).__name__}: {e}"}

    return {
        "ok": True,
        "image_bytes": out_bytes,
        "mime_type": "image/jpeg",
        "matched_fragments": matched,
    }

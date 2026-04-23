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
import os

_LAMA = None
_SD = None
_OCR = None
_TEMPLATE = None  # watermark template (grayscale) para matching

SD_MODEL_NAME = "runwayml/stable-diffusion-inpainting"
SD_DEFAULT_PROMPT = "high quality jersey photograph, preserve the jersey design and logos exactly, seamless background, no watermark, no text"
SD_DEFAULT_NEGATIVE = "watermark, text, logo overlay, minkang, yupoo, letters, typography, distortion, blurry, low quality"

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "assets", "watermark-template.png"
)

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


def _get_sd():
    """Lazy-load del modelo SD-1.5 Inpainting (~5GB). Requiere download previo:
        iopaint download --model runwayml/stable-diffusion-inpainting
    """
    global _SD
    if _SD is None:
        from iopaint.model_manager import ModelManager
        _SD = ModelManager(name=SD_MODEL_NAME, device="cuda")
    return _SD


def sd_available():
    """Chequea si SD-Inpaint model está disponible localmente."""
    try:
        from iopaint.download import scan_models
        models = scan_models()
        for m in models:
            if SD_MODEL_NAME in m.name:
                return True
    except Exception:
        pass
    return False


def sd_inpaint_bytes(image_bytes, mime_type="image/jpeg",
                     prompt=None, negative_prompt=None,
                     use_ocr_mask=True, force_mask=False,
                     family_id=None, photo_index=None):
    """SD-1.5 Inpaint con prompt. Para casos donde LaMa daña logos/texturas.

    Preserva detalles del jersey mejor que LaMa porque genera contenido nuevo
    con conocimiento visual del modelo de diffusion (5 años de training sobre
    imágenes web = entiende qué es un "jersey de fútbol con escudo").

    Args:
        use_ocr_mask: si True, detecta watermark con OCR + template (como
            watermark_inpaint_bytes). Si False, usa force_mask (hardcoded center).
        force_mask: si True + use_ocr_mask=False, usa mask hardcoded.
        prompt: prompt positivo (default: preserve jersey design).
        negative_prompt: prompt negativo (default: no watermark/text).

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

    # Generate mask
    mask = None
    if use_ocr_mask:
        mask, _ = _detect_watermark_mask(img_bgr)
        if mask is None:
            # Template match fallback
            bbox, conf = _template_match_watermark(img_bgr, threshold=0.5)
            if bbox is not None:
                mask = _pixel_precise_mask_from_bbox(img_bgr, bbox, brightness_delta=30)
                if np.count_nonzero(mask) < 100:
                    mask = None
    if mask is None and force_mask:
        # Hardcoded center mask — mismo que force_inpaint_center_bytes
        mask = np.zeros((h, w), dtype=np.uint8)
        mask_w = int(w * 0.66)
        mask_h = int(h * 0.09)
        cx, cy = w // 2, int(h * 0.54)
        x_min = max(0, cx - mask_w // 2)
        y_min = max(0, cy - mask_h // 2)
        x_max = min(w, cx + mask_w // 2)
        y_max = min(h, cy + mask_h // 2)
        cv2.rectangle(mask, (x_min, y_min), (x_max, y_max), 255, -1)

    if mask is None:
        return {"ok": True, "image_bytes": image_bytes, "mime_type": mime_type,
                "skipped": "no_watermark_detected"}

    # Run SD inpaint
    try:
        sd = _get_sd()
        from iopaint.schema import InpaintRequest
        req = InpaintRequest(
            prompt=prompt or SD_DEFAULT_PROMPT,
            negative_prompt=negative_prompt or SD_DEFAULT_NEGATIVE,
            sd_steps=25,  # default 50 — reduzco para speed (25 suele ser suficiente)
            sd_guidance_scale=7.5,
            sd_strength=1.0,
        )
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        result = sd(img_rgb, mask, req)
        if result.dtype != np.uint8:
            result = np.clip(result, 0, 255).astype(np.uint8)
    except Exception as e:
        return {"ok": False, "error": f"SD: {type(e).__name__}: {e}"}

    # Encode JPEG
    try:
        success, encoded = cv2.imencode(".jpg", result, [cv2.IMWRITE_JPEG_QUALITY, 92])
        if not success:
            return {"ok": False, "error": "JPEG encode failed"}
    except Exception as e:
        return {"ok": False, "error": f"encode: {type(e).__name__}: {e}"}

    return {"ok": True, "image_bytes": bytes(encoded), "mime_type": "image/jpeg",
            "detection_method": "sd_inpaint"}


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


def _get_template():
    global _TEMPLATE
    if _TEMPLATE is None and os.path.exists(_TEMPLATE_PATH):
        tpl_bgr = cv2.imread(_TEMPLATE_PATH)
        if tpl_bgr is not None:
            _TEMPLATE = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
    return _TEMPLATE


def _template_match_watermark(img_bgr, threshold=0.5, scales=None):
    """Busca el watermark Yupoo en `img_bgr` via multi-scale template matching.
    Funciona AÚN sobre texturas/logos porque compara glyph shapes (no readability).
    Retorna bbox (x_min, y_min, x_max, y_max) del mejor match o None.
    """
    tpl = _get_template()
    if tpl is None:
        return None, 0.0
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    img_h, img_w = img_gray.shape
    tpl_h, tpl_w = tpl.shape
    if scales is None:
        scales = [0.6, 0.75, 0.85, 0.95, 1.0, 1.05, 1.15, 1.3]

    best_conf = 0.0
    best_bbox = None
    for s in scales:
        new_w = int(tpl_w * s)
        new_h = int(tpl_h * s)
        if new_w >= img_w or new_h >= img_h or new_w < 50:
            continue
        tpl_scaled = cv2.resize(tpl, (new_w, new_h))
        res = cv2.matchTemplate(img_gray, tpl_scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best_conf:
            best_conf = max_val
            best_bbox = (max_loc[0], max_loc[1],
                         max_loc[0] + new_w, max_loc[1] + new_h)

    if best_conf < threshold:
        return None, best_conf
    return best_bbox, best_conf


def _pixel_precise_mask_from_bbox(img_bgr, bbox, brightness_delta=30):
    """Dentro del bbox detectado, genera mask solo de pixels brillantes que
    son watermark (text bright/semi-transparent sobre darker backgrounds).

    Técnica: computa la brightness media del bbox + extrae pixels que están
    N puntos por encima (semi-transparent text siempre es más bright que
    fondo promedio). Resulta mask con forma de glyphs, no rectángulo.

    Retorna mask_uint8 (mismas dims que img_bgr).
    """
    h, w = img_bgr.shape[:2]
    x_min, y_min, x_max, y_max = bbox
    x_min = max(0, x_min)
    y_min = max(0, y_min)
    x_max = min(w, x_max)
    y_max = min(h, y_max)

    mask = np.zeros((h, w), dtype=np.uint8)
    if x_max <= x_min or y_max <= y_min:
        return mask

    roi = img_bgr[y_min:y_max, x_min:x_max]
    # LAB L channel — brightness more stable to color variations
    lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0]
    # Threshold dinámico: brightness_delta por encima de la media del ROI
    mean_L = np.mean(L)
    threshold = min(255, mean_L + brightness_delta)
    _, binary = cv2.threshold(L, threshold, 255, cv2.THRESH_BINARY)

    # Morphological close para conectar glyphs cercanos + dilate ligero
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.dilate(binary, kernel, iterations=1)

    mask[y_min:y_max, x_min:x_max] = binary
    return mask


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

    # Fallback chain para detectar watermark:
    #  1. EasyOCR (current, 70% casos — fondos lisos)
    #  2. Template matching + pixel-precise mask (para watermark sobre
    #     logos/texturas — ~20% additional recovery, preserva detalles)
    detection_method = None
    matched = []
    try:
        mask, matched = _detect_watermark_mask(img_bgr)
        if mask is not None:
            detection_method = "ocr"
    except Exception as e:
        return {"ok": False, "error": f"OCR: {type(e).__name__}: {e}"}

    if mask is None:
        # Fallback: template matching sobre grayscale → encuentra pattern
        # aun cuando está sobre textura/logo. Mask resulting es pixel-precisa
        # (solo glyphs, no rectángulo) → preserva el resto de la imagen.
        try:
            bbox, conf = _template_match_watermark(img_bgr, threshold=0.5)
            if bbox is not None:
                mask = _pixel_precise_mask_from_bbox(img_bgr, bbox,
                                                     brightness_delta=30)
                # Check that mask has enough pixels (sanity) — si muy pocos,
                # probable false positive
                if np.count_nonzero(mask) > 100:
                    detection_method = f"template_match (conf={conf:.2f})"
                    matched = [{"method": "template", "bbox": bbox, "conf": conf}]
                else:
                    mask = None
        except Exception as e:
            # No fatal, continue con skip
            pass

    if mask is None:
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
        "detection_method": detection_method,
    }

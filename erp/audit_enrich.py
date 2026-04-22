"""Audit enrichment — Claude API + Gemini API integration.

Spec en elclub-catalogo-priv/docs/AUDIT-SYSTEM.md sección 7.

- Claude (claude-haiku-4-5): enriquece title/description/historia/sku/keywords
- Gemini (gemini-2.5-flash-image): inpainting de watermarks + regen calidad baja

Manejo de errores: si una API falla o la key no está seteada, degrada gracefully
(retorna dict con error=... pero no propaga excepciones).
"""

import base64
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime

# Import lazy de audit_db para log de errores (evita circular si audit_db hace import
# de este módulo en el futuro).
def _log_api_err(family_id, photo_index, api, error, attempt_n, final_failure=False):
    try:
        import audit_db
        audit_db.log_api_error(family_id, photo_index, api, error, attempt_n, final_failure)
    except Exception:
        pass  # no romper el flow por un fallo de log


# ───────────────────────────────────────────
# Lazy env loading (sin requerir python-dotenv)
# ───────────────────────────────────────────

def _load_env():
    """Carga vars de erp/.env. Si una var en os.environ está vacía o ausente,
    la sobreescribe con la del .env. Esto maneja el caso donde Claude Code
    setea ANTHROPIC_API_KEY='' globalmente.
    """
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if not k:
                    continue
                # Sobreescribe si está vacía o ausente
                if not os.environ.get(k, "").strip():
                    os.environ[k] = v
    except Exception:
        pass


_load_env()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()

CLAUDE_MODEL = "claude-haiku-4-5"
CLAUDE_MAX_TOKENS = 1500
CLAUDE_TEMPERATURE = 0.3

# Ops s11 — retry config
RETRY_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SEC = 1.0   # multiplicado por 2^(attempt-1): 1, 2, 4
CLAUDE_TIMEOUT_SEC = 30
GEMINI_TIMEOUT_SEC = 60

# Excepciones "retriables" — transient errors. Otras (e.g. permission denied,
# 400 bad request) no se retrían.
def _is_retriable(exc):
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    # Anthropic + google-genai suelen usar nombres estándar
    if any(s in name for s in ("timeout", "connection", "apierror", "apiconnectionerror",
                                "internalservererror", "overloadederror", "rateelimiterror",
                                "ratelimiterror", "serviceunavailable")):
        return True
    if any(s in msg for s in ("timeout", "timed out", "connection reset", "overloaded",
                               "rate limit", "429", "500", "502", "503", "504",
                               "temporarily unavailable")):
        return True
    return False


def _with_retry(fn, api_name, family_id=None, photo_index=None):
    """Ejecuta fn() con exponential backoff. Si todos los intentos fallan,
    registra en audit_api_errors y re-raise. Si un error NO es retriable,
    falla al primer intento pero aún loguea.

    fn: callable sin args
    api_name: 'claude' o 'gemini'
    family_id / photo_index: contexto para el log
    """
    last_exc = None
    for attempt in range(1, RETRY_MAX_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            retriable = _is_retriable(exc)
            is_final = (not retriable) or (attempt == RETRY_MAX_ATTEMPTS)
            _log_api_err(family_id, photo_index, api_name,
                         f"{type(exc).__name__}: {exc}", attempt, final_failure=is_final)
            if not retriable:
                # Error no-retriable: fallar de una
                raise
            if attempt < RETRY_MAX_ATTEMPTS:
                sleep_sec = RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1))
                time.sleep(sleep_sec)
    # Agotó todos los retries
    raise last_exc


def claude_available():
    return bool(ANTHROPIC_KEY) and ANTHROPIC_KEY.startswith("sk-ant-")


def gemini_available():
    return bool(GEMINI_KEY) and GEMINI_KEY.startswith("AIza")


# ───────────────────────────────────────────
# Claude enrichment
# ───────────────────────────────────────────

PROMPT_TEMPLATE = """Eres el editor del catálogo de El Club Vault (catálogo privado de jerseys de fútbol en Guatemala). Brand: Midnight Stadium, premium dark, voseo guatemalteco 40% educativo + 40% emocional + 20% irreverente.

Enriquece este producto con la metadata.

Input:
- family_id: {family_id}
- team: {team}
- season: {season}
- variant_label: {variant_label}
- category: {category}
- variants: {variants}
- current_title: {current_title}
- current_description: {current_description}
- current_historia: {current_historia}
- checks: {checks}
- notes: {notes}

Output EXCLUSIVAMENTE un JSON válido con este schema (sin markdown fences, sin prosa):
{{
  "title": "string pulido corto (< 60 chars)",
  "description": "2-3 oraciones, tono Midnight Stadium",
  "historia": "50-80 palabras, tono 40/40/20 voseo guatemalteco, null si current_historia ya existe",
  "sku": "identificador único generado tipo TEAM-YY-YY-TYPE-CAT",
  "keywords": ["search", "terms", "en", "espanol"],
  "similar_product_ids": [],
  "validation_issues": []
}}"""


def _build_claude_prompt(family, checks, notes):
    variants = [v.get("type") for v in (family.get("variants") or [])]
    return PROMPT_TEMPLATE.format(
        family_id=family.get("family_id", ""),
        team=family.get("team", ""),
        season=family.get("season", ""),
        variant_label=family.get("variant", ""),
        category=family.get("category", ""),
        variants=", ".join(variants) if variants else "none",
        current_title=family.get("title") or "null",
        current_description=family.get("description") or "null",
        current_historia=family.get("historia") or "null",
        checks=json.dumps(checks or {}, ensure_ascii=False),
        notes=notes or "null",
    )


def claude_enrich(family, checks=None, notes=""):
    """Llama Claude API para un family. Retorna dict con keys:
    - ok (bool)
    - data (dict enriched si ok=True)
    - error (str si ok=False)
    - raw (str respuesta raw si parse falla)
    """
    if not claude_available():
        return {"ok": False, "error": "ANTHROPIC_API_KEY no seteada o invalida"}

    try:
        from anthropic import Anthropic
    except ImportError:
        return {"ok": False, "error": "anthropic package no instalado. pip install anthropic"}

    client = Anthropic(api_key=ANTHROPIC_KEY, timeout=CLAUDE_TIMEOUT_SEC)
    prompt = _build_claude_prompt(family, checks, notes)

    fid = (family or {}).get("family_id")
    try:
        resp = _with_retry(
            lambda: client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                temperature=CLAUDE_TEMPERATURE,
                messages=[{"role": "user", "content": prompt}],
            ),
            api_name="claude",
            family_id=fid,
            photo_index=None,
        )
    except Exception as e:
        return {"ok": False, "error": f"Claude API error tras {RETRY_MAX_ATTEMPTS} intentos: {type(e).__name__}: {e}"}

    raw_text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            raw_text += block.text

    # Intentar parsear JSON. Claude a veces envuelve en ```json
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        # strip fences
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"Claude no devolvio JSON valido: {e}", "raw": raw_text}

    return {"ok": True, "data": data, "raw": raw_text}


def claude_enrich_batch(families_with_context, concurrency=3, on_progress=None,
                         per_item_timeout=120):
    """Procesa multiples families en paralelo.
    families_with_context: list of dicts { family, checks, notes }
    concurrency: workers paralelos (default 3, antes 5 — reduje para no activar
      rate limit de TPM de Anthropic que causaba cuelgues en cascade).
    on_progress: callback(done_count, total, last_fid, last_ok) para UI.
    per_item_timeout: timeout por item (sec). Si un item excede, su future
      se cancela y se marca error; los demás siguen.

    Retorna: dict {family_id: result_dict}.

    Fix s14m: antes usaba executor.map() que es ORDERED — si el primer item
    se colgaba, los demás no yieldean (bloqueaba UI forever). Ahora usa
    as_completed() + per-item timeout para no bloquear.
    """
    results = {}
    total = len(families_with_context)

    def _one(item):
        family = item["family"]
        r = claude_enrich(family, item.get("checks"), item.get("notes", ""))
        return family["family_id"], r

    done = 0
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_fid = {}
        for item in families_with_context:
            fid = item["family"].get("family_id", "?")
            fut = executor.submit(_one, item)
            future_to_fid[fut] = fid

        for fut in as_completed(future_to_fid):
            fid = future_to_fid[fut]
            try:
                result_fid, result = fut.result(timeout=per_item_timeout)
                results[result_fid] = result
            except FuturesTimeoutError:
                results[fid] = {"ok": False, "error": f"per_item_timeout ({per_item_timeout}s)"}
            except Exception as e:
                results[fid] = {"ok": False, "error": f"worker exception: {type(e).__name__}: {e}"}
            done += 1
            if on_progress:
                try:
                    on_progress(done, total, fid, results[fid].get("ok", False))
                except Exception:
                    pass  # UI callback no debe romper el batch

    return results


# ───────────────────────────────────────────
# Gemini watermark inpainting
# ───────────────────────────────────────────

GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
GEMINI_REGEN_PROMPT_WATERMARK = (
    "Remove all watermark text from this image (especially 'minkang.x.yupoo.com' "
    "or similar watermarks). Preserve the jersey exactly as shown — do not modify "
    "colors, logos, sponsors, or team crest. Keep the neutral gray background and "
    "mannequin intact. Maintain the same resolution and quality."
)
GEMINI_REGEN_PROMPT_QUALITY = (
    "Improve the image quality of this football jersey photograph: enhance sharpness, "
    "adjust lighting to be even, remove any watermark text, and preserve the jersey "
    "colors, sponsors, team crest, and overall composition exactly. Keep the same "
    "neutral gray studio background with mannequin. Do not add or remove any design "
    "elements of the jersey itself."
)


def gemini_regen_image(image_bytes, mime_type="image/jpeg", prompt_variant="watermark",
                        family_id=None, photo_index=None):
    """Llama Gemini para re-generar una imagen. Input bytes, output bytes.
    prompt_variant: 'watermark' o 'quality'
    family_id / photo_index: contexto para retry error log.
    Retorna dict { ok, image_bytes, mime_type, error }
    """
    if not gemini_available():
        return {"ok": False, "error": "GEMINI_API_KEY no seteada"}

    try:
        from google import genai
        from google.genai import types as gtypes
    except ImportError:
        try:
            # Fallback al package viejo
            import google.generativeai as genai_legacy
            return _gemini_regen_image_legacy(
                image_bytes, mime_type, prompt_variant, genai_legacy,
                family_id=family_id, photo_index=photo_index,
            )
        except ImportError:
            return {"ok": False, "error": "google-genai package no instalado. pip install google-genai"}

    prompt = GEMINI_REGEN_PROMPT_WATERMARK if prompt_variant == "watermark" else GEMINI_REGEN_PROMPT_QUALITY

    def _call():
        client = genai.Client(api_key=GEMINI_KEY)
        http_options = gtypes.HttpOptions(timeout=GEMINI_TIMEOUT_SEC * 1000) if hasattr(gtypes, "HttpOptions") else None
        kwargs = {
            "model": GEMINI_IMAGE_MODEL,
            "contents": [
                gtypes.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                prompt,
            ],
        }
        if http_options is not None:
            kwargs["config"] = gtypes.GenerateContentConfig(http_options=http_options) if hasattr(gtypes, "GenerateContentConfig") else None
        # Algunos SDKs no aceptan config aún — intento sin config si falla el primer uso
        if kwargs.get("config") is None:
            kwargs.pop("config", None)
        return client.models.generate_content(**kwargs)

    try:
        response = _with_retry(_call, api_name="gemini", family_id=family_id, photo_index=photo_index)
    except Exception as e:
        return {"ok": False, "error": f"Gemini error tras {RETRY_MAX_ATTEMPTS} intentos: {type(e).__name__}: {e}"}

    # Extrae la imagen de la respuesta
    for candidate in (response.candidates or []):
        parts = candidate.content.parts if candidate.content else []
        for part in parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                out_bytes = inline.data
                out_mime = getattr(inline, "mime_type", "image/jpeg")
                return {"ok": True, "image_bytes": out_bytes, "mime_type": out_mime}

    # Gemini respondió pero sin imagen útil — log + signal a caller para reintentar en
    # otro contexto o marcar needs_rework
    _log_api_err(family_id, photo_index, "gemini",
                 "empty_response (no inline_data in candidates)",
                 RETRY_MAX_ATTEMPTS, final_failure=True)
    return {"ok": False, "error": "Gemini no devolvio imagen en la respuesta"}


def _gemini_regen_image_legacy(image_bytes, mime_type, prompt_variant, genai_legacy,
                                 family_id=None, photo_index=None):
    """Fallback con google-generativeai viejo."""
    prompt = GEMINI_REGEN_PROMPT_WATERMARK if prompt_variant == "watermark" else GEMINI_REGEN_PROMPT_QUALITY
    def _call():
        genai_legacy.configure(api_key=GEMINI_KEY)
        model = genai_legacy.GenerativeModel(GEMINI_IMAGE_MODEL)
        return model.generate_content([
            {"mime_type": mime_type, "data": image_bytes},
            prompt,
        ])
    try:
        response = _with_retry(_call, api_name="gemini", family_id=family_id, photo_index=photo_index)
    except Exception as e:
        return {"ok": False, "error": f"Gemini legacy error tras {RETRY_MAX_ATTEMPTS} intentos: {type(e).__name__}: {e}"}

    # Intenta extraer imagen
    for candidate in (response.candidates or []):
        for part in (candidate.content.parts or []):
            if hasattr(part, "inline_data") and part.inline_data:
                return {
                    "ok": True,
                    "image_bytes": part.inline_data.data,
                    "mime_type": getattr(part.inline_data, "mime_type", "image/jpeg"),
                }
    _log_api_err(family_id, photo_index, "gemini",
                 "empty_response_legacy (no inline_data)",
                 RETRY_MAX_ATTEMPTS, final_failure=True)
    return {"ok": False, "error": "Gemini legacy no devolvio imagen"}


# ───────────────────────────────────────────
# R2 upload helper (para fotos procesadas)
# ───────────────────────────────────────────

def upload_image_to_r2(image_bytes, key, content_type="image/jpeg"):
    """Sube bytes a R2. Key ej: 'families/<fid>/01-cleaned.jpg'.
    Retorna { ok, public_url, error }
    """
    account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
    access_key = os.getenv("R2_ACCESS_KEY_ID", "").strip()
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
    bucket = os.getenv("R2_BUCKET", "elclub-vault-images").strip()

    if not (account_id and access_key and secret_key):
        return {"ok": False, "error": "R2 creds no seteados en env"}

    try:
        import boto3
    except ImportError:
        return {"ok": False, "error": "boto3 no instalado"}

    try:
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=image_bytes,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as e:
        return {"ok": False, "error": f"R2 upload failed: {type(e).__name__}: {e}"}

    public_url = f"https://img.elclub.club/{key}"
    return {"ok": True, "public_url": public_url}

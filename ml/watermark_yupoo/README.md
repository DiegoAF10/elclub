# Tier 3 — U-Net especializado en watermark Yupoo

Modelo entrenado end-to-end para limpiar el watermark diagonal de Yupoo
(`minkang.x.yupoo.com` y variantes). Corre local en GPU, ~200ms por foto,
escala a todo el catálogo.

## Por qué esto funciona

El watermark de Yupoo es **determinístico**:
- Mismo font (Arial-ish bold)
- Mismo opacity (~20-30%)
- Misma orientación (diagonal ~-15°)
- Mismo tiling pattern (repetición en grid ~200×80px)

Entonces podemos **reproducirlo exactamente** con PIL/OpenCV → generar
pares sintéticos infinitos: `(foto_limpia + watermark_overlay, foto_limpia_target)`.

Un U-Net pequeño entrenado en esos pares aprende "undo el watermark Yupoo"
y nada más — no inventa, no alucina, no daña texturas. Es como
fine-tunear un filtro quirúrgico.

## Pipeline

```
1. Recolectar ~2000 fotos limpias de jerseys (data/clean/)
   ↓
2. synthesize_watermark.py aplica el overlay de Yupoo con variaciones
   aleatorias de escala/rotación/opacity → genera data/pairs/
   ↓
3. train.py entrena U-Net (input=watermarked, target=clean)
   ↓
4. inference.py expone clean_image(img_bytes) → img_bytes drop-in
   compatible con _regen_watermark como mode="ml"
```

## Status

- [x] Scaffold creado
- [x] synthesize_watermark.py funcional (usa template existente)
- [ ] Data collection: llenar `data/clean/` con ~2000 fotos (ver `DATA_COLLECTION.md`)
- [ ] Synthesis batch run
- [ ] train.py (U-Net 20M params, ~2-3 días GPU)
- [ ] Evaluation harness
- [ ] Integration en ERP (`mode="ml"`)

## Scope y no-scope

**Scope:** watermark Yupoo `minkang.x.yupoo.com` (y variantes tipo
`*.yupoo.com`) sobre jerseys de fútbol.

**No-scope:** otros watermarks (Aliexpress, DHGate, etc.). Si aparecen,
entrenamos un segundo modelo o ampliamos este.

## Costos

- Training: ~$0 (GPU local)
- Inference: ~$0 (GPU local, ~200ms/foto)
- Data annotation: $0 (todo es sintético)
- Tiempo Diego: ~4h data collection + ~2h validation de resultados

Todo el resto lo hago yo.

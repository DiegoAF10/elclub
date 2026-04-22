# GPT Image Prompting — El Club
**Generado:** 2026-04-22
**Aplica a:** gpt-image-1 / gpt-image-1.5 (ChatGPT / API)
**Source of visual truth:** [`BRAND.md`](../../BRAND.md) sección 4

---

## Por qué este doc existe

Los prompts Gemini que tenemos en `gemini-prompts-launch.md` funcionan para Gemini.
GPT Image usa **otro modelo mental**: entiende instrucciones labeled, respeta text rendering, y soporta anchor images para consistencia de marca. Este doc traduce nuestro estilo Midnight Stadium al formato óptimo de GPT Image.

---

## 1. Estructura canónica (6-part framework)

Siempre seguí este orden, preferiblemente con **line breaks o labels**, no como párrafo denso:

```
1. SCENE / BACKGROUND
2. SUBJECT
3. KEY DETAILS (materials, textures, pose)
4. LIGHTING + MOOD
5. COMPOSITION (framing, angle, placement)
6. CONSTRAINTS + USE CASE
```

### Ejemplo El Club (Mystery Box hero)

```
SCENE: Pure black studio background (#0D0D0D), minimalist void.

SUBJECT: Single kraft cardboard mystery box, closed, centered.
Simple, unbranded, matte finish with slight cardboard texture.

DETAILS: Small ice-blue wax seal on the box lid (color #4DA8FF).
Visible grain on the kraft, one folded corner.

LIGHTING: Dramatic side spotlight from 45° left, deep shadows,
rim light on the right edge of the box. High contrast.

COMPOSITION: Eye-level shot, 1:1 square format, subject centered,
negative space above and below.

CONSTRAINTS: Photorealistic. No text, no logo, no watermark.
Editorial product photography style for premium e-commerce.
```

---

## 2. El "El Club base prompt" (copy-paste ready)

Pegá este bloque al inicio de CADA prompt y después agregá el subject-specific:

```
STYLE ANCHOR — El Club "Midnight Stadium":
Pure black background (#0D0D0D). Monochrome scene except for the
colored subject. Dramatic spotlight lighting with deep shadows and
rim light. Editorial product photography, museum-piece feel.
Premium, cinematic, streetwear underground aesthetic.
The only color in the frame is the product. No extra graphics,
no text, no watermarks. Photorealistic. 1:1 square for feed, 9:16
for stories, 4:5 for IG portrait. No generic drop shadows.
```

---

## 3. Reglas específicas para GPT Image (diferente a Gemini)

### Cosas que GPT Image hace MEJOR que Gemini

1. **Text rendering.** GPT Image sí puede escribir texto legible si usás comillas + ALL CAPS + spelling letter-by-letter para brand names.
   - `Add text "EL CLUB" spelled E-L C-L-U-B, in Oswald 700 uppercase, white color, bottom center.`
2. **Respeta constraints negativos.** "no watermark", "no text" funcionan mejor.
3. **Anchor images.** Subí una imagen de referencia y decile: `match the style of the reference image (Image 1)`.

### Cosas donde GPT Image falla

1. **Tiende a oscurecer más de la cuenta.** Si pedís "dark cinematic", a veces sale casi negro puro. **Fix:** agregá `with visible details, dramatic but readable exposure`.
2. **Color drift.** Si decís "blue accent" sin hex, te tira cualquier azul. **Fix:** siempre usar HEX: `ice blue #4DA8FF`.
3. **Jerseys genéricos.** Si pedís "Chelsea 11/12 jersey" puede inventar diseño. **Fix:** subir imagen de referencia real del jersey + decir `preserve the exact design, colors, and sponsor placement of Image 1`.

---

## 4. Anchor Image Strategy (LA clave para consistencia de marca)

**El problema:** si cada post lo generás solo con prompt, la estética drifta. Un post sale más oscuro, otro más warm, otro con fondo gris.

**La solución:** anchor images.

### Setup inicial (1 sola vez)

1. Generá 1 imagen que sea TU master reference de Midnight Stadium.
   - Pegá el base prompt + un subject simple (caja kraft sobre midnight).
   - Iterá hasta que salga perfecta.
   - Guardala como `assets/img/brand/style-anchor.jpg`.

2. Generá un segundo anchor con jersey real:
   - Foto real del jersey + base prompt + "elevate to Midnight Stadium aesthetic"
   - Guardalo como `assets/img/brand/anchor-jersey.jpg`

### Uso por post

Para cualquier post nuevo:
```
Upload: style-anchor.jpg (Image 1) + [subject photo if any] (Image 2)

Prompt:
"Apply the exact lighting, background, contrast, and color grading
of Image 1 to Image 2. Keep the subject from Image 2 intact (preserve
design, logos, text). Output in 1:1 format for Instagram feed."
```

**Resultado:** estética consistente 100% across posts.

---

## 5. Ajustes a los prompts del plan vault-launch

### POST 01 (Algo se guarda, algo se muestra) — UPGRADE

**Antes (estilo Gemini):**
```
Dark cinematic flat lay on pure black background (#0D0D0D)...
```

**Ahora (estilo GPT Image):**
```
[Pegá el "El Club base prompt" primero, después:]

SCENE: Pure black studio surface, overhead view.

SUBJECT: Two objects arranged side by side with 20% gap between them.
Left object: one folded vintage football jersey in vibrant red with
white stripes (90s retro style, no specific team logo visible).
Right object: one closed kraft cardboard box, simple matte finish.

DETAILS: The jersey is neatly folded showing the collar and a
partial view of the crest area (generic, no identifiable team).
The box has a faint fold line and natural cardboard texture.
No labels on the box.

LIGHTING: Single dramatic top-down spotlight creating strong shadow
to the right of each object. Key light color neutral white.
Rim highlights on the top edges. Readable but moody exposure.

COMPOSITION: Top-down flat lay, 1:1 square. Both objects together
occupy 70% of frame width, centered.

CONSTRAINTS: Photorealistic editorial product photography.
Only the jersey is colored (red); everything else monochrome black
and dark grays. No text, no watermarks. For Instagram feed post.
```

### POST 13 (Reveal Vault) — UPGRADE con text rendering

**GPT Image puede escribir el texto overlay DIRECTO en la imagen:**

```
[Base prompt] + 

SCENE: Dark editorial photo of a wooden archive cabinet with
glass doors in pure black void. Multiple football jerseys visible
inside as silhouettes.

SUBJECT: One central jersey in vibrant color (deep red) is highlighted
with a warm spotlight. Other jerseys are in deep shadow.

DETAILS: Cabinet is minimalist, dark wood, brass handles.
Inside, jerseys hang on wooden hangers.

LIGHTING: Single warm spotlight on the central jersey.
Other jerseys barely visible in shadow.

COMPOSITION: 1:1 square. Cabinet centered, subject jersey
positioned using rule of thirds.

TEXT: Add text "EL ARCHIVO ESTÁ ABIERTO" spelled
E-L  A-R-C-H-I-V-O  E-S-T-Á  A-B-I-E-R-T-O,
in Oswald 700 uppercase font, white color, positioned
across the top third of the image. Use accent mark over the "A"
in "ESTÁ". Below it in smaller text, add "VAULT" in ice blue
color #4DA8FF.

CONSTRAINTS: Photorealistic. EXACT text, no extra characters,
no misspellings. No additional watermarks or graphics.
```

---

## 6. Prompt templates por tipo de post

### Template A — Jersey hero shot

```
[Base prompt]

SCENE: Pure black studio void, minimalist.

SUBJECT: Single football jersey displayed [floating in space /
on black mannequin torso / flat lay over kraft box].
[Describe design, colors, sponsor if shown].

DETAILS: Visible fabric texture (mesh pattern, stitching).
[Specific era details if retro: vintage cotton, embroidered crest,
period-accurate sponsor placement].

LIGHTING: Dramatic [side / top / rim] spotlight creating deep
shadows. Jersey colors pop against black void.

COMPOSITION: [Eye-level / slight low angle / overhead].
[1:1 / 9:16 / 4:5].

CONSTRAINTS: Photorealistic editorial product photography.
Only the jersey is colored. No text, no watermarks.
```

### Template B — Mystery Box + unboxing moment

```
[Base prompt]

SCENE: Pure black surface, slight vignette.

SUBJECT: Kraft cardboard mystery box, [closed / slightly open with
warm glow emerging / open with one jersey visible inside].

DETAILS: [If ice-blue wax seal visible, describe with hex #4DA8FF].
Tissue paper peeking if open.

LIGHTING: Warm spotlight suggesting inner light. Hard shadows
around box.

COMPOSITION: [Overhead POV for unboxing / 45° hero / close-up
on seal detail].

CONSTRAINTS: Photorealistic. Cardboard texture visible.
No brand text unless specified. 
```

### Template C — Texto/quote post (statement)

```
[Base prompt]

SCENE: Pure black (#0D0D0D), completely empty void.

TEXT ONLY: Add text "[YOUR STATEMENT]" spelled [letter-by-letter
if tricky], in Oswald 700 uppercase, white color, centered.
Secondary line below in Space Grotesk 400, smaller, in color
ice blue #4DA8FF.

COMPOSITION: 1:1 square. Text occupies central 60% of frame.
Generous negative space top and bottom.

CONSTRAINTS: Typography-focused. No subjects, no photographic
elements. EXACT text rendering, no misspellings, no extra
characters. Clean, editorial, premium.
```

### Template D — Poll comparativo (2 jerseys)

```
[Base prompt]

SCENE: Pure black surface, split composition.

SUBJECTS:
- LEFT SIDE: [Jersey A description].
- RIGHT SIDE: [Jersey B description].
Separated by a subtle thin vertical line of ice blue light.

DETAILS: Both jerseys at same size, same angle, equal prominence.

LIGHTING: Identical spotlight on each jersey to avoid bias.
Deep shadow between them.

COMPOSITION: 1:1 square, perfect 50/50 split.

TEXT (optional): Add letter "A" top-left and "B" top-right,
in Oswald 700 white, small.

CONSTRAINTS: Photorealistic. Both jerseys equally lit.
Neutral presentation. No overt winner styling.
```

### Template E — BTS / archivo mood

```
[Base prompt]

SCENE: Dark storage space or archive cabinet. Pure black
surroundings with selective illumination.

SUBJECT: [Multiple jerseys hanging on rack / stacked folded
jerseys / archive drawers open].

DETAILS: Atmospheric, slightly dusty feel. Wooden or metal
hangers. Jerseys partially visible as silhouettes.

LIGHTING: Single dramatic sidelight, most jerseys in deep shadow,
one or two catching rim light.

COMPOSITION: [Low angle looking up / eye level straight / 3/4
from corner].

CONSTRAINTS: Monochrome black and dark grays. One small pop of
color on the closest jersey's collar or sleeve. Editorial,
cinematic. No text, no branding.
```

---

## 7. Regeneration budget & QC

Según benchmarks 2026, ~**12% de imágenes** requieren regeneration por:
- Color drift (azul equivocado)
- Sobre-oscurecimiento
- Texto mal escrito
- Detalles inventados en jerseys específicos

### Proceso recomendado
1. Generá 2 variaciones del mismo prompt
2. Elegí la mejor
3. Si ninguna sirve, ajustá UN solo parámetro y regenerá
4. Budget 15-20% extra de tiempo vs generación con Gemini

### Checklist pre-publicar
- [ ] ¿Fondo #0D0D0D verdadero (no gris ni marrón)?
- [ ] ¿Solo el jersey/objeto tiene color?
- [ ] ¿Exposición readable (no casi negro puro)?
- [ ] ¿Hex de ice blue correcto donde aplica?
- [ ] ¿Texto sin misspellings?
- [ ] ¿Aspect ratio correcto (1:1 feed / 9:16 story / 4:5 portrait)?
- [ ] ¿Alinea con style-anchor.jpg visualmente?

---

## 8. Flujo de trabajo por sprint

```
Día 1 (planning):
  - Definir 5-7 posts del sprint
  - Listar subject específico de cada uno
  - Confirmar que hay anchor image actualizado

Día 2 (batch generation):
  - Generar en bloque de 5-7 posts consecutivos
  - Usar mismo anchor image reference para los 5-7
  - Quality "high" para posts de producto y reveal
  - Quality "medium" para BTS y posts secundarios

Día 3 (QC + upload):
  - Revisar con checklist
  - Regenerar ~12% que no pase
  - Agregar text overlays en Canva/Figma si hacen falta ajustes finos
  - Programar en Meta Business Suite
```

---

## Referencias

- [GPT Image Generation Models Prompting Guide — OpenAI Cookbook](https://developers.openai.com/cookbook/examples/multimodal/image-gen-models-prompting-guide)
- [Gpt-image-1.5 Prompting Guide](https://cookbook.openai.com/examples/multimodal/image-gen-1.5-prompting_guide)
- [4o Image Generation — Prompt Engineering Guide](https://www.promptingguide.ai/guides/4o-image-generation)
- [`BRAND.md`](../../BRAND.md) sección 4 (Brand visual)
- [`plan-vault-launch-2026-04-22.md`](../../content/social-posts/plan-vault-launch-2026-04-22.md)

---

*Este doc se actualiza cuando OpenAI releasea nueva versión del modelo. Última revisión: 2026-04-22 / gpt-image-1.5.*

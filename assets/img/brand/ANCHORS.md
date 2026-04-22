# Brand Anchors — El Club

**Actualizado:** 2026-04-22
**Uso:** imágenes maestras que se suben como knowledge files al Custom GPT "El Club · Creative Director" para garantizar consistencia visual en todo el contenido generado.

---

## Los 3 anchors universales (subir al GPT)

### `brand-anchor-hero.png`
**Qué es:** caja kraft lisa + wax seal ice blue #4DA8FF + jersey rojo genérico peeking desde debajo del lid.
**Uso en el GPT:** referenciada cuando se genera Product Mode hero shots, Mystery Box ads (`ad mystery`), Vault Mode (`vault hero`), lanzamientos, reveals.
**Neutralidad:** sin branding, sin equipo específico, sin sponsor. Por eso sirve como style reference para cualquier subject.
**Generada:** 2026-04-22 con comando `anchor hero` en el GPT.

### `brand-anchor-flatlay.png`
**Qué es:** jersey genérico blanco con trim azul, bird's eye 90°, sleeves angled 20° outward, fondo Midnight Stadium.
**Uso en el GPT:** referenciada para Product Mode (default flat lay), Back view, Detail Mode, Historia Mode.
**Neutralidad:** jersey sin sponsor/crest identificable.
**Generada:** 2026-04-22 con comando `anchor flatlay` en el GPT.

### `brand-anchor-player.png`
**Qué es:** atleta genérico mid-20s, chest-up, Rembrandt lighting, stadium haze background, jersey rojo genérico.
**Uso en el GPT:** referenciada para Player Mode, Ad Mode (`ad catalog`), retratos, contenido Mundial 2026.
**Neutralidad:** figura genérica, cara parcialmente en sombra, sin equipo.
**Generada:** 2026-04-22 con comando `anchor player` en el GPT.

---

## Assets aspirational (NO subir al GPT como anchor)

### `brand-anchor-hero-branded.png`
**Qué es:** variante de hero con branding real de El Club (tapa con texto "EL CLUB / MYSTERY BOXES") + jersey Inter Milan específico como display de referencia.
**Uso:** post de producto real donde la caja branded es el protagonista (ej: unboxing hero shot, post de lanzamiento donde se muestra la caja real). Es un asset creativo.
**NO usar como anchor** — el texto y el jersey específico sesgarían todas las generaciones futuras hacia Inter Milan y harían que el modelo inyecte "EL CLUB / MYSTERY BOXES" en composiciones donde no va.
**Generada:** 2026-04-22 como primer intento de `anchor hero`, conservada por calidad visual.

---

## Cuándo regenerar los anchors

Regenerar si:
- El modelo de GPT Image se actualiza significativamente (ej: gpt-image-2)
- BRAND.md cambia la paleta o tipografía
- Un cliente nuevo pide foto con estética distinta y hay que pivotar

Cada regeneración debe:
1. Pasar el QC checklist del playbook
2. Ser committed al repo
3. Actualizar este `ANCHORS.md` con fecha nueva
4. Re-subirse al Custom GPT (reemplazar el anterior)

---

## Generación: prompts canonical

Los 3 prompts completos viven en `el-club/docs/content/el-club-playbook.md` sección "Anchor generation prompts". Para regenerar, ejecutar en el GPT:

```
anchor hero
anchor flatlay
anchor player
```

El GPT lee el playbook y aplica los prompts estructurados.

---

*Fin. Si agregás un anchor nuevo, documentalo acá.*

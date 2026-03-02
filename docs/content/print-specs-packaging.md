# El Club — Specs de Imprenta para Packaging

---

## 1. STICKER SELLO PARA CAJA

### Descripción
Sticker circular que sella la caja kraft de la mystery box. Es lo primero que el cliente ve.

### Specs técnicos
- **Forma:** Círculo
- **Diámetro:** 5 cm (50 mm)
- **Material:** Vinilo mate adhesivo (o papel adhesivo mate)
- **Acabado:** Mate (NO brillante — la marca es midnight, no flashy)
- **Resolución:** 300 dpi mínimo
- **Modo de color:** CMYK
- **Sangrado:** 2mm alrededor

### Diseño
- **Fondo:** Negro sólido (C:0 M:0 Y:0 K:100 — negro puro CMYK)
- **Contenido:** Escudo de El Club centrado, blanco (C:0 M:0 Y:0 K:0)
- **El escudo debe ocupar ~70% del diámetro** (dejar borde negro visible)
- **SIN texto adicional.** Solo el escudo. Limpio.
- **SIN ice blue.** El logo es siempre monocromático.

### Archivo fuente
Usar `el-club/assets/img/brand/logo-icon.svg` como base.

### Cómo armarlo en Illustrator
1. Nuevo documento: 50×50mm, CMYK, 300dpi
2. Dibujar círculo de 50mm, relleno negro K:100
3. Importar logo-icon.svg, escalar a ~35mm de ancho
4. Centrar horizontal y verticalmente
5. Agregar sangrado de 2mm (el negro se extiende)
6. Exportar como PDF/X-1a para imprenta

### Cantidad sugerida
**200 unidades** (~Q100-150 estimado)
Suficiente para ~60 cajas del inventario actual + margen.

---

## 2. THANK YOU CARD

### Descripción
Tarjeta que va dentro de cada mystery box. Refuerza la marca y conecta al cliente con redes.

### Specs técnicos
- **Tamaño:** 10 × 15 cm (tarjeta postal estándar)
- **Material:** Cartulina couché mate 300g+
- **Acabado:** Mate ambos lados
- **Impresión:** Full color ambos lados (4/4)
- **Resolución:** 300 dpi
- **Modo de color:** CMYK
- **Sangrado:** 3mm por lado

### FRENTE (lado principal)
- **Fondo:** Negro sólido K:100 (todo el frente)
- **Centro:** Escudo El Club en blanco, tamaño ~4cm de ancho
- **Debajo del escudo:** Wordmark "EL CLUB" en blanco
  - Tipografía: Space Grotesk Light (o la sans-serif del logo)
  - Uppercase, tracking amplio (~0.2em equivalente)
- **Fragmentos del logo:** 2-3 fragmentos pequeños en la esquina inferior derecha (como en el logo)
- **Sin más texto en el frente.** Limpio, impactante.

### REVERSO
Layout vertical, fondo negro K:100:

```
[parte superior — 60% del espacio]

        "Bienvenido al Club."
    (Oswald Bold, blanco, centrado, ~18pt)

  "La camiseta te eligió a vos."
    (Space Grotesk Regular, smoke #999, centrado, ~11pt)


[línea divisora — chalk #2A2A2A, 1px, 70% del ancho]


[parte inferior — 40% del espacio]

   [QR code]        @club.gt
   (2.5×2.5cm)      elclub.club
   (blanco sobre
    negro)          [ícono IG] [ícono TikTok]
```

- **QR code:** Apunta a https://instagram.com/club.gt
- **QR color:** Módulos blancos, fondo negro (inverted QR)
- **Íconos sociales:** IG y TikTok en blanco, ~6mm

### Cómo armarlo en Illustrator
1. Nuevo documento: 100×150mm, CMYK, 300dpi, sangrado 3mm
2. **Frente:** Fondo negro, escudo + wordmark centrados
3. **Reverso:** Fondo negro, texto + QR + sociales
4. Generar QR en https://www.qr-code-generator.com/ → color blanco, fondo transparente
5. Exportar como PDF/X-1a con sangrado y marcas de corte

### Cantidad sugerida
**100 unidades** (~Q150-200 estimado)

---

## 3. QR CODE BRANDED

### Para generar:
1. Ir a https://www.qr-code-generator.com/ (o similar)
2. URL: `https://instagram.com/club.gt`
3. Color de módulos: Blanco (#FFFFFF)
4. Fondo: Transparente
5. Descargar como SVG o PNG alta resolución
6. En Illustrator: colocar el escudo del logo al centro del QR (tamaño ~20% del QR)
7. Verificar que el QR siga escaneando correctamente con el logo al centro

---

## RESUMEN PARA LA IMPRENTA

| Pieza | Cantidad | Tamaño | Material | Lados | Acabado |
|-------|----------|--------|----------|-------|---------|
| Sticker sello | 200 | Círculo 5cm | Vinilo adhesivo | 1 | Mate |
| Thank you card | 100 | 10×15cm | Couché 300g | 2 | Mate |

**Entregar a imprenta:** Archivos PDF/X-1a con sangrado y marcas de corte.
**Colores:** Predominantemente negro + blanco. Costo de tinta bajo.
**Tiempo estimado:** 2-3 días hábiles para imprenta digital.

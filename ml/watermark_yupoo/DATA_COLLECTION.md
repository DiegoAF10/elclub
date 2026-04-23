# Data Collection — Jerseys sin watermark

Necesitamos ~2000 fotos de jerseys SIN watermark Yupoo, lo más diversas
posible, para entrenar el U-Net específico.

## Sources recomendados

### A — Alta calidad, sin watermark (prioridad alta)
- **adidas.com/football** — fichas de producto oficiales, multi-angle
- **nike.com/football** — ídem
- **pumashop.com** — ídem
- **store.fifa.com** — jerseys oficiales
- **dickssportinggoods.com** — retail legítimo, fotos profesionales
- **prodirectsoccer.com** — amplio catálogo

### B — Mid quality, verificar watermark antes de usar
- **soccer.com**
- **worldsoccershop.com**
- **subside-sports.com**
- **classicfootballshirts.co.uk** — vintage, buena variedad

### C — Backups ya limpios que tenés
- Todo lo que hayas procesado con LaMa/SD que haya salido bien → copiar a `data/clean/`
- Fotos de tu propio catálogo que NO vinieron de Yupoo

## Criterios

Cada foto debe cumplir:
- [ ] Jersey de fútbol (no polos, no camisas casuales)
- [ ] Sin watermark visible (ningún texto overlay)
- [ ] Resolución >= 500px en el lado más corto
- [ ] JPG o PNG
- [ ] Variedad de teams, años, colores, proveedores (adidas, Nike, Puma, New Balance, Kappa, etc.)
- [ ] Variedad de ángulos (front, back, detail shots, folded, on mannequin, flat lay)

## Organización

Guardá en `ml/watermark_yupoo/data/clean/`:
```
data/clean/
  adidas_argentina_2022_home_001.jpg
  adidas_argentina_2022_home_002.jpg
  nike_barcelona_2024_away_001.jpg
  ...
```

Naming libre, pero si podés incluir `{brand}_{team}_{year}_{kit}_{idx}.jpg`
mejor para que el synthesis agregue diversity balanceada.

## Target

- **Mínimo viable para prototype**: 500 fotos
- **Recomendado**: 2,000 fotos
- **Ideal**: 5,000 fotos (maximiza generalization a jerseys nuevos)

Podemos empezar a entrenar con 500 y seguir añadiendo data mientras
el modelo mejora iterativamente.

## Herramientas útiles para scrape legítimo

- `gallery-dl` — extractor universal para muchos sites
- `wget -r --accept jpg,png <url>` — para catálogos públicos
- Extensions tipo "Imageye" en Chrome para bulk download visual
- Script custom si son sites con listing JSON (te armo uno cuando tengamos los sources)

## Auditoría rápida pre-training

Antes de synthesize, corro `python audit_clean_data.py` (no existe todavía,
se crea en la Fase 2 del roadmap) que:
- Detecta imágenes con watermarks todavía presentes (false negatives en collection)
- Flagea resolución insuficiente
- Detecta duplicados via perceptual hash
- Reporta balance de brands/teams/years

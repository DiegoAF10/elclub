# El Club ERP — Overhaul prototype

Prototipo del nuevo ERP. SvelteKit + Tailwind v4. Dark mode estilo Linear + Raycast.
Mock data del Mundial 2026. **Nada conectado a prod** — es un playground para tocar.

## Cómo correrlo

```bash
cd overhaul
npm run dev
```

Abrís `http://localhost:5173` y estás adentro.

## Qué tocar

### Mouse
Click en cualquier SKU del panel medio → se abre en el detail de la derecha.
Sidebar items son clickables (highlight cambia) aunque solo "Audit" está
conectado por ahora — el resto es mockup visual.

### Keyboard

| Shortcut | Acción |
|---|---|
| `Ctrl+K` | Command palette (fuzzy search) |
| `J` / `↓` | Next SKU |
| `K` / `↑` | Prev SKU |
| `V` | Verify (toast mock) |
| `F` | Flag (toast mock) |
| `S` | Skip (toast mock) |
| `ESC` | Cerrar palette |

### Command palette — probá esto primero
1. Apretá `Ctrl+K`.
2. Escribí `brazil fan long` → solo BRA-2026-L-FL.
3. Flecha abajo + Enter → salta al SKU.

Comparalo con el search del Streamlit — acá es 0ms.

## Lo que NO está y es intencional
- Tauri wrapper: después
- Data real: después (mocks en `src/lib/data/mock.ts`)
- Backend / persistencia: después
- Gallery inpaint (LaMa/Gemini/SD): toolbar visual, no acciona
- Drag-and-drop reordenar: no, mockup
- Auto-save specs: inputs editan pero no guardan

## Lo que SÍ funciona
- Layout 3 paneles + scroll independiente por pane
- Dark theme consistente (design tokens en `app.css`)
- Command palette Cmd+K con fuzzy multi-token
- Keyboard nav J/K
- 6 estados de status con color semantic
- Pre-publish checks calculados del modelo
- Family siblings visible
- Toast feedback en V/F/S

## Qué necesito de vos después de tocarlo

Anotá:
1. **Primer momento:** ¿se siente otra cosa? (test de éxito: evidente desde el primer segundo)
2. **Command palette:** ¿indispensable u overkill?
3. **Detail pane:** ¿la info que está ahí es la que querés?
4. **Density:** ¿cabe info útil o sobra whitespace?
5. **Color / fuentes:** ¿"pro tool" o "demo web"?
6. **Keyboard shortcuts:** ¿J/K te gusta?

Cuando tengas feedback, iteramos antes de escalar a las otras pantallas.

## Estructura

```
src/
├── app.css                       # Design tokens + Tailwind v4
├── routes/
│   ├── +layout.svelte            # root, fonts, css
│   └── +page.svelte              # main: 3-pane + keyboard
└── lib/
    ├── data/
    │   ├── types.ts              # Family, Modelo, Status
    │   └── mock.ts               # 9 mock families del Mundial
    └── components/
        ├── Sidebar.svelte        # 200px izq
        ├── ListPane.svelte       # 380px medio, agrupado A-L
        ├── DetailPane.svelte     # flex-1 der
        ├── CommandPalette.svelte # ⌘K modal
        └── StatusBadge.svelte    # dot + label semántico
```

## Siguientes pasos (post-feedback)
1. Ajustar mockup según feedback
2. Conectar a data real (catalog.json o nuevo clean Mundial)
3. Implementar acciones reales (verify → API)
4. Wrap Tauri → `.exe` instalable
5. Migrar próxima pantalla (Publicados o Mundial dashboard)

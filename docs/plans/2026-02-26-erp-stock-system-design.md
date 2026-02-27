# El Club ERP — Stock System Design

**Date:** 2026-02-26
**Owner:** Diego Arriaza Flores
**Status:** Approved
**Scope:** Phase 1 — Stock database, inventory entry form, inventory management, dashboard, sync to website

---

## Architecture

**Stack:** Streamlit + SQLite (ClanTrack pattern)
**Location:** `el-club/erp/` inside the repo
**DB:** `el-club/erp/elclub.db` (gitignored)
**Teams data:** `el-club/erp/data/teams.json` (~200 pre-loaded teams)
**Photos:** `el-club/erp/photos/[jersey_id]/` (gitignored)
**Launcher:** `el-club/erp/ElClub-ERP.bat` (Chrome app mode, port 8502)
**Mobile access:** Streamlit serves on `0.0.0.0:8502` for phone browser on same WiFi

```
el-club/erp/
├── app.py                  ← Streamlit multipage app
├── schema.sql              ← SQLite schema
├── elclub.db               ← Database (gitignored)
├── data/
│   └── teams.json          ← ~200 pre-loaded teams with leagues and tiers
├── photos/                 ← Jersey photos (gitignored)
│   └── JRS-001/
│       ├── front.jpg
│       ├── back.jpg
│       └── detail-1.jpg
├── .streamlit/
│   └── config.toml         ← Midnight Stadium theme
└── ElClub-ERP.bat          ← Double-click launcher
```

## Database Schema

### Table: `teams` (pre-loaded, ~200 rows)

| Column | Type | Notes |
|--------|------|-------|
| team_id | INTEGER PK | Auto |
| name | TEXT NOT NULL | "FC Barcelona", "Real Madrid" |
| short_name | TEXT | "Barcelona", "Real Madrid" |
| league | TEXT NOT NULL | "Premier League", "La Liga", etc. |
| country | TEXT | "España", "Inglaterra" |
| tier | TEXT DEFAULT 'B' | A/B/C — default value per team |

### Table: `jerseys` (main inventory)

| Column | Type | Notes |
|--------|------|-------|
| jersey_id | TEXT PK | Auto: JRS-001, JRS-002... |
| team_id | INTEGER FK | → teams |
| season | TEXT NOT NULL | "2023/24", "Retro" |
| variant | TEXT NOT NULL | home/away/third/special |
| player_name | TEXT | nullable |
| player_number | INTEGER | nullable |
| size | TEXT NOT NULL | S/M/L/XL |
| patches | TEXT | description of patches |
| tier | TEXT | A/B/C — inherited from team, editable |
| cost | REAL DEFAULT 100 | Q100 sunk cost |
| price | REAL | nullable — TBD later |
| status | TEXT DEFAULT 'available' | available/reserved/sold |
| notes | TEXT | nullable |
| created_at | TEXT | datetime |

### Table: `photos`

| Column | Type | Notes |
|--------|------|-------|
| photo_id | INTEGER PK | Auto |
| jersey_id | TEXT FK | → jerseys |
| photo_type | TEXT | front/back/detail |
| filename | TEXT | relative path in photos/ |
| uploaded_at | TEXT | datetime |

### Indexes
- `jerseys`: team_id, size, status, tier
- `photos`: jersey_id

### Views
- `v_inventory_summary`: Count by size, league, tier, status
- `v_stock_by_team`: Available jerseys grouped by team
- `v_photo_coverage`: Jerseys with/without photos

## Pre-loaded Teams (~200)

| League | Count | Tier A | Tier B | Tier C |
|--------|-------|--------|--------|--------|
| Premier League | 20 | Big 6 (City, Arsenal, Liverpool, Chelsea, United, Spurs) | Rest | — |
| La Liga | 20 | Barcelona, Real Madrid, Atlético | Rest | — |
| Serie A | 20 | Juventus, Inter, Milan, Napoli | Rest | — |
| Bundesliga | 18 | Bayern, Dortmund | Rest | — |
| Ligue 1 | 18 | PSG | Rest | — |
| Liga MX | 18 | América, Chivas, Cruz Azul, Tigres, Monterrey | Rest | — |
| Guatemala | 6 | — | Municipal, Comunicaciones, Xelajú | Rest |
| Argentina | 10 | Boca, River | Rest | — |
| Brasil | 10 | Flamengo, Palmeiras, Corinthians | Rest | — |
| Colombia | 6 | — | Millonarios, Nacional, América de Cali | — |
| Selecciones | ~40 | Argentina, Brasil, Francia, Alemania, España, Inglaterra | Rest | — |

Flow: Select team → league auto-fills → tier inherits (editable).

## Modules (Phase 1)

### 1. Registro de Camisetas (main form)

Purpose: Fast jersey data entry during physical inventory count.

Form fields:
- **Equipo**: Searchable dropdown (st.selectbox with search). ~200 options.
- **Liga**: Auto-filled from team selection. Read-only display.
- **Temporada**: Dropdown — 2019/20, 2020/21, 2021/22, 2022/23, 2023/24, 2024/25, 2025/26, Retro, Clásica
- **Tipo**: Radio buttons — Local / Visita / Reserva / Especial
- **Talla**: Radio buttons — S / M / L / XL
- **Jugador**: Text input (optional)
- **Número**: Number input (optional)
- **Parches**: Text input (optional)
- **Tier**: Dropdown A/B/C (pre-filled from team, editable)
- **Notas**: Text area (optional)
- **Fotos**: File uploader × 3 (front, back, detail) — optional, can add later

UX rules:
- "Guardar y Siguiente" clears form but stays on page
- Last saved jersey shows as confirmation below the button
- Running count: "Camiseta #47 de la sesión"
- Team dropdown remembers last 5 selections for quick re-select

### 2. Inventario (view + manage)

- Full table with all jerseys, sortable and filterable
- Filters: league, team, size, status, tier, has photos
- Click jersey → detail view with photos
- Inline edit for quick corrections
- Bulk actions: select multiple → change status

### 3. Agregar Fotos (mobile-optimized)

- List of jerseys without photos (or partial photos)
- Select jersey → see current photos
- Upload new photos (front/back/detail)
- Camera input on mobile (accept="image/*" capture="environment")
- Designed for phone browser usage

### 4. Dashboard

- Total jerseys: available / reserved / sold
- Distribution by size (bar chart)
- Distribution by league (bar chart)
- Distribution by tier (donut chart)
- World Cup countdown
- Photo coverage: X of Y jerseys with complete photos
- "Sync al Sitio" button

### 5. Sync al Sitio

Button on dashboard:
1. Query all jerseys with status=available
2. Generate `content/products.json` matching website format
3. Show diff: "Adding X jerseys, removing Y"
4. Diego confirms → write file
5. Optional: git add + commit + push

## Deferred (Phase 2+)

- **Mystery Box Engine**: Configurable box types, smart generation, swap/confirm flow
- **Pricing**: Define prices per jersey/tier/box type
- **Sales module**: Record sales, pipeline tracking
- **Finance module**: Revenue vs debt, margins, projections

## Technical Notes

- Streamlit multipage via `st.navigation()` or sidebar pages
- SQLite with WAL mode for concurrent read (laptop + phone)
- Photos stored as files, paths in DB (not blobs)
- Theme: Midnight Stadium colors (dark bg, ice accent)
- `.gitignore`: elclub.db, photos/, __pycache__/

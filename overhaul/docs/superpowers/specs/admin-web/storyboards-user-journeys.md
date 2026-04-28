# Admin Web — Storyboards / User Journeys

> 10 flujos paso-a-paso de las tareas más comunes que Diego va a ejecutar en el Admin Web. Sirven como **acceptance criteria funcional** del R7 + R7.1 + R7.2 + R7.3.
>
> Cada storyboard es testeable end-to-end. Si algún paso falla, hay un bug.

---

## Journey 1: Audit completa de la queue diaria

**Trigger:** Diego abre el ERP cada mañana. Lo primero es atender el queue del Vault.

**Flow:**

1. Diego abre el ERP Tauri.
2. Sidebar global muestra "Admin Web" con badge "12" (queue count).
3. Click en Admin Web → landing en Home (último estado guardado).
4. Home muestra 8 KPIs. KPI "QUEUE" rojo: 12.
5. Inbox card crítico arriba: "🔴 12 jerseys esperando audit · más antiguo lleva 18h".
6. Click [QUEUE] → navega a `/admin-web/vault/queue`.
7. Lista de 12 jerseys ordenadas por priority + recencia. Primera abierta default en panel detail.
8. Diego revisa la jersey actual:
   - Hero + 8 thumbs gallery
   - Specs panel: family_id, team, season, variant, modelos (3), tags, meta
9. Decisión: la jersey está OK. Atajo `V` (verify).
10. Modal toast verde "Verified ARG-2026-V-FS". Auto-jump a la siguiente jersey.
11. Repite para 11 jerseys más.
12. Una de las jerseys tiene foto rota. Atajo `F` (flag for ERP) → marca como dirty para review posterior.
13. Otra jersey es accesorio basura. Click "🗑 Borrar" → confirm dialog "¿Eliminar permanente?" → confirm.
14. Después de 12 audits: queue size 0. Sidebar badge desaparece.
15. Inbox event "queue_pending" auto-resuelve.
16. KPI "QUEUE" se actualiza a 0 (verde).

**Tiempo target:** 8-12 minutos para 12 jerseys.

**Componentes involucrados:** AdminWebShell, AdminWebSidebar, HomeView, KpisGrid, InboxFeed, EventCard, VaultShell, QueueTab, AuditModal (existente).

**Tauri commands:** get_admin_web_kpis, list_inbox_events, list_queue, verify_audit, flag_audit, delete_audit.

---

## Journey 2: Programar drop de Mundial Wave 1

**Trigger:** Diego decide hacer un drop temático en Stock para 12 jerseys del Mundial 2026.

**Flow:**

1. Diego abre Admin Web → Vault > Universo.
2. Aplica preset "🇲🇽 Latam Mundial 2026" (vista guardada).
3. Tabla muestra 12 jerseys filtradas por tag Mundial 2026 + Latam.
4. Selecciona los 12 con checkbox "Select all visible".
5. Bulk Action Bar aparece slide-up: "✓ 12 jerseys seleccionadas · [+ TAG] [+ GRUPO] [📦 PROMOVER STOCK] ..."
6. Click [📦 PROMOVER STOCK] → BulkDropCreator modal.
7. Modal:
   - Dropdown "Aplicar template": selecciona "Drop estándar 7 días Q475".
   - Auto-pobla: duration_days=7, price_override=Q475, badge="GARANTIZADA"
   - Diego edita: publish_at=2026-05-15 18:00, copy override="Mundial 2026 Wave 1 · entrega Mayo"
8. Submit → Tauri `bulk_create_stock_overrides` ejecuta en transaction.
9. Confirmación: "12 overrides Stock creados · próximo: 2026-05-15 18:00"
10. Diego va a Stock > Calendario.
11. Calendario muestra block scheduled "🆕 DROP MUNDIAL WAVE 1" con duración 7 días, color amarillo (SCHEDULED).
12. Inbox event nuevo (después del cron next run): "Stock drop programado para 2026-05-15 18:00 · 12 jerseys".
13. Diego confirma visualmente que las fechas son correctas.

**Tiempo target:** 5-8 minutos.

**Componentes involucrados:** UniversoTable, UniversoPresets, BulkActionBar, BulkDropCreator, DropTemplatesList, CalendarTimeline, CalendarBlock.

**Tauri commands:** list_universo, list_drop_templates, bulk_create_stock_overrides, list_stock_calendar.

---

## Journey 3: Fix dirty publicado (foto rota)

**Trigger:** Inbox del Home muestra "🔴 3 publicados con foto rota detectada hoy".

**Flow:**

1. Diego clica [REVISAR] en el inbox event.
2. Navega a Vault > Publicados con filter "⚠ Necesita atención" pre-seleccionado.
3. Smart filter activo muestra 3 cards con badge "DIRTY" rojo.
4. Diego clica thumb de la primera card → modal grande FM-style abre en modo PUBLISHED.
5. Modal muestra hero + gallery + specs. La foto hero claramente está rota (404 image).
6. Diego clica "🔄 Re-fetch foto" en acciones del modal.
7. Tauri command `re_fetch_jersey_galleries(family_id)` ejecuta:
   - Re-fetch desde Yupoo con `--include-primary --force` (L9 + L18 del playbook)
   - Cache-bust URLs `?v={timestamp}` (L19 del playbook)
   - Limpia `dirty_flag = 0` si fetch exitoso
8. Toast verde "Re-fetch OK · 8 fotos · cache invalidado"
9. Modal refresca. Hero ahora muestra foto correcta.
10. Diego cierra modal. Card desaparece de smart filter "Necesita atención" (porque dirty=0).
11. Repite para las 2 jerseys restantes.
12. Inbox event "dirty_detected" auto-resuelve después de 4h cron run (cuando count vuelve a 0).

**Tiempo target:** 3-5 minutos para 3 jerseys.

**Componentes involucrados:** InboxFeed, EventCard, PublicadosTab, PublishedCard, AuditModal (modo PUBLISHED).

**Tauri commands:** dismiss_event, list_published(filter='attention'), re_fetch_jersey_galleries, toggle_dirty_flag.

---

## Journey 4: Crear nuevo grupo Eurocopa 2024

**Trigger:** Diego quiere agrupar 8 jerseys de Eurocopa 2024 que ya están publicadas.

**Flow:**

1. Diego abre Admin Web → Vault > Grupos.
2. Encuentra sección "🏆 COMPETICIÓN".
3. Tag "Eurocopa 2024" ya existe (pre-seeded) con 24 jerseys. Pero Diego quiere uno más curado.
4. Click [+ NEW] de Competición → modal Crear Tag.
5. Form:
   - Tipo: Competición (auto-poblado)
   - Display name: "Eurocopa 2024 Top 8"
   - Slug: auto-generado "eurocopa-2024-top-8"
   - Icon: 🏆
   - Color: "#1e3a8a" (azul Champions)
   - is_auto_derived: false
6. Submit → Tauri `create_tag` ejecuta. Tag aparece en lista.
7. Diego clica [VER] en el nuevo tag.
8. Drill modal abre vacío (0 jerseys asignadas).
9. Click "+ AGREGAR JERSEYS" → selector con search.
10. Diego escribe "Eurocopa 2024" → resultados filtrados a 24 jerseys.
11. Marca 8 de las 24 (las top performers según su criterio).
12. Click "Asignar 8 jerseys" → Tauri `bulk_assign_tag(tag_id, family_ids)`.
13. Validación: cardinalidad de Competición es N (no excluyente) → OK pasan todas.
14. Drill modal refresca: 8 jerseys aparecen como cards.
15. Diego cierra modal. Tag count actualiza: "Eurocopa 2024 Top 8: 8 jerseys".

**Tiempo target:** 4-6 minutos.

**Componentes involucrados:** GruposTab, TagsSection, CreateTagModal, DrillTagModal, JerseySelector.

**Tauri commands:** create_tag, bulk_assign_tag, list_jerseys_by_tag, search_jerseys.

---

## Journey 5: Cambiar branding del sitio (paleta nueva)

**Trigger:** Diego quiere probar un nuevo color accent (de verde a amarillo neon).

**Flow:**

1. Diego abre Admin Web → Site > Branding.
2. Vista mockup-8: izquierda controles + derecha preview live iframe.
3. Diego clica el swatch del color "Accent" (#4ade80).
4. Color picker abre.
5. Diego cambia a #facc15 (amarillo neon).
6. Iframe preview cambia inmediatamente (CSS variable update).
7. Banner "⚠ Cambios sin aplicar" aparece arriba del preview.
8. Diego ve cómo se ve el sitio con accent amarillo: hero CTA, navigation active, badges.
9. Decisión: le gusta. Click "APPLY · DEPLOY".
10. Confirm dialog: "Esto deploy a producción. ¿Confirmas?"
11. Confirm → Tauri `apply_branding_changes`:
    - UPDATE site_branding SET value=#facc15 WHERE key='palette.accent'
    - Trigger webhook a worker → invalidate CDN
    - Worker re-builds CSS bundle con nueva variable
12. Toast verde "Branding deployado · CDN invalidado · live en ~30s"
13. Diego abre `vault.elclub.club` en nueva tab → confirma color amarillo en sitio público.
14. Inbox event nuevo: "Branding cambió hace 0h · Diego tiene un preview pendiente" → ya resuelto porque applied.
15. Audit log entry: "diego changed branding palette.accent from #4ade80 to #facc15"

**Tiempo target:** 2-4 minutos.

**Componentes involucrados:** SiteShell, BrandingTab, ColorPicker, PreviewIframe.

**Tauri commands:** list_branding, set_branding, apply_branding_changes.

---

## Journey 6: Atender review pendiente

**Trigger:** Inbox event "12 reviews esperando moderación".

**Flow:**

1. Diego clica [MODERAR] en el inbox event → navega a Site > Comunidad.
2. Sub-tab "⭐ Reviews" activo. Filter "pending" pre-seleccionado.
3. Lista de 12 reviews ordenadas por submitted_at desc.
4. Diego clica en la primera:
   - Customer: Maria González
   - Jersey: ARG-2026-L-FS
   - Rating: 5 estrellas
   - Body: "Llegó super rápido y la calidad es increíble!"
   - Photos: 1 foto del unboxing
5. Acciones disponibles: [✓ Aprobar] [⭐ Featured] [❌ Rechazar] [💬 Responder]
6. Diego clica [⭐ Featured] (es review excelente con foto, vale para hero).
7. Tauri `moderate_review(id, status='featured')` ejecuta.
8. Review desaparece de filter "pending" (status cambió).
9. Diego repite para las 11 reviews restantes:
   - 9 reviews positivas → [✓ Aprobar]
   - 2 reviews mixed (3 estrellas con feedback constructivo) → [💬 Responder] primero, después [✓ Aprobar]
   - 0 reviews fake/spam → [❌ Rechazar]
10. Filter "pending" vacío. Inbox event auto-resuelve.

**Tiempo target:** 8-12 minutos.

**Componentes involucrados:** ComunidadTab, ReviewsList, ReviewDetail, ModerationActions, ReplyModal.

**Tauri commands:** list_reviews(status_filter=['pending']), moderate_review, reply_to_review.

---

## Journey 7: Diagnosticar caída del worker

**Trigger:** Inbox event crítico "🔴 Worker errores subieron a 2.4%".

**Flow:**

1. Diego clica [LOGS] en el inbox event → navega a Sistema > Status.
2. Banner "🟢 ALL OK" cambió a "🔴 1 ALERT CRITICAL".
3. Metric card "Error Rate" muestra 2.4% en rojo, sparkline arriba.
4. Diego clica en metric card → drill a vista detalle de error rate.
5. Vista detalle: gráfico 24h con spike claro hace 30 min.
6. Activity feed lista los errors más recientes:
   - 12:45 ✗ Error 500 en `/api/admin-web/kpis` · "TypeError: cannot read property"
   - 12:43 ✗ Error 500 en `/api/admin-web/kpis` · mismo error
   - ...repetido N veces
7. Diego identifica que el endpoint `/api/admin-web/kpis` está rompiendo.
8. Click "Ver Logs Completo" → tab Operaciones > Logs streaming.
9. Logs muestran stack trace completo. Diego identifica el bug en línea X.
10. Decisión: rollback al deploy anterior.
11. Tab Operaciones > Deploys: lista deploys recientes.
12. Last deploy: abcb9c4 · status='success' (mintió, está rompiendo).
13. Diego clica "🔙 Rollback al anterior" en el deploy actual.
14. Confirm → Tauri `rollback_deploy(deploy_id)`.
15. Worker rolls back a previous version. Toast "Rollback completado · monitoreando..."
16. Después de 5 min: error rate vuelve a 0.1%. Banner verde regresa.
17. Inbox event auto-resuelve.

**Tiempo target:** 10-15 minutos (depende de complejidad del bug).

**Componentes involucrados:** SistemaShell, StatusTab, MetricCard, ActivityFeed, OperacionesTab, DeploysList, LogsStreaming.

**Tauri commands:** get_health_snapshot, get_health_history, list_logs, list_deploy_history, rollback_deploy.

---

## Journey 8: Crear página de campaña con drop landing

**Trigger:** Diego va a lanzar una campaña Meta Ads y necesita una landing dedicada.

**Flow:**

1. Diego abre Site > Páginas.
2. Sub-categoría "🎯 Campañas" tiene 0 páginas hoy.
3. Click [+ NUEVA PÁGINA] → form modal:
   - Slug: "promo-mundial"
   - Title: "Mundial 2026 — Drop Especial"
   - Category: "campaign"
   - Status: draft
4. Submit → page creada vacía. Editor de bloques abre.
5. Diego construye la página agregando bloques:
   - Hero: "Mundial 2026 está acá. Tu jersey te elige."
   - CTA Button: "Ver Drop"
   - Gallery: thumbnails de 12 jerseys del drop (link al Vault filtrado)
   - Testimonials: 3 reviews featured de Mundial 2026
   - FAQ: 5 preguntas tipo "¿Cuándo entregan?" "¿Hay devoluciones?"
6. Cada bloque drag-drop para reordenar. Cada bloque tiene panel propiedades.
7. Diego termina. Click "💾 Guardar borrador".
8. Status sigue "draft". Diego ve preview en iframe abajo del editor.
9. Cuando todo OK: click "📅 Programar publicación" → input fecha:
   - publish_at: 2026-05-14 12:00
   - unpublish_at: 2026-05-30 23:59 (cuando termina campaña)
10. Submit → status="scheduled". Inbox event aparecerá 24h antes de unpublish.
11. Diego copia URL: `https://elclub.club/promo-mundial?utm_source=meta&utm_campaign=mundial2026`
12. Pega URL en Meta Ads Manager (separado).
13. El día 14, page auto-publish. Audit log: "page promo-mundial transitioned draft→live by cron"

**Tiempo target:** 15-25 minutos (la primera vez; después 5-10 min con templates).

**Componentes involucrados:** SiteShell, PaginasTab, CreatePageModal, BlockEditor, BlockTypes (Hero, CTA, Gallery, Testimonials, FAQ).

**Tauri commands:** create_page, update_page, publish_page, get_page_preview.

---

## Journey 9: Customer recibió jersey contra preferencias (handle excepción)

**Trigger:** Inbox event "🔴 Customer X recibió jersey contra prefs".

**Flow:**

1. Esta vez el evento es Comercial-side, pero el detector lo originó Admin Web (Mystery algorithm fallback).
2. Diego abre Comercial > Inbox (no Admin Web).
3. Event card: "Customer Pedro García recibió jersey ARG-2026-L-FS pero su wizard pedía evitar Argentina".
4. Diego clica [VER CUSTOMER] → Comercial > Customer detail de Pedro.
5. Customer detail muestra: order_id #1842, jersey entregada, prefs registradas.
6. Comercial detail tiene cross-link a Admin Web > Mystery > Universo filtrado por la jersey específica.
7. Diego ve histórico de entregas de ARG-2026-L-FS: 18 entregas, sin issues previos.
8. Decisión: compensar al customer. Acciones disponibles:
   - [📧 Email disculpa con Q50 cupón]
   - [🔄 Re-enviar otra jersey gratis]
   - [💬 WhatsApp directo]
9. Diego clica "📧 Email disculpa con Q50 cupón".
10. Tauri `send_email_template(template='apology_wrong_jersey', customer_id, custom_vars)` ejecuta:
    - Crea cupón único Q50
    - Envía email con template de Site > Comunicación
11. Toast "Email enviado · cupón APOL-2W3K-X9 creado"
12. Diego va a Mystery > Reglas (Admin Web).
13. Investiga por qué algoritmo eligió Argentina:
    - Click "Ver historial selecciones" → modal con últimas 50 selecciones
    - Filtra por customer_id de Pedro
    - Ve que algoritmo "hybrid" eligió ARG porque el pool sin Argentina dejaba <5 elegibles
    - Fallback ignored prefs como esperado
14. Diego decide ajustar reglas:
    - Cambiar fallback a "esperar customer service manual delivery" en lugar de ignorar prefs
    - Submit reglas
15. Audit log captura el cambio.
16. Inbox event original se resolve manualmente.

**Tiempo target:** 15-20 minutos.

**Componentes involucrados:** ComercialInbox, CustomerDetail, MysteryReglas, AlgorithmHistoryModal, EmailTemplates.

**Tauri commands:** get_customer, list_mystery_deliveries(customer_id), send_email_template, update_mystery_rules.

---

## Journey 10: Búsqueda rápida + ⌘K + atajos

**Trigger:** Diego necesita encontrar una jersey específica rápido.

**Flow:**

1. Diego está en cualquier vista del Admin Web (puede ser Sistema > Status).
2. Atajo `⌘K` → Command Palette overlay abre.
3. Diego escribe "argentina".
4. Resultados fuzzy search en orden:
   - Jersey: ARG-2026-L-FS · Argentina 2026 Local
   - Jersey: ARG-2026-V-FS · Argentina 2026 Visita
   - Jersey: ARG-2024-L-FS · Argentina 2024 Local
   - Tag: Argentina (país)
   - Action: "Ir a Vault > Universo · filter team=Argentina"
5. Diego presiona ↓ navega, selecciona la primera jersey.
6. Enter → modal grande de la jersey ARG-2026-L-FS abre en contexto actual.
7. Diego ve specs, decide editar tags. Cierra modal con `Esc`.
8. Atajo `g v` → navega a Vault (default tab Queue).
9. Atajo `g h` → vuelve al Home.
10. `?` → modal con cheat sheet de todos los atajos.
11. Diego ve atajos disponibles. Aprende uno nuevo: `n` jump to next jersey en queue.
12. Cierra modal con `Esc`.

**Tiempo target:** 30-60 segundos por búsqueda.

**Componentes involucrados:** CommandPalette, KeyboardShortcuts overlay, fuzzy search engine.

**Tauri commands:** search_global(query) — busca en jerseys + tags + customers + reviews.

---

## Resumen de cobertura

| Journey | Módulos involucrados | Funcionalidad probada |
|---|---|---|
| 1. Audit queue | Vault Queue | Audit existente intacto |
| 2. Drop Mundial Wave 1 | Vault Universo, Stock | Bulk + templates + calendario |
| 3. Fix dirty | Vault Publicados | Smart filters + modal extended + re-fetch |
| 4. Crear grupo nuevo | Vault Grupos | CRUD tags + drill view + bulk assign |
| 5. Cambiar branding | Site Branding | Live preview + apply + CDN invalidation |
| 6. Moderar reviews | Site Comunidad | Workflow inbound completo |
| 7. Worker caído | Sistema Status + Operaciones | Diagnóstico + rollback |
| 8. Página de campaña | Site Páginas | Block editor + scheduling |
| 9. Compensar cliente | Mystery + Comercial | Cross-module + algoritmo + emails |
| 10. ⌘K + atajos | Cross-module | Power user navigation |

Cada uno cubre 1-3 features clave del Admin Web. Si los 10 corren sin friction, el R7 + R7.1 + R7.2 + R7.3 están funcionalmente completos.

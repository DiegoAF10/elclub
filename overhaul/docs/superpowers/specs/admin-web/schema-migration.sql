-- =============================================================================
-- Admin Web — Schema Migration
-- =============================================================================
-- Para aplicar a: el-club/erp/elclub.db (SQLite local del ERP Tauri)
-- Versión target: ERP v0.2.0
-- Pre-requisito: Comercial R1 (v0.1.28) ya mergeado y deployed
-- Backup obligatorio antes de aplicar:
--   cp el-club/erp/elclub.db el-club/erp/elclub.backup-before-admin-web-r7.db
--
-- Aplicar con:
--   sqlite3 el-club/erp/elclub.db < schema-migration.sql
--
-- Idempotente: usa CREATE TABLE IF NOT EXISTS y verifica columnas antes de ALTER.
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

BEGIN TRANSACTION;

-- =============================================================================
-- 1. EXTENSIONES A TABLAS EXISTENTES
-- =============================================================================

-- audit_decisions: agregar campos para ARCHIVED state + dirty flag
-- (No usamos IF NOT EXISTS porque SQLite no lo soporta en ALTER. El check manual
--  se hace en el bridge Python antes de ejecutar este script.)

ALTER TABLE audit_decisions ADD COLUMN archived_at INTEGER;
ALTER TABLE audit_decisions ADD COLUMN dirty_flag INTEGER NOT NULL DEFAULT 0;
ALTER TABLE audit_decisions ADD COLUMN dirty_reason TEXT;
ALTER TABLE audit_decisions ADD COLUMN dirty_detected_at INTEGER;

-- Index para queries del Universo (filter por estado + flags)
CREATE INDEX IF NOT EXISTS idx_audit_archived ON audit_decisions(archived_at) WHERE archived_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_dirty ON audit_decisions(dirty_flag) WHERE dirty_flag = 1;
CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_decisions(status);

-- =============================================================================
-- 2. SISTEMA DE TAGS
-- =============================================================================

-- Tipos de tags: definidos en código + seedeados al inicio
CREATE TABLE IF NOT EXISTS tag_types (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  slug          TEXT NOT NULL UNIQUE,             -- 'competicion', 'geografia_region', etc.
  display_name  TEXT NOT NULL,                    -- 'Competición', 'Geografía Región'
  icon          TEXT,                             -- '🏆', '🌎'
  cardinality   TEXT NOT NULL CHECK (cardinality IN ('one', 'many')),
  display_order INTEGER NOT NULL DEFAULT 0,

  -- JSON de reglas condicionales:
  --   {"applies_when": {"tag_type": "tipo_equipo", "tag_slug": "club_pro"}}
  --   {"forbidden_when": {"tag_type": "tipo_equipo", "tag_slug": "seleccion_nacional"}}
  --   {"required_when": {"tag_type": "tipo_equipo", "tag_slug": "club_pro"}}
  conditional_rule TEXT,

  description   TEXT,
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

-- Tags individuales
CREATE TABLE IF NOT EXISTS tags (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  type_id         INTEGER NOT NULL REFERENCES tag_types(id) ON DELETE CASCADE,
  slug            TEXT NOT NULL,                    -- 'mundial-2026', 'sudamerica'
  display_name    TEXT NOT NULL,                    -- 'Mundial 2026', 'Sudamérica'
  icon            TEXT,                             -- '⚽', '🌎'
  color           TEXT,                             -- '#4ade80'
  is_auto_derived INTEGER NOT NULL DEFAULT 0,       -- 1 si lo calcula el sistema
  derivation_rule TEXT,                             -- JSON con la regla de auto-derivación
  is_deleted      INTEGER NOT NULL DEFAULT 0,       -- soft-delete
  display_order   INTEGER NOT NULL DEFAULT 0,
  created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  UNIQUE(type_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_tags_type ON tags(type_id) WHERE is_deleted = 0;
CREATE INDEX IF NOT EXISTS idx_tags_slug ON tags(slug) WHERE is_deleted = 0;

-- Asignación many-to-many jersey ↔ tag
CREATE TABLE IF NOT EXISTS jersey_tags (
  family_id     TEXT NOT NULL,                      -- referencia a catalog.json (no FK)
  tag_id        INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  assigned_at   INTEGER NOT NULL DEFAULT (unixepoch()),
  assigned_by   TEXT NOT NULL DEFAULT 'manual',     -- 'manual', 'auto:rule_id', 'bulk:user'
  PRIMARY KEY (family_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_jersey_tags_family ON jersey_tags(family_id);
CREATE INDEX IF NOT EXISTS idx_jersey_tags_tag ON jersey_tags(tag_id);

-- =============================================================================
-- 3. OVERRIDES POR PRODUCTO (Stock + Mystery)
-- =============================================================================

CREATE TABLE IF NOT EXISTS stock_overrides (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  family_id       TEXT NOT NULL,                    -- ref a catalog.json
  publish_at      INTEGER,                          -- NULL = DRAFT
  unpublish_at    INTEGER,                          -- NULL = permanente
  price_override  INTEGER,                          -- en centavos GTQ (ej. 47500 = Q475)
  badge           TEXT,                             -- 'GARANTIZADA', 'EXCLUSIVA', etc.
  copy_override   TEXT,                             -- copy custom para esta jersey en Stock
  priority        INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
  status          TEXT NOT NULL DEFAULT 'draft'     -- redundante con publish_at pero útil
                  CHECK (status IN ('draft', 'scheduled', 'live', 'ended', 'paused')),
  created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  created_by      TEXT NOT NULL DEFAULT 'diego'
);

CREATE INDEX IF NOT EXISTS idx_stock_family ON stock_overrides(family_id);
CREATE INDEX IF NOT EXISTS idx_stock_status ON stock_overrides(status);
CREATE INDEX IF NOT EXISTS idx_stock_publish_at ON stock_overrides(publish_at) WHERE publish_at IS NOT NULL;

CREATE TABLE IF NOT EXISTS mystery_overrides (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  family_id       TEXT NOT NULL,
  publish_at      INTEGER,
  unpublish_at    INTEGER,
  pool_weight     REAL NOT NULL DEFAULT 1.0,        -- multiplicador en algoritmo
  status          TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'scheduled', 'live', 'ended', 'paused')),
  created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  created_by      TEXT NOT NULL DEFAULT 'diego'
);

CREATE INDEX IF NOT EXISTS idx_mystery_family ON mystery_overrides(family_id);
CREATE INDEX IF NOT EXISTS idx_mystery_status ON mystery_overrides(status);

-- =============================================================================
-- 4. INBOX DE EVENTOS (Home)
-- =============================================================================

CREATE TABLE IF NOT EXISTS inbox_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  type          TEXT NOT NULL,                      -- 'queue_pending', 'dirty_detected', etc.
  severity      TEXT NOT NULL CHECK (severity IN ('critical', 'important', 'info')),
  title         TEXT NOT NULL,
  description   TEXT,
  action_label  TEXT,                               -- 'QUEUE', 'REVISAR', etc.
  action_target TEXT,                               -- '/admin-web/vault/queue'
  module        TEXT NOT NULL,                      -- 'vault', 'stock', 'mystery', 'site', 'sistema'
  metadata      TEXT,                               -- JSON con context específico del evento
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  dismissed_at  INTEGER,                            -- usuario lo dismisseó manualmente
  resolved_at   INTEGER,                            -- el sistema detectó que ya no aplica
  expires_at    INTEGER                             -- para auto-dismiss (info=3d, important=7d)
);

CREATE INDEX IF NOT EXISTS idx_inbox_active ON inbox_events(severity, created_at)
  WHERE dismissed_at IS NULL AND resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_inbox_expired ON inbox_events(expires_at)
  WHERE expires_at IS NOT NULL AND dismissed_at IS NULL;

-- =============================================================================
-- 5. SITE — Páginas, Componentes, Branding
-- =============================================================================

CREATE TABLE IF NOT EXISTS site_pages (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  slug          TEXT NOT NULL UNIQUE,
  title         TEXT NOT NULL,
  category      TEXT NOT NULL                       -- categorización en sub-listas
                CHECK (category IN ('static', 'dynamic_seo', 'campaign', 'catalog', 'account', 'special')),
  status        TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'live', 'scheduled')),
  publish_at    INTEGER,
  blocks        TEXT NOT NULL DEFAULT '[]',         -- JSON array de bloques (Notion-style)
  seo_meta      TEXT,                               -- JSON con title/description/og/etc
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_pages_status ON site_pages(status);
CREATE INDEX IF NOT EXISTS idx_pages_category ON site_pages(category);

CREATE TABLE IF NOT EXISTS site_components (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  type          TEXT NOT NULL,                      -- 'header', 'footer', 'banner_top', etc.
  config        TEXT NOT NULL DEFAULT '{}',         -- JSON con la config del componente
  enabled       INTEGER NOT NULL DEFAULT 1,
  publish_at    INTEGER,
  unpublish_at  INTEGER,
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE INDEX IF NOT EXISTS idx_components_type ON site_components(type);
CREATE INDEX IF NOT EXISTS idx_components_active ON site_components(enabled, publish_at, unpublish_at);

-- Branding como key-value para flexibilidad (paleta, fonts, logos, etc.)
CREATE TABLE IF NOT EXISTS site_branding (
  key         TEXT PRIMARY KEY,                     -- 'palette.primary', 'logo.dark', 'fonts.heading'
  value       TEXT NOT NULL,                        -- valor (color hex, URL, JSON, etc.)
  value_type  TEXT NOT NULL DEFAULT 'string'        -- 'string', 'color', 'url', 'json'
              CHECK (value_type IN ('string', 'color', 'url', 'json', 'number', 'boolean')),
  updated_at  INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_by  TEXT NOT NULL DEFAULT 'diego'
);

-- =============================================================================
-- 6. SITE — Comunicación (templates + workflows + listas)
-- =============================================================================

CREATE TABLE IF NOT EXISTS communication_templates (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  slug          TEXT NOT NULL UNIQUE,               -- 'order-confirmation', 'welcome-1'
  channel       TEXT NOT NULL CHECK (channel IN ('email', 'sms', 'whatsapp', 'web_push')),
  display_name  TEXT NOT NULL,
  subject       TEXT,                               -- para emails
  body          TEXT NOT NULL,                      -- contenido (puede ser HTML, plaintext, JSON)
  variables     TEXT,                               -- JSON array de variables usadas: ["customer_name", "order_id"]
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS subscriber_lists (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  slug          TEXT NOT NULL UNIQUE,
  display_name  TEXT NOT NULL,
  description   TEXT,
  segment_rule  TEXT,                               -- JSON con reglas dinámicas (NULL = manual)
  created_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS subscribers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT,
  phone         TEXT,
  name          TEXT,
  metadata      TEXT,                               -- JSON con cualquier extra
  subscribed_at INTEGER NOT NULL DEFAULT (unixepoch()),
  unsubscribed_at INTEGER,
  source        TEXT,                               -- 'newsletter_form', 'import', 'order'
  CHECK (email IS NOT NULL OR phone IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email) WHERE email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_subscribers_phone ON subscribers(phone) WHERE phone IS NOT NULL;

CREATE TABLE IF NOT EXISTS subscriber_list_members (
  list_id       INTEGER NOT NULL REFERENCES subscriber_lists(id) ON DELETE CASCADE,
  subscriber_id INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
  added_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  PRIMARY KEY (list_id, subscriber_id)
);

CREATE TABLE IF NOT EXISTS workflows (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  slug          TEXT NOT NULL UNIQUE,
  display_name  TEXT NOT NULL,
  trigger_type  TEXT NOT NULL,                      -- 'order_placed', 'cart_abandoned', etc.
  trigger_config TEXT,                              -- JSON con config del trigger
  steps         TEXT NOT NULL DEFAULT '[]',         -- JSON array de steps (template_id, delay, condition)
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

-- =============================================================================
-- 7. SITE — Comunidad (reviews + encuestas + feedback)
-- =============================================================================

CREATE TABLE IF NOT EXISTS reviews (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  family_id       TEXT,                             -- jersey específica (opcional)
  customer_id     INTEGER,                          -- ref a comercial.customers (cuando exista)
  rating          INTEGER CHECK (rating BETWEEN 1 AND 5),
  title           TEXT,
  body            TEXT NOT NULL,
  photo_urls      TEXT,                             -- JSON array de URLs
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected', 'featured')),
  moderation_note TEXT,
  submitted_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  moderated_at    INTEGER,
  moderated_by    TEXT
);

CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status, submitted_at);
CREATE INDEX IF NOT EXISTS idx_reviews_family ON reviews(family_id) WHERE family_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS surveys (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  slug          TEXT NOT NULL UNIQUE,
  display_name  TEXT NOT NULL,
  questions     TEXT NOT NULL DEFAULT '[]',         -- JSON array
  trigger       TEXT,                               -- 'pre_checkout', 'post_purchase', 'nps_quarterly'
  enabled       INTEGER NOT NULL DEFAULT 1,
  created_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS survey_responses (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  survey_id     INTEGER NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
  customer_id   INTEGER,
  answers       TEXT NOT NULL,                      -- JSON con respuestas
  submitted_at  INTEGER NOT NULL DEFAULT (unixepoch())
);

-- =============================================================================
-- 8. SISTEMA — Audit log + KPIs históricos + Health snapshots
-- =============================================================================

CREATE TABLE IF NOT EXISTS system_audit_log (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp     INTEGER NOT NULL DEFAULT (unixepoch()),
  user          TEXT NOT NULL DEFAULT 'diego',
  module        TEXT NOT NULL                       -- 'vault', 'stock', 'mystery', 'site', 'sistema'
                CHECK (module IN ('vault', 'stock', 'mystery', 'site', 'sistema')),
  action        TEXT NOT NULL,                      -- 'create', 'update', 'delete', 'archive', etc.
  entity_type   TEXT,                               -- 'jersey', 'tag', 'override', 'page', etc.
  entity_id     TEXT,                               -- id del afectado
  diff          TEXT,                               -- JSON con before/after de campos cambiados
  severity      TEXT NOT NULL DEFAULT 'info'
                CHECK (severity IN ('info', 'warning', 'critical')),
  ip_address    TEXT,
  user_agent    TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON system_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_module ON system_audit_log(module, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON system_audit_log(entity_type, entity_id);

-- KPIs históricos para sparklines del Home (snapshot diario por cron)
CREATE TABLE IF NOT EXISTS kpi_snapshots (
  date          TEXT NOT NULL,                      -- 'YYYY-MM-DD'
  kpi_key       TEXT NOT NULL,                      -- 'published_count', 'queue_count', etc.
  value         REAL NOT NULL,
  PRIMARY KEY (date, kpi_key)
);

CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_key_date ON kpi_snapshots(kpi_key, date DESC);

-- Health snapshots del sistema (worker uptime, latency, error rate)
CREATE TABLE IF NOT EXISTS health_snapshots (
  timestamp     INTEGER NOT NULL,
  metric_key    TEXT NOT NULL,                      -- 'worker_latency_p50', 'cdn_hit_rate', etc.
  value         REAL NOT NULL,
  PRIMARY KEY (timestamp, metric_key)
);

CREATE INDEX IF NOT EXISTS idx_health_metric ON health_snapshots(metric_key, timestamp DESC);

-- =============================================================================
-- 9. SISTEMA — Operaciones (scrap history, deploys, jobs/cron)
-- =============================================================================

CREATE TABLE IF NOT EXISTS scrap_history (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  category_url    TEXT NOT NULL,
  domain          TEXT,                             -- 'mundial2026', 'retros', etc. (auto-inferido)
  status          TEXT NOT NULL                     -- 'running', 'success', 'failed', 'cancelled'
                  CHECK (status IN ('running', 'success', 'failed', 'cancelled')),
  started_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  finished_at     INTEGER,
  firecrawl_credits_used INTEGER,
  families_created INTEGER,
  families_wiped   INTEGER,
  galleries_fetched INTEGER,
  errors          TEXT,                             -- log de errores si failed
  triggered_by    TEXT NOT NULL DEFAULT 'diego'
);

CREATE INDEX IF NOT EXISTS idx_scrap_status ON scrap_history(status, started_at DESC);

CREATE TABLE IF NOT EXISTS deploy_history (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  target          TEXT NOT NULL,                    -- 'worker', 'site', 'erp_msi'
  version         TEXT NOT NULL,
  commit_sha      TEXT,
  status          TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed', 'rolled_back')),
  started_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  finished_at     INTEGER,
  triggered_by    TEXT NOT NULL DEFAULT 'diego',
  release_notes   TEXT
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  slug            TEXT NOT NULL UNIQUE,             -- 'detect-dirty-galleries', 'kpi-snapshot-daily'
  display_name    TEXT NOT NULL,
  cron_expression TEXT NOT NULL,
  handler         TEXT NOT NULL,                    -- nombre de la función a invocar
  enabled         INTEGER NOT NULL DEFAULT 1,
  last_run_at     INTEGER,
  last_status     TEXT,                             -- 'success', 'failed'
  last_error      TEXT,
  next_run_at     INTEGER,
  created_at      INTEGER NOT NULL DEFAULT (unixepoch())
);

CREATE TABLE IF NOT EXISTS backups (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  type            TEXT NOT NULL CHECK (type IN ('catalog', 'db', 'r2_manifest', 'full')),
  path            TEXT NOT NULL,                    -- path local o R2 URL
  size_bytes      INTEGER,
  created_at      INTEGER NOT NULL DEFAULT (unixepoch()),
  triggered_by    TEXT NOT NULL DEFAULT 'cron',     -- 'cron' o 'diego' (manual)
  expires_at      INTEGER                           -- retention policy
);

CREATE INDEX IF NOT EXISTS idx_backups_type ON backups(type, created_at DESC);

-- =============================================================================
-- 10. CONFIGURACIÓN del módulo (key-value flexible)
-- =============================================================================

CREATE TABLE IF NOT EXISTS admin_web_config (
  key           TEXT PRIMARY KEY,                   -- 'feature_flags', 'bot.prompt', 'notifications.threshold'
  value         TEXT NOT NULL,                      -- valor (JSON serializado para tipos complejos)
  value_type    TEXT NOT NULL DEFAULT 'string'
                CHECK (value_type IN ('string', 'json', 'number', 'boolean')),
  updated_at    INTEGER NOT NULL DEFAULT (unixepoch())
);

-- Vistas guardadas (presets) del Universo del Vault y otras tablas densas
CREATE TABLE IF NOT EXISTS saved_views (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  module        TEXT NOT NULL,                      -- 'vault.universo', 'stock.universo', etc.
  slug          TEXT NOT NULL,
  display_name  TEXT NOT NULL,
  icon          TEXT,
  filters       TEXT NOT NULL DEFAULT '{}',         -- JSON con filtros aplicados
  sort          TEXT,                               -- JSON con sort config
  columns       TEXT,                               -- JSON con columnas visibles + orden
  is_factory    INTEGER NOT NULL DEFAULT 0,         -- preset de fábrica vs custom
  display_order INTEGER NOT NULL DEFAULT 0,
  created_at    INTEGER NOT NULL DEFAULT (unixepoch()),
  UNIQUE(module, slug)
);

CREATE INDEX IF NOT EXISTS idx_saved_views_module ON saved_views(module, display_order);

-- =============================================================================
-- 11. VIEWS HELPERS (queries comunes)
-- =============================================================================

-- Vista combinada: una jersey con su estado primario derivado
DROP VIEW IF EXISTS v_jersey_state;
CREATE VIEW v_jersey_state AS
SELECT
  ad.family_id,
  ad.sku,
  CASE
    WHEN ad.archived_at IS NOT NULL THEN 'ARCHIVED'
    WHEN ad.status = 'deleted' THEN 'REJECTED'
    WHEN ad.status = 'verified' AND ad.final_verified = 1 THEN 'PUBLISHED'
    WHEN ad.status = 'pending' THEN 'QUEUE'
    ELSE 'DRAFT'
  END AS state,
  ad.dirty_flag,
  ad.dirty_reason,
  ad.qa_priority,
  ad.archived_at,
  ad.created_at,
  ad.last_updated
FROM audit_decisions ad;

-- Vista del estado de overrides Stock con cómputo de status real
DROP VIEW IF EXISTS v_stock_status;
CREATE VIEW v_stock_status AS
SELECT
  so.*,
  CASE
    WHEN so.publish_at IS NULL THEN 'draft'
    WHEN so.publish_at > unixepoch() THEN 'scheduled'
    WHEN so.unpublish_at IS NOT NULL AND so.unpublish_at < unixepoch() THEN 'ended'
    ELSE 'live'
  END AS computed_status
FROM stock_overrides so;

DROP VIEW IF EXISTS v_mystery_status;
CREATE VIEW v_mystery_status AS
SELECT
  mo.*,
  CASE
    WHEN mo.publish_at IS NULL THEN 'draft'
    WHEN mo.publish_at > unixepoch() THEN 'scheduled'
    WHEN mo.unpublish_at IS NOT NULL AND mo.unpublish_at < unixepoch() THEN 'ended'
    ELSE 'live'
  END AS computed_status
FROM mystery_overrides mo;

-- Vista de count de inbox events activos por severidad (para badge del sidebar)
DROP VIEW IF EXISTS v_inbox_counts;
CREATE VIEW v_inbox_counts AS
SELECT
  severity,
  COUNT(*) AS count
FROM inbox_events
WHERE dismissed_at IS NULL
  AND resolved_at IS NULL
  AND (expires_at IS NULL OR expires_at > unixepoch())
GROUP BY severity;

-- =============================================================================
-- COMMIT
-- =============================================================================

COMMIT;

-- =============================================================================
-- POST-MIGRATION: aplicar seed de tag_types + tags + componentes default + etc
-- Ver: schema-seed.sql (separado para idempotencia)
-- =============================================================================

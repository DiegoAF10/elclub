// El Club ERP — Rust backend.
// Commands registrados con #[tauri::command] son invocables desde el frontend
// via `invoke('nombre', args)`. Todos async-safe.
//
// Invariantes sagrados enforced acá:
//   1. audit_decisions con final_verified=1 AND status='verified' NO se cambian
//      salvo override=true explícito.
//   2. catalog.json se escribe atómicamente (tmp + rename) + backup timestamped.
//   3. Paths resueltos por env vars con fallback a defaults cableados para la
//      máquina de Diego (C:/Users/Diego/...).

use serde::{Deserialize, Serialize};
use serde_json::{Value, Map};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

// ─── Errors ──────────────────────────────────────────────────────────
#[derive(Debug, thiserror::Error)]
pub enum ErpError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("SQL error: {0}")]
    Sql(#[from] rusqlite::Error),
    #[error("Sagrado violation on {sku}: {reason}")]
    Sagrado { sku: String, reason: String },
    #[error("Not found: {0}")]
    NotFound(String),
    #[error("Not implemented yet: {0}")]
    NotImplemented(&'static str),
    #[error("{0}")]
    Other(String),
}

// Tauri requires errors implement Serialize for the JS side.
// Usamos std::result::Result explícito porque más abajo redefinimos `Result`
// como alias sobre ErpError (pa' el resto del módulo).
impl serde::Serialize for ErpError {
    fn serialize<S>(&self, serializer: S) -> std::result::Result<S::Ok, S::Error>
    where
        S: serde::ser::Serializer,
    {
        serializer.serialize_str(self.to_string().as_ref())
    }
}

type Result<T> = std::result::Result<T, ErpError>;

// ─── Paths resolver ──────────────────────────────────────────────────

fn catalog_path() -> PathBuf {
    std::env::var("ERP_CATALOG_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            PathBuf::from(r"C:\Users\Diego\elclub-catalogo-priv\data\catalog.json")
        })
}

fn db_path() -> PathBuf {
    std::env::var("ERP_DB_PATH")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(r"C:\Users\Diego\el-club\erp\elclub.db"))
}

/// Validates `IMP-YYYY-MM-DD` format with real date check.
/// Cero dependencias nuevas — char check + chrono::NaiveDate parsing.
fn is_valid_import_id(s: &str) -> bool {
    if s.len() != 14 || !s.starts_with("IMP-") {
        return false;
    }
    let date_part = &s[4..]; // "YYYY-MM-DD"
    chrono::NaiveDate::parse_from_str(date_part, "%Y-%m-%d").is_ok()
}

fn catalog_repo_path() -> PathBuf {
    // Repo root de elclub-catalogo-priv (parent dir de data/catalog.json)
    std::env::var("ERP_CATALOG_REPO")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            let mut p = catalog_path();
            p.pop(); // data/
            p.pop(); // repo root
            p
        })
}

fn backup_dir() -> PathBuf {
    let mut p = catalog_path();
    p.pop(); // drop "catalog.json"
    p.push("backups");
    p
}

// ─── Filter shape (matchea TS ListFilter) ─────────────────────────────
#[derive(Debug, Deserialize, Default)]
pub struct ListFilter {
    pub published: Option<bool>,
    pub tier: Option<String>,
    pub status: Option<String>,
    pub category: Option<String>,
}

// ─── AuditDecision shape (matchea TS AuditDecision) ───────────────────
#[derive(Debug, Serialize)]
pub struct AuditDecision {
    pub sku: String,
    pub tier: Option<String>,
    pub status: String,
    pub final_verified: bool,
    pub qa_priority: bool,
    pub notes: Option<String>,
    pub decided_at: Option<String>,
    pub reviewed_at: Option<String>,
    pub final_verified_at: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct PhotoAction {
    pub family_id: String,
    pub original_url: Option<String>,
    pub original_index: Option<i64>,
    pub action: Option<String>,
    pub new_index: Option<i64>,
    pub is_new_hero: bool,
    pub processed_url: Option<String>,
    pub decided_at: Option<String>,
}

// ─── Importaciones (IMP-R1) ────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct Import {
    pub import_id: String,
    pub paid_at: Option<String>,
    pub arrived_at: Option<String>,
    pub supplier: String,
    pub bruto_usd: Option<f64>,
    pub shipping_gtq: Option<f64>,
    pub fx: f64,
    pub total_landed_gtq: Option<f64>,
    pub n_units: Option<i64>,
    pub unit_cost: Option<f64>,
    pub status: String,
    pub notes: Option<String>,
    pub created_at: String,
    pub tracking_code: Option<String>,
    pub carrier: String,
    pub lead_time_days: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct ImportItem {
    pub source_table: String,
    pub source_id: i64,
    pub import_id: String,
    pub family_id: Option<String>,
    pub jersey_id: Option<String>,
    pub size: Option<String>,
    pub player_name: Option<String>,
    pub player_number: Option<i64>,
    pub patch: Option<String>,
    pub version: Option<String>,
    pub unit_cost_usd: Option<f64>,
    pub unit_cost: Option<f64>,
    pub customer_id: Option<String>,
    pub customer_name: Option<String>,
    pub is_free_unit: bool,
}

#[derive(Debug, Serialize)]
pub struct ImportPulso {
    pub capital_amarrado_gtq: f64,
    pub closed_ytd_landed_gtq: f64,
    pub avg_landed_unit: Option<f64>,
    pub lead_time_avg_days: Option<f64>,
    pub wishlist_count: i64,
    pub free_units_unassigned: i64,
}

// ─── App state — cacheamos el catalog en memoria (se re-lee al mutate) ─

pub struct AppState {
    pub catalog_cache: Mutex<Option<Vec<Value>>>,
    pub catalog_mtime: Mutex<Option<std::time::SystemTime>>,
}

impl Default for AppState {
    fn default() -> Self {
        AppState {
            catalog_cache: Mutex::new(None),
            catalog_mtime: Mutex::new(None),
        }
    }
}

fn load_catalog(state: &AppState) -> Result<Vec<Value>> {
    let path = catalog_path();
    // Auto-invalidate cache si el archivo en disk cambió (ej. script externo,
    // git pull, backfill.py corriendo en paralelo). Comparamos mtime.
    let disk_mtime = fs::metadata(&path).and_then(|m| m.modified()).ok();
    {
        let mut cache = state.catalog_cache.lock().unwrap();
        let mut cached_mtime = state.catalog_mtime.lock().unwrap();
        if let Some(cached) = cache.as_ref() {
            // Si mtime matches lo que teníamos, cache válido
            if *cached_mtime == disk_mtime {
                return Ok(cached.clone());
            }
            // Mtime cambió — invalidar
            *cache = None;
            *cached_mtime = None;
        }
    }
    let raw = fs::read_to_string(&path)
        .map_err(|e| ErpError::Other(format!("Cannot read catalog at {:?}: {}", path, e)))?;
    let data: Vec<Value> = serde_json::from_str(&raw)?;
    {
        let mut cache = state.catalog_cache.lock().unwrap();
        let mut cached_mtime = state.catalog_mtime.lock().unwrap();
        *cache = Some(data.clone());
        *cached_mtime = disk_mtime;
    }
    Ok(data)
}

fn invalidate_catalog(state: &AppState) {
    *state.catalog_cache.lock().unwrap() = None;
    *state.catalog_mtime.lock().unwrap() = None;
}

// ─── Atomic write + backup ────────────────────────────────────────────

fn write_catalog_atomic(data: &[Value]) -> Result<()> {
    let path = catalog_path();
    let dir = path.parent().ok_or_else(|| {
        ErpError::Other(format!("Invalid catalog path (no parent): {:?}", path))
    })?;

    // 1. Backup primero
    let backup_d = backup_dir();
    fs::create_dir_all(&backup_d)?;
    let ts = chrono::Local::now().format("%Y%m%d-%H%M%S").to_string();
    let backup_file = backup_d.join(format!("catalog.backup-{}.json", ts));
    fs::copy(&path, &backup_file).ok(); // non-fatal si no existe aún

    // 2. Write a tmp en el mismo directorio (para que rename sea atomic en el mismo volumen)
    let tmp = dir.join(format!("catalog.json.tmp.{}", ts));
    let pretty = serde_json::to_string_pretty(data)?;
    fs::write(&tmp, &pretty)?;

    // 3. Rename atomic (Windows NTFS soporta overwrite con rename, ojo en otros FS)
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        // En Windows rename falla si target existe — usamos rename_file path
        if path.exists() {
            fs::remove_file(&path)?;
        }
        fs::rename(&tmp, &path)?;
        // Evita warning del import no usado en algunas builds
        let _ = std::fs::OpenOptions::new().write(true).custom_flags(0);
    }
    #[cfg(not(windows))]
    {
        fs::rename(&tmp, &path)?;
    }

    // 4. Retención de backups — mantener últimos 50
    prune_backups(&backup_d, 50).ok();

    Ok(())
}

/// Commit a catalog al disk + actualizar cache mtime. Úsese en lugar de
/// write_catalog_atomic + invalidate_catalog cuando querés mantener el cache
/// en memoria post-write (evita re-read innecesario).
fn write_catalog_atomic_keep_cache(data: &[Value], state: &AppState) -> Result<()> {
    write_catalog_atomic(data)?;
    // Actualizar cache con el new state + nuevo mtime (el del archivo recién escrito)
    let path = catalog_path();
    let new_mtime = fs::metadata(&path).and_then(|m| m.modified()).ok();
    *state.catalog_cache.lock().unwrap() = Some(data.to_vec());
    *state.catalog_mtime.lock().unwrap() = new_mtime;
    Ok(())
}

fn prune_backups(dir: &Path, keep: usize) -> Result<()> {
    let mut entries: Vec<_> = fs::read_dir(dir)?
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.file_name()
                .to_string_lossy()
                .starts_with("catalog.backup-")
        })
        .collect();
    entries.sort_by_key(|e| e.file_name());
    // Más viejos primero → los primeros (len-keep) se borran
    if entries.len() > keep {
        for e in entries.iter().take(entries.len() - keep) {
            let _ = fs::remove_file(e.path());
        }
    }
    Ok(())
}

// ─── DB helpers ──────────────────────────────────────────────────────

fn open_db() -> Result<rusqlite::Connection> {
    let path = db_path();
    let conn = rusqlite::Connection::open(&path)?;
    // PRAGMA WAL para coexistir con el ERP Streamlit abierto
    conn.pragma_update(None, "journal_mode", "WAL")?;
    conn.pragma_update(None, "busy_timeout", 5000)?;
    Ok(conn)
}

fn row_to_decision(row: &rusqlite::Row) -> rusqlite::Result<AuditDecision> {
    Ok(AuditDecision {
        sku: row.get("family_id")?,
        tier: row.get("tier").ok(),
        status: row.get::<_, Option<String>>("status")?.unwrap_or_else(|| "pending".to_string()),
        final_verified: row.get::<_, Option<i64>>("final_verified")?.unwrap_or(0) == 1,
        qa_priority: row.get::<_, Option<i64>>("qa_priority").unwrap_or(Some(0)).unwrap_or(0) == 1,
        notes: row.get("notes").ok(),
        decided_at: row.get("decided_at").ok(),
        reviewed_at: row.get("reviewed_at").ok(),
        final_verified_at: row.get("final_verified_at").ok(),
    })
}

// ═══════════════════════════════════════════════════════════════════════
// TAURI COMMANDS — Reads
// ═══════════════════════════════════════════════════════════════════════

#[tauri::command]
fn list_families(
    filter: Option<ListFilter>,
    state: tauri::State<AppState>,
) -> Result<Vec<Value>> {
    let catalog = load_catalog(&state)?;
    let f = filter.unwrap_or_default();
    let out: Vec<Value> = catalog
        .into_iter()
        .filter(|fam| {
            // Filter zombies: families con status='deleted' (post delete_family).
            // El entry queda en catalog para audit trail pero NO debe aparecer en UI.
            let status = fam.get("status").and_then(|v| v.as_str()).unwrap_or("");
            if status == "deleted" {
                return false;
            }
            if let Some(p) = f.published {
                let is_pub = fam.get("published").and_then(|v| v.as_bool()).unwrap_or(false);
                if is_pub != p {
                    return false;
                }
            }
            if let Some(ref cat) = f.category {
                let c = fam.get("category").and_then(|v| v.as_str()).unwrap_or("");
                if c != cat {
                    return false;
                }
            }
            true
        })
        .collect();
    Ok(out)
}

#[tauri::command]
fn get_family(id: String, state: tauri::State<AppState>) -> Result<Option<Value>> {
    let catalog = load_catalog(&state)?;
    Ok(catalog.into_iter().find(|f| {
        f.get("family_id").and_then(|v| v.as_str()).map(|s| s == id).unwrap_or(false)
    }))
}

#[tauri::command]
fn get_decision(sku: String) -> Result<Option<AuditDecision>> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT family_id, tier, status, final_verified, qa_priority,
                notes, decided_at, reviewed_at, final_verified_at
         FROM audit_decisions WHERE family_id = ?1",
    )?;
    let result = stmt.query_row([&sku], row_to_decision).ok();
    Ok(result)
}

#[tauri::command]
fn list_decisions(filter: Option<ListFilter>) -> Result<Vec<AuditDecision>> {
    let conn = open_db()?;
    let f = filter.unwrap_or_default();

    let mut q = String::from(
        "SELECT family_id, tier, status, final_verified, qa_priority,
                notes, decided_at, reviewed_at, final_verified_at
         FROM audit_decisions WHERE 1=1",
    );
    let mut params: Vec<String> = vec![];
    if let Some(ref t) = f.tier {
        q.push_str(" AND tier = ?");
        params.push(t.clone());
    }
    if let Some(ref s) = f.status {
        q.push_str(" AND status = ?");
        params.push(s.clone());
    }

    let mut stmt = conn.prepare(&q)?;
    let param_refs: Vec<&dyn rusqlite::ToSql> =
        params.iter().map(|p| p as &dyn rusqlite::ToSql).collect();
    let rows = stmt.query_map(param_refs.as_slice(), row_to_decision)?;
    let decisions: Vec<AuditDecision> = rows.filter_map(|r| r.ok()).collect();
    Ok(decisions)
}

#[tauri::command]
fn get_photo_actions(family_id: String) -> Result<Vec<PhotoAction>> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT family_id, original_url, original_index, action, new_index,
                is_new_hero, processed_url, decided_at
         FROM audit_photo_actions WHERE family_id = ?1 ORDER BY original_index",
    )?;
    let rows = stmt.query_map([&family_id], |row| {
        Ok(PhotoAction {
            family_id: row.get("family_id")?,
            original_url: row.get("original_url").ok(),
            original_index: row.get("original_index").ok(),
            action: row.get("action").ok(),
            new_index: row.get("new_index").ok(),
            is_new_hero: row.get::<_, Option<i64>>("is_new_hero")?.unwrap_or(0) == 1,
            processed_url: row.get("processed_url").ok(),
            decided_at: row.get("decided_at").ok(),
        })
    })?;
    Ok(rows.filter_map(|r| r.ok()).collect())
}

// ═══════════════════════════════════════════════════════════════════════
// TAURI COMMANDS — Writes (audit_decisions)
// ═══════════════════════════════════════════════════════════════════════

#[tauri::command]
fn set_decision_status(sku: String, status: String, override_sagrado: Option<bool>) -> Result<()> {
    let override_flag = override_sagrado.unwrap_or(false);
    let conn = open_db()?;

    // Sagrado check: si final_verified=1 AND current status='verified', rechazar cambio sin override.
    let current: Option<(Option<String>, i64)> = conn
        .query_row(
            "SELECT status, COALESCE(final_verified, 0) FROM audit_decisions WHERE family_id = ?1",
            [&sku],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .ok();

    if let Some((cur_status, fv)) = current.as_ref() {
        let is_sagrado = fv == &1i64 && cur_status.as_deref() == Some("verified");
        if is_sagrado && !override_flag && status != "verified" {
            return Err(ErpError::Sagrado {
                sku: sku.clone(),
                reason: format!(
                    "Cannot change status of final_verified=1 SKU from '{}' to '{}' without override=true",
                    cur_status.as_deref().unwrap_or("verified"),
                    status
                ),
            });
        }
    }

    let now = chrono::Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
    // UPSERT — el SKU puede NO tener row previa (scrape fresh sin seed_audit_queue
    // del Streamlit viejo). SQLite ON CONFLICT ...  DO UPDATE maneja ambos casos.
    conn.execute(
        "INSERT INTO audit_decisions (family_id, status, decided_at)
         VALUES (?1, ?2, ?3)
         ON CONFLICT(family_id) DO UPDATE SET status = excluded.status, decided_at = excluded.decided_at",
        rusqlite::params![sku, status, now],
    )?;
    Ok(())
}

#[tauri::command]
fn set_final_verified(sku: String, verified: bool) -> Result<()> {
    let conn = open_db()?;
    let now = chrono::Local::now().format("%Y-%m-%dT%H:%M:%S").to_string();
    let fv = if verified { 1 } else { 0 };
    // UPSERT — crear row si no existe
    conn.execute(
        "INSERT INTO audit_decisions (family_id, final_verified, final_verified_at)
         VALUES (?1, ?2, ?3)
         ON CONFLICT(family_id) DO UPDATE SET
             final_verified = excluded.final_verified,
             final_verified_at = CASE WHEN excluded.final_verified = 1 THEN excluded.final_verified_at ELSE final_verified_at END",
        rusqlite::params![sku, fv, now],
    )?;
    Ok(())
}

// ═══════════════════════════════════════════════════════════════════════
// TAURI COMMANDS — Writes (catalog.json)
// ═══════════════════════════════════════════════════════════════════════

fn find_family_mut<'a>(catalog: &'a mut [Value], family_id: &str) -> Option<&'a mut Map<String, Value>> {
    catalog
        .iter_mut()
        .filter_map(|v| v.as_object_mut())
        .find(|m| m.get("family_id").and_then(|v| v.as_str()).map(|s| s == family_id).unwrap_or(false))
}

#[tauri::command]
fn set_family_published(
    family_id: String,
    published: bool,
    state: tauri::State<AppState>,
) -> Result<()> {
    let mut catalog = load_catalog(&state)?;
    {
        let fam = find_family_mut(&mut catalog, &family_id)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", family_id)))?;
        fam.insert("published".to_string(), Value::Bool(published));
    }
    write_catalog_atomic_keep_cache(&catalog, &state)?;
    Ok(())
}

#[tauri::command]
fn set_family_featured(
    family_id: String,
    featured: bool,
    state: tauri::State<AppState>,
) -> Result<()> {
    let mut catalog = load_catalog(&state)?;
    {
        let fam = find_family_mut(&mut catalog, &family_id)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", family_id)))?;
        fam.insert("featured".to_string(), Value::Bool(featured));
    }
    write_catalog_atomic_keep_cache(&catalog, &state)?;
    Ok(())
}

#[tauri::command]
fn set_primary_modelo_idx(
    family_id: String,
    modelo_idx: u64,
    state: tauri::State<AppState>,
) -> Result<()> {
    let mut catalog = load_catalog(&state)?;
    {
        let fam = find_family_mut(&mut catalog, &family_id)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", family_id)))?;
        let modelos_len = fam
            .get("modelos")
            .and_then(|v| v.as_array())
            .map(|a| a.len())
            .unwrap_or(0);
        if modelos_len == 0 {
            return Err(ErpError::Other(
                "family no tiene modelos[] — no se puede setear primary".to_string(),
            ));
        }
        if (modelo_idx as usize) >= modelos_len {
            return Err(ErpError::Other(format!(
                "modelo_idx {} fuera de rango (family tiene {} modelos)",
                modelo_idx, modelos_len
            )));
        }
        // Capturar gallery + hero del primary ANTES de mutar fam
        // (evita conflicto de borrow del checker).
        let (primary_gallery, primary_hero) = {
            let modelos = fam
                .get("modelos")
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            let primary = modelos.get(modelo_idx as usize).cloned();
            let gallery = primary
                .as_ref()
                .and_then(|m| m.get("gallery").cloned());
            let hero = primary.as_ref().and_then(|m| {
                m.get("hero_thumbnail").cloned().or_else(|| {
                    m.get("gallery")
                        .and_then(|v| v.as_array())
                        .and_then(|a| a.first())
                        .cloned()
                })
            });
            (gallery, hero)
        };

        fam.insert(
            "primary_modelo_idx".to_string(),
            Value::Number(modelo_idx.into()),
        );
        if let Some(g) = primary_gallery {
            fam.insert("gallery".to_string(), g);
        }
        if let Some(h) = primary_hero {
            fam.insert("hero_thumbnail".to_string(), h);
        }
    }
    write_catalog_atomic_keep_cache(&catalog, &state)?;
    Ok(())
}

#[tauri::command]
fn set_family_archived(
    family_id: String,
    archived: bool,
    state: tauri::State<AppState>,
) -> Result<()> {
    let mut catalog = load_catalog(&state)?;
    {
        let fam = find_family_mut(&mut catalog, &family_id)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", family_id)))?;
        fam.insert("archived".to_string(), Value::Bool(archived));
    }
    write_catalog_atomic_keep_cache(&catalog, &state)?;
    Ok(())
}

/// Set simple field on modelo: price (number) / sizes (string) / notes (string)
/// No regenera SKU. Delega al Python bridge.
#[tauri::command]
async fn set_modelo_field(
    family_id: String,
    modelo_idx: u64,
    field: String,
    value: serde_json::Value,
    state: tauri::State<'_, AppState>,
) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "set_modelo_field",
        "fid": family_id,
        "modelo_idx": modelo_idx,
        "field": field,
        "value": value,
    });
    let _ = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking: {}", e)))??;
    invalidate_catalog(&state);
    Ok(())
}

#[derive(Debug, Serialize)]
pub struct SetFamilyVariantResult {
    pub ok: bool,
    pub old_variant: Option<String>,
    pub new_variant: Option<String>,
    pub old_skus: Vec<String>,
    pub new_skus: Vec<String>,
    pub migrated: Option<serde_json::Value>,
    pub error: Option<String>,
}

/// Cambia variant del family. Regenera SKUs + migra audit DB.
#[tauri::command]
async fn set_family_variant(
    family_id: String,
    new_variant: String,
    new_variant_label: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<SetFamilyVariantResult> {
    let payload = serde_json::json!({
        "cmd": "set_family_variant",
        "fid": family_id,
        "new_variant": new_variant,
        "new_variant_label": new_variant_label,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking: {}", e)))??;
    invalidate_catalog(&state);

    let to_string_vec = |v: &serde_json::Value| -> Vec<String> {
        v.as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|x| x.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default()
    };

    Ok(SetFamilyVariantResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        old_variant: result
            .get("old_variant")
            .and_then(|v| v.as_str())
            .map(String::from),
        new_variant: result
            .get("new_variant")
            .and_then(|v| v.as_str())
            .map(String::from),
        old_skus: result
            .get("old_skus")
            .map(to_string_vec)
            .unwrap_or_default(),
        new_skus: result
            .get("new_skus")
            .map(to_string_vec)
            .unwrap_or_default(),
        migrated: result.get("migrated").cloned(),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

#[tauri::command]
fn set_modelo_sold_out(
    family_id: String,
    modelo_idx: u64,
    sold_out: bool,
    state: tauri::State<AppState>,
) -> Result<()> {
    let mut catalog = load_catalog(&state)?;
    {
        let fam = find_family_mut(&mut catalog, &family_id)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", family_id)))?;
        let modelos = fam
            .get_mut("modelos")
            .and_then(|v| v.as_array_mut())
            .ok_or_else(|| ErpError::Other("family has no modelos[] array".to_string()))?;
        let modelo = modelos
            .get_mut(modelo_idx as usize)
            .ok_or_else(|| ErpError::NotFound(format!("modelo idx {}", modelo_idx)))?;
        let modelo_map = modelo
            .as_object_mut()
            .ok_or_else(|| ErpError::Other("modelo is not an object".to_string()))?;
        modelo_map.insert("sold_out".to_string(), Value::Bool(sold_out));
    }
    write_catalog_atomic_keep_cache(&catalog, &state)?;
    Ok(())
}

#[derive(Debug, Serialize)]
pub struct RemovePhotosResult {
    pub removed_from_catalog: u32,
    pub deleted_from_r2: u32,
    pub r2_failed: u32,
    pub r2_errors: Vec<String>,
}

/// Remueve fotos específicas (por índice) del gallery de un modelo.
/// Opcionalmente borra también los objetos de R2 (libera espacio).
#[tauri::command]
async fn remove_modelo_photos(
    family_id: String,
    modelo_idx: u64,
    photo_indices: Vec<u64>,
    also_delete_r2: Option<bool>,
    state: tauri::State<'_, AppState>,
) -> Result<RemovePhotosResult> {
    if photo_indices.is_empty() {
        return Ok(RemovePhotosResult {
            removed_from_catalog: 0,
            deleted_from_r2: 0,
            r2_failed: 0,
            r2_errors: vec![],
        });
    }
    let to_remove: std::collections::HashSet<u64> =
        photo_indices.iter().copied().collect();

    // 1. Mutate catalog in memory, capturar URLs removidas para R2 delete
    let mut catalog = load_catalog(&state)?;
    let mut removed_urls: Vec<String> = vec![];
    let removed_count;
    {
        let fam = find_family_mut(&mut catalog, &family_id)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", family_id)))?;

        let is_primary_modelo = fam
            .get("primary_modelo_idx")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
            == modelo_idx;

        let modelos = fam
            .get_mut("modelos")
            .and_then(|v| v.as_array_mut())
            .ok_or_else(|| ErpError::Other("family has no modelos[] array".to_string()))?;

        let modelo = modelos
            .get_mut(modelo_idx as usize)
            .ok_or_else(|| ErpError::NotFound(format!("modelo idx {}", modelo_idx)))?;

        let modelo_map = modelo
            .as_object_mut()
            .ok_or_else(|| ErpError::Other("modelo is not an object".to_string()))?;

        let gallery = modelo_map
            .get("gallery")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();

        let before_len = gallery.len();
        let mut kept: Vec<Value> = vec![];
        for (i, v) in gallery.into_iter().enumerate() {
            if to_remove.contains(&(i as u64)) {
                if let Some(url) = v.as_str() {
                    removed_urls.push(url.to_string());
                }
            } else {
                kept.push(v);
            }
        }
        removed_count = before_len - kept.len();

        modelo_map.insert("gallery".to_string(), Value::Array(kept.clone()));
        if let Some(new_hero) = kept.first() {
            modelo_map.insert("hero_thumbnail".to_string(), new_hero.clone());
        } else {
            modelo_map.insert("hero_thumbnail".to_string(), Value::Null);
        }

        if is_primary_modelo {
            fam.insert("gallery".to_string(), Value::Array(kept.clone()));
            if let Some(new_hero) = kept.first() {
                fam.insert("hero_thumbnail".to_string(), new_hero.clone());
            } else {
                fam.insert("hero_thumbnail".to_string(), Value::Null);
            }
        }
    }

    // 2. Persist catalog (ANTES de borrar R2, por si falla R2 al menos el catalog queda limpio)
    write_catalog_atomic_keep_cache(&catalog, &state)?;

    // 3. Opcionalmente borrar de R2
    let (deleted_r2, r2_failed, r2_errors) = if also_delete_r2.unwrap_or(false) && !removed_urls.is_empty() {
        let urls_clone = removed_urls.clone();
        let payload = serde_json::json!({
            "cmd": "delete_r2_objects",
            "urls": urls_clone,
        });
        let r2_result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
            .await
            .map_err(|e| ErpError::Other(format!("spawn_blocking: {}", e)))??;
        let deleted = r2_result.get("deleted").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        let failed = r2_result.get("failed").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
        let errors: Vec<String> = r2_result
            .get("errors")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|x| x.as_str().map(String::from)).collect())
            .unwrap_or_default();
        (deleted, failed, errors)
    } else {
        (0, 0, vec![])
    };

    Ok(RemovePhotosResult {
        removed_from_catalog: removed_count as u32,
        deleted_from_r2: deleted_r2,
        r2_failed,
        r2_errors,
    })
}

#[tauri::command]
fn update_gallery_order(
    canonical_fid: String,
    modelo_idx: u64,
    new_order: Vec<String>,
    state: tauri::State<AppState>,
) -> Result<()> {
    let mut catalog = load_catalog(&state)?;
    {
        let fam = find_family_mut(&mut catalog, &canonical_fid)
            .ok_or_else(|| ErpError::NotFound(format!("family_id {}", canonical_fid)))?;

        // Mutate modelos[idx].gallery
        let is_primary_modelo = {
            let pidx = fam
                .get("primary_modelo_idx")
                .and_then(|v| v.as_u64())
                .unwrap_or(0);
            pidx == modelo_idx
        };

        let modelos = fam
            .get_mut("modelos")
            .and_then(|v| v.as_array_mut())
            .ok_or_else(|| ErpError::Other("family has no modelos[] array".to_string()))?;

        let modelo = modelos
            .get_mut(modelo_idx as usize)
            .ok_or_else(|| ErpError::NotFound(format!("modelo idx {}", modelo_idx)))?;

        let modelo_map = modelo
            .as_object_mut()
            .ok_or_else(|| ErpError::Other("modelo is not an object".to_string()))?;

        let new_gallery_val =
            Value::Array(new_order.iter().cloned().map(Value::String).collect::<Vec<_>>());
        modelo_map.insert("gallery".to_string(), new_gallery_val.clone());

        // Hero sync: hero_thumbnail = gallery[0]. Sin esto, reorder dejaba el
        // hero apuntando a la foto vieja → vault.elclub.club mostraba imagen
        // distinta a la que el ERP pintaba como primary (foto con corona).
        let new_hero = new_order.first().cloned();
        if let Some(ref hero_url) = new_hero {
            modelo_map.insert("hero_thumbnail".to_string(), Value::String(hero_url.clone()));
        }

        // Sync top-level si es primary modelo
        if is_primary_modelo {
            fam.insert("gallery".to_string(), new_gallery_val);
            if let Some(ref hero_url) = new_hero {
                fam.insert("hero_thumbnail".to_string(), Value::String(hero_url.clone()));
            }
        }
    }
    write_catalog_atomic_keep_cache(&catalog, &state)?;
    Ok(())
}

// ═══════════════════════════════════════════════════════════════════════
// TAURI COMMANDS — External processes (deferred to v0.2)
// ═══════════════════════════════════════════════════════════════════════

#[derive(Debug, Deserialize)]
pub struct WatermarkArgs {
    pub family_id: String,
    pub modelo_idx: u64,
    pub photo_idx: u64,
    /// "auto" | "force" | "sd" | "gemini"
    pub mode: String,
}

#[derive(Debug, Serialize)]
pub struct WatermarkResult {
    pub ok: bool,
    pub new_url: Option<String>,
    pub error: Option<String>,
    pub stderr: Option<String>,
}

fn erp_scripts_dir() -> PathBuf {
    std::env::var("ERP_SCRIPTS_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(r"C:\Users\Diego\el-club\erp"))
}

fn python_exe() -> String {
    std::env::var("ERP_PYTHON").unwrap_or_else(|_| {
        // Default al Python instalado del sistema de Diego.
        // Si el PATH de Tauri tiene Python, `python` resuelve; sino usamos path absoluto.
        String::from(r"python")
    })
}

fn run_python_bridge(payload: &serde_json::Value) -> Result<serde_json::Value> {
    run_python_bridge_inner(payload, None)
}

/// Variante con app handle: emite eventos `bridge-progress` al frontend en
/// tiempo real cuando el bridge Python escribe líneas JSONL con __progress__
/// a stderr. Útil para batch operations largas.
fn run_python_bridge_with_progress(
    payload: &serde_json::Value,
    app: tauri::AppHandle,
) -> Result<serde_json::Value> {
    run_python_bridge_inner(payload, Some(app))
}

fn run_python_bridge_inner(
    payload: &serde_json::Value,
    app_handle: Option<tauri::AppHandle>,
) -> Result<serde_json::Value> {
    use std::io::{BufRead, BufReader, Write};
    use std::process::{Command, Stdio};
    use tauri::Emitter;

    #[cfg(windows)]
    use std::os::windows::process::CommandExt;
    #[cfg(windows)]
    const CREATE_NO_WINDOW: u32 = 0x08000000;

    let erp_dir = erp_scripts_dir();
    let script = erp_dir.join("scripts").join("erp_rust_bridge.py");
    if !script.exists() {
        return Err(ErpError::Other(format!(
            "Python bridge no encontrado en {:?}",
            script
        )));
    }

    let mut cmd = Command::new(python_exe());
    cmd.arg(script.as_os_str())
        .current_dir(&erp_dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    let mut child = cmd
        .spawn()
        .map_err(|e| ErpError::Other(format!("no se pudo ejecutar python: {}", e)))?;

    if let Some(stdin) = child.stdin.as_mut() {
        let json = serde_json::to_string(payload)?;
        stdin
            .write_all(json.as_bytes())
            .map_err(|e| ErpError::Other(format!("write stdin: {}", e)))?;
    }

    // Si nos dieron app_handle, leemos stderr en thread paralelo y emitimos
    // eventos tauri 'bridge-progress'. Sino, consumimos stderr con wait_with_output.
    let stderr_thread = if let Some(app) = app_handle {
        let stderr = child.stderr.take();
        if let Some(stderr) = stderr {
            let handle = app.clone();
            Some(std::thread::spawn(move || {
                let reader = BufReader::new(stderr);
                let mut accumulated = String::new();
                for line_result in reader.lines() {
                    let Ok(line) = line_result else { break };
                    accumulated.push_str(&line);
                    accumulated.push('\n');
                    // Try parse como JSON progress event
                    let trimmed = line.trim();
                    if trimmed.starts_with('{') {
                        if let Ok(v) = serde_json::from_str::<serde_json::Value>(trimmed) {
                            if v.get("__progress__")
                                .and_then(|x| x.as_bool())
                                .unwrap_or(false)
                            {
                                let _ = handle.emit("bridge-progress", v);
                                continue;
                            }
                        }
                    }
                    // Otras líneas stderr (logs Python) — quedan accumuladas
                }
                accumulated
            }))
        } else {
            None
        }
    } else {
        None
    };

    let output = child
        .wait_with_output()
        .map_err(|e| ErpError::Other(format!("wait python: {}", e)))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    // stderr: si el thread estaba leyéndolo, usamos lo que accumuló; sino, el output
    let stderr = if let Some(t) = stderr_thread {
        t.join().unwrap_or_default()
    } else {
        String::from_utf8_lossy(&output.stderr).to_string()
    };

    let line = stdout
        .lines()
        .rev()
        .find(|l| l.trim_start().starts_with('{'))
        .unwrap_or("");

    if line.is_empty() {
        return Err(ErpError::Other(format!(
            "Python bridge no devolvió JSON. stdout={:?} stderr={:?}",
            stdout, stderr
        )));
    }

    let mut parsed: serde_json::Value = serde_json::from_str(line)?;
    if let Some(obj) = parsed.as_object_mut() {
        if !stderr.is_empty() {
            obj.insert("_stderr".to_string(), serde_json::Value::String(stderr));
        }
    }
    Ok(parsed)
}

#[tauri::command]
async fn invoke_watermark(
    args: WatermarkArgs,
    state: tauri::State<'_, AppState>,
) -> Result<WatermarkResult> {
    let allowed = ["auto", "force", "sd", "gemini"];
    if !allowed.contains(&args.mode.as_str()) {
        return Err(ErpError::Other(format!(
            "mode inválido: {:?} — usar auto/force/sd/gemini",
            args.mode
        )));
    }

    let payload = serde_json::json!({
        "cmd": "regen_watermark",
        "fid": args.family_id,
        "modelo_idx": args.modelo_idx,
        "photo_idx": args.photo_idx,
        "mode": args.mode,
    });

    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;

    // Python saves catalog itself — invalidamos el cache local para forzar re-read
    // en el próximo listFamilies.
    invalidate_catalog(&state);

    let ok = result
        .get("ok")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let new_url = result
        .get("new_url")
        .and_then(|v| v.as_str())
        .map(String::from);
    let error = result
        .get("error")
        .and_then(|v| v.as_str())
        .map(String::from);
    let stderr = result
        .get("_stderr")
        .and_then(|v| v.as_str())
        .map(String::from);

    Ok(WatermarkResult {
        ok,
        new_url,
        error,
        stderr,
    })
}

#[derive(Debug, Serialize)]
pub struct PythonPingResult {
    pub ok: bool,
    pub deps: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct EditModeloTypeArgs {
    pub fid: String,
    pub modelo_idx: u64,
    pub new_type: String,
    pub new_sleeve: Option<String>,
    pub motivo: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct EditModeloTypeResult {
    pub ok: bool,
    pub old_sku: Option<String>,
    pub new_sku: Option<String>,
    pub old_type: Option<String>,
    pub new_type: Option<String>,
    pub migrated: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[tauri::command]
async fn edit_modelo_type(
    args: EditModeloTypeArgs,
    state: tauri::State<'_, AppState>,
) -> Result<EditModeloTypeResult> {
    let payload = serde_json::json!({
        "cmd": "edit_modelo_type",
        "fid": args.fid,
        "modelo_idx": args.modelo_idx,
        "new_type": args.new_type,
        "new_sleeve": args.new_sleeve,
        "motivo": args.motivo.unwrap_or_default(),
    });

    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    invalidate_catalog(&state);

    Ok(EditModeloTypeResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        old_sku: result
            .get("old_sku")
            .and_then(|v| v.as_str())
            .map(String::from),
        new_sku: result
            .get("new_sku")
            .and_then(|v| v.as_str())
            .map(String::from),
        old_type: result
            .get("old_type")
            .and_then(|v| v.as_str())
            .map(String::from),
        new_type: result
            .get("new_type")
            .and_then(|v| v.as_str())
            .map(String::from),
        migrated: result.get("migrated").cloned(),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NewFamilyData {
    pub team: String,
    pub season: String,
    pub variant: String,
    pub variant_label: Option<String>,
    pub category: Option<String>,
    pub meta_country: Option<String>,
    pub meta_league: Option<String>,
    pub meta_confederation: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MoveModeloArgs {
    pub source_fid: String,
    pub source_modelo_idx: Option<u64>,
    pub target_fid: Option<String>,
    pub new_family: Option<NewFamilyData>,
    pub absorb_all: Option<bool>,
}

#[derive(Debug, Serialize)]
pub struct MoveModeloResult {
    pub ok: bool,
    pub source_fid: Option<String>,
    pub target_fid: Option<String>,
    pub source_empty_now: bool,
    pub moved: u32,
    pub old_skus: Vec<String>,
    pub new_skus: Vec<String>,
    pub migrated: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[tauri::command]
async fn move_modelo(
    args: MoveModeloArgs,
    state: tauri::State<'_, AppState>,
) -> Result<MoveModeloResult> {
    let payload = serde_json::json!({
        "cmd": "move_modelo",
        "source_fid": args.source_fid,
        "source_modelo_idx": args.source_modelo_idx,
        "target_fid": args.target_fid,
        "new_family": args.new_family.map(|n| serde_json::json!({
            "team": n.team,
            "season": n.season,
            "variant": n.variant,
            "variant_label": n.variant_label,
            "category": n.category,
            "meta_country": n.meta_country,
            "meta_league": n.meta_league,
            "meta_confederation": n.meta_confederation,
        })),
        "absorb_all": args.absorb_all.unwrap_or(false),
    });

    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking: {}", e)))??;
    invalidate_catalog(&state);

    let to_strs = |v: &serde_json::Value| -> Vec<String> {
        v.as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|x| x.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default()
    };

    Ok(MoveModeloResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        source_fid: result
            .get("source_fid")
            .and_then(|v| v.as_str())
            .map(String::from),
        target_fid: result
            .get("target_fid")
            .and_then(|v| v.as_str())
            .map(String::from),
        source_empty_now: result
            .get("source_empty_now")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        moved: result.get("moved").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
        old_skus: result.get("old_skus").map(to_strs).unwrap_or_default(),
        new_skus: result.get("new_skus").map(to_strs).unwrap_or_default(),
        migrated: result.get("migrated").cloned(),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

#[derive(Debug, Deserialize)]
pub struct DeleteSkuArgs {
    pub sku: String,
    pub motivo: String,
}

#[derive(Debug, Serialize)]
pub struct DeleteSkuResult {
    pub ok: bool,
    pub family_deleted: bool,
    pub was_published: bool,
    pub committed: bool,
    pub error: Option<String>,
}

#[tauri::command]
async fn delete_sku(
    args: DeleteSkuArgs,
    state: tauri::State<'_, AppState>,
) -> Result<DeleteSkuResult> {
    if args.motivo.trim().is_empty() {
        return Err(ErpError::Other(
            "motivo requerido — explicá por qué se borra este SKU".to_string(),
        ));
    }

    let payload = serde_json::json!({
        "cmd": "delete_sku",
        "sku": args.sku,
        "motivo": args.motivo,
    });

    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    invalidate_catalog(&state);

    Ok(DeleteSkuResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        family_deleted: result
            .get("family_deleted")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        was_published: result
            .get("was_published")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        committed: result
            .get("committed")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeleteFamilyArgs {
    pub family_id: String,
    pub motivo: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DeleteFamilyResult {
    pub ok: bool,
    pub family_id: Option<String>,
    pub deleted_skus: Vec<String>,
    pub delete_log_rows: u32,
    pub was_published: bool,
    pub committed: bool,
    pub push_error: Option<String>,
    pub error: Option<String>,
}

/// Soft-delete de una family entera. Refuses si published=true.
/// - audit_decisions: status='deleted' para todos los SKUs
/// - audit_delete_log: row per SKU con motivo
/// - catalog: fam.status='deleted', modelos=[], published=false
/// - commit + push automático
#[tauri::command]
async fn delete_family(
    args: DeleteFamilyArgs,
    state: tauri::State<'_, AppState>,
) -> Result<DeleteFamilyResult> {
    if args.motivo.trim().is_empty() {
        return Err(ErpError::Other(
            "motivo requerido — explicá por qué se borra esta family".to_string(),
        ));
    }

    let payload = serde_json::json!({
        "cmd": "delete_family",
        "family_id": args.family_id,
        "motivo": args.motivo,
    });

    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    invalidate_catalog(&state);

    let to_strs = |v: &serde_json::Value| -> Vec<String> {
        v.as_array()
            .map(|a| {
                a.iter()
                    .filter_map(|s| s.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default()
    };

    Ok(DeleteFamilyResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        family_id: result
            .get("family_id")
            .and_then(|v| v.as_str())
            .map(String::from),
        deleted_skus: result
            .get("deleted_skus")
            .map(to_strs)
            .unwrap_or_default(),
        delete_log_rows: result
            .get("delete_log_rows")
            .and_then(|v| v.as_u64())
            .map(|n| n as u32)
            .unwrap_or(0),
        was_published: result
            .get("was_published")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        committed: result
            .get("committed")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        push_error: result
            .get("push_error")
            .and_then(|v| v.as_str())
            .map(String::from),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

/// Limpia el cache de catalog.json en memoria. Siguiente `list_families`
/// re-lee el archivo desde disco. Útil cuando ops/scraper escribió al catalog
/// y querés que la UI refresque sin reiniciar la app.
#[tauri::command]
fn invalidate_cache(state: tauri::State<AppState>) -> Result<()> {
    invalidate_catalog(&state);
    Ok(())
}

#[derive(Debug, Serialize)]
pub struct BackfillMetaResult {
    pub ok: bool,
    pub stats: Option<serde_json::Value>,
    pub error: Option<String>,
}

/// Corre backfill_catalog_meta.py vía bridge — llena meta_country, conf,
/// wc2026_eligible, primary_modelo_idx, prices default donde estén null.
/// Idempotente. Útil cuando aparece un warning L1 en checks pre-publish.
#[tauri::command]
async fn backfill_meta(state: tauri::State<'_, AppState>) -> Result<BackfillMetaResult> {
    let payload = serde_json::json!({ "cmd": "backfill_meta" });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    invalidate_catalog(&state);

    Ok(BackfillMetaResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        stats: result.get("stats").cloned(),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

#[derive(Debug, Serialize)]
pub struct BatchCleanResult {
    pub ok: bool,
    pub total: u32,
    pub cleaned: u32,
    pub failed: u32,
    pub skipped: u32,
    pub errors: Vec<String>,
}

// modelo_idx opcional: si presente, solo limpia ese modelo; sino limpia todo el family.
#[tauri::command]
async fn batch_clean_family(
    family_id: String,
    modelo_idx: Option<u64>,
    state: tauri::State<'_, AppState>,
    app: tauri::AppHandle,
) -> Result<BatchCleanResult> {
    let payload = if let Some(idx) = modelo_idx {
        serde_json::json!({
            "cmd": "batch_clean_family",
            "fid": family_id,
            "modelo_idx": idx,
        })
    } else {
        serde_json::json!({
            "cmd": "batch_clean_family",
            "fid": family_id,
        })
    };

    // Usamos la variante con progress: emite eventos 'bridge-progress' al frontend
    // en tiempo real mientras el bridge itera las fotos.
    let result =
        tauri::async_runtime::spawn_blocking(move || run_python_bridge_with_progress(&payload, app))
            .await
            .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;

    invalidate_catalog(&state);

    let errors: Vec<String> = result
        .get("errors")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    Ok(BatchCleanResult {
        ok: result.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
        total: result.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
        cleaned: result
            .get("cleaned")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as u32,
        failed: result.get("failed").and_then(|v| v.as_u64()).unwrap_or(0) as u32,
        skipped: result
            .get("skipped")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as u32,
        errors,
    })
}

/// Abre la carpeta con los .msi de updates en Windows Explorer.
#[tauri::command]
fn open_msi_folder() -> Result<()> {
    // Path fijo — la carpeta de builds de Tauri en Diego's machine.
    // Si Diego mueve el repo, setear ERP_MSI_FOLDER env var.
    let path = std::env::var("ERP_MSI_FOLDER").unwrap_or_else(|_| {
        r"C:\Users\Diego\el-club\overhaul\src-tauri\target\release\bundle\msi".to_string()
    });
    std::process::Command::new("explorer.exe")
        .arg(&path)
        .spawn()
        .map_err(|e| ErpError::Other(format!("no se pudo abrir Explorer: {}", e)))?;
    Ok(())
}

#[tauri::command]
async fn python_ping() -> Result<PythonPingResult> {
    let payload = serde_json::json!({ "cmd": "ping" });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(PythonPingResult {
        ok: result
            .get("ok")
            .and_then(|v| v.as_bool())
            .unwrap_or(false),
        deps: result.get("deps").cloned(),
        error: result
            .get("error")
            .and_then(|v| v.as_str())
            .map(String::from),
    })
}

#[derive(Debug, Serialize)]
pub struct CommitResult {
    pub ok: bool,
    pub commit_sha: Option<String>,
    pub pushed: bool,
    pub nothing_to_commit: bool,
    pub error: Option<String>,
    pub stdout: Option<String>,
}

fn run_git(cwd: &Path, args: &[&str]) -> std::result::Result<String, (String, String)> {
    let out = std::process::Command::new("git")
        .current_dir(cwd)
        .args(args)
        .output()
        .map_err(|e| (format!("git not available: {}", e), String::new()))?;

    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).to_string();

    if !out.status.success() {
        return Err((stderr, stdout));
    }

    Ok(stdout)
}

#[tauri::command]
async fn commit_and_push(message: String) -> Result<CommitResult> {
    tauri::async_runtime::spawn_blocking(move || commit_and_push_sync(message))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

fn commit_and_push_sync(message: String) -> Result<CommitResult> {
    let repo = catalog_repo_path();
    if !repo.exists() {
        return Err(ErpError::Other(format!(
            "Catalog repo not found at {:?}",
            repo
        )));
    }

    // 1. Stage el catalog.json
    run_git(&repo, &["add", "data/catalog.json"])
        .map_err(|(e, _)| ErpError::Other(format!("git add failed: {}", e)))?;

    // 2. Check si hay cambios staged
    let status = run_git(&repo, &["status", "--porcelain", "data/catalog.json"])
        .map_err(|(e, _)| ErpError::Other(format!("git status failed: {}", e)))?;

    if status.trim().is_empty() {
        return Ok(CommitResult {
            ok: true,
            commit_sha: None,
            pushed: false,
            nothing_to_commit: true,
            error: None,
            stdout: Some("nothing to commit".into()),
        });
    }

    // 3. Commit
    let commit_msg = if message.trim().is_empty() {
        format!(
            "ERP audit update — {}",
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S")
        )
    } else {
        message
    };
    run_git(&repo, &["commit", "-m", &commit_msg])
        .map_err(|(stderr, stdout)| {
            ErpError::Other(format!("git commit failed: {}\n{}", stderr, stdout))
        })?;

    // 4. Get SHA
    let sha_raw = run_git(&repo, &["rev-parse", "HEAD"])
        .map_err(|(e, _)| ErpError::Other(format!("git rev-parse failed: {}", e)))?;
    let sha = sha_raw.trim().chars().take(8).collect::<String>();

    // 5. Push — puede fallar por auth, red, branch divergence, etc.
    //    Devolvemos commit_sha igual aunque falle el push (commit ya existe local).
    match run_git(&repo, &["push", "origin", "main"]) {
        Ok(_) => Ok(CommitResult {
            ok: true,
            commit_sha: Some(sha),
            pushed: true,
            nothing_to_commit: false,
            error: None,
            stdout: None,
        }),
        Err((stderr, stdout)) => Ok(CommitResult {
            ok: false,
            commit_sha: Some(sha),
            pushed: false,
            nothing_to_commit: false,
            error: Some(format!("git push failed (commit saved locally): {}", stderr)),
            stdout: Some(stdout),
        }),
    }
}

#[derive(Debug, Serialize)]
pub struct GitStatusInfo {
    pub clean: bool,
    pub catalog_changed: bool,
    pub changed_lines: String,
    pub ahead: u32,
    pub behind: u32,
}

#[tauri::command]
async fn git_status() -> Result<GitStatusInfo> {
    tauri::async_runtime::spawn_blocking(git_status_sync)
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

fn git_status_sync() -> Result<GitStatusInfo> {
    let repo = catalog_repo_path();
    if !repo.exists() {
        return Err(ErpError::Other(format!(
            "Catalog repo not found at {:?}",
            repo
        )));
    }
    let porcelain = run_git(&repo, &["status", "--porcelain"])
        .map_err(|(e, _)| ErpError::Other(e))?;
    let catalog_changed = porcelain
        .lines()
        .any(|l| l.contains("data/catalog.json"));

    // Ahead/behind
    let (mut ahead, mut behind) = (0u32, 0u32);
    if let Ok(rev_list) = run_git(
        &repo,
        &[
            "rev-list",
            "--left-right",
            "--count",
            "origin/main...HEAD",
        ],
    ) {
        let parts: Vec<&str> = rev_list.split_whitespace().collect();
        if parts.len() == 2 {
            behind = parts[0].parse().unwrap_or(0);
            ahead = parts[1].parse().unwrap_or(0);
        }
    }

    Ok(GitStatusInfo {
        clean: porcelain.trim().is_empty(),
        catalog_changed,
        changed_lines: porcelain,
        ahead,
        behind,
    })
}

// ─── Health check ────────────────────────────────────────────────────
#[derive(Debug, Serialize)]
pub struct HealthStatus {
    pub catalog_path: String,
    pub catalog_exists: bool,
    pub catalog_size_bytes: Option<u64>,
    pub db_path: String,
    pub db_exists: bool,
    pub version: &'static str,
}

#[tauri::command]
fn erp_health() -> HealthStatus {
    let c = catalog_path();
    let d = db_path();
    let size = fs::metadata(&c).ok().map(|m| m.len());
    HealthStatus {
        catalog_path: c.display().to_string(),
        catalog_exists: c.exists(),
        catalog_size_bytes: size,
        db_path: d.display().to_string(),
        db_exists: d.exists(),
        version: env!("CARGO_PKG_VERSION"),
    }
}

// ─── Comercial R1 ──────────────────────────────────────────

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListEventsFilter {
    pub status: Option<String>,
    pub severity: Option<String>,
}

#[tauri::command]
async fn comercial_list_events(filter: ListEventsFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_events",
        "status": filter.status,
        "severity": filter.severity,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;

    Ok(result.get("events").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_set_event_status(event_id: i64, status: String) -> Result<()> {
    let payload = serde_json::json!({ "cmd": "set_event_status", "eventId": event_id, "status": status });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

// IMPORTANT: `ref` is a reserved keyword in Rust. Use a struct with serde rename:
#[derive(Debug, Deserialize)]
pub struct GetOrderArgs {
    #[serde(rename = "ref")]
    pub reff: String,
}

#[tauri::command]
async fn comercial_get_order(args: GetOrderArgs) -> Result<Option<Value>> {
    let payload = serde_json::json!({ "cmd": "get_order", "ref": args.reff });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("order").cloned().filter(|v| !v.is_null()))
}

#[derive(Debug, Deserialize)]
pub struct MarkShippedArgs {
    #[serde(rename = "ref")]
    pub reff: String,
    #[serde(rename = "trackingCode")]
    pub tracking_code: Option<String>,
}

#[tauri::command]
async fn comercial_mark_order_shipped(args: MarkShippedArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "mark_order_shipped",
        "ref": args.reff,
        "trackingCode": args.tracking_code,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[tauri::command]
async fn comercial_list_sales_in_range(start: String, end: String) -> Result<Vec<Value>> {
    let payload = serde_json::json!({ "cmd": "list_sales_in_range", "start": start, "end": end });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("sales").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_list_leads_in_range(start: String, end: String) -> Result<Vec<Value>> {
    let payload = serde_json::json!({ "cmd": "list_leads_in_range", "start": start, "end": end });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("leads").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

// IMPORTANT: Python's cmd_list_ad_spend_in_range returns the array under key "adSpend"
// (camelCase), NOT "ad_spend". This was fixed in Task 10 fix commit 631f8f1.
// Use "adSpend" in result.get(...) below.
#[tauri::command]
async fn comercial_list_ad_spend_in_range(start: String, end: String) -> Result<Vec<Value>> {
    let payload = serde_json::json!({ "cmd": "list_ad_spend_in_range", "start": start, "end": end });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("adSpend").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct InsertEventArgs {
    #[serde(rename = "type")]
    pub type_: String,
    pub severity: String,
    pub title: String,
    pub sub: Option<String>,
    pub items_affected: Vec<Value>,
}

#[tauri::command]
async fn comercial_insert_event(args: InsertEventArgs) -> Result<i64> {
    let payload = serde_json::json!({
        "cmd": "insert_event",
        "type": args.type_,
        "severity": args.severity,
        "title": args.title,
        "sub": args.sub,
        "itemsAffected": args.items_affected,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("eventId").and_then(|v| v.as_i64()).unwrap_or(-1))
}

// ─── Comercial R2-combo ────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SyncManychatArgs {
    pub since: Option<String>,
    pub worker_base: Option<String>,
    pub dashboard_key: String,
}

#[tauri::command]
async fn comercial_sync_manychat(args: SyncManychatArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "sync_manychat",
        "since": args.since,
        "workerBase": args.worker_base,
        "dashboardKey": args.dashboard_key,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListLeadsFilter {
    pub status: Option<String>,
    pub range_start: Option<String>,
    pub range_end: Option<String>,
}

#[tauri::command]
async fn comercial_list_leads(filter: ListLeadsFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_leads",
        "status": filter.status,
        "rangeStart": filter.range_start,
        "rangeEnd": filter.range_end,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("leads").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListConvsFilter {
    pub outcome: Option<String>,
    pub range_start: Option<String>,
    pub range_end: Option<String>,
    pub lead_id: Option<i64>,
}

#[tauri::command]
async fn comercial_list_conversations(filter: ListConvsFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_conversations",
        "outcome": filter.outcome,
        "rangeStart": filter.range_start,
        "rangeEnd": filter.range_end,
        "leadId": filter.lead_id,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("conversations").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[derive(Debug, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ListCustomersFilter {
    pub last_order_before: Option<String>,
    pub min_ltv_gtq: Option<f64>,
}

#[tauri::command]
async fn comercial_list_customers(filter: ListCustomersFilter) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "list_customers",
        "lastOrderBefore": filter.last_order_before,
        "minLtvGtq": filter.min_ltv_gtq,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("customers").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

#[tauri::command]
async fn comercial_get_meta_sync(source: String) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_meta_sync", "source": source });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("metaSync").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetConvMessagesArgs {
    pub conv_id: String,
    pub worker_base: Option<String>,
    pub dashboard_key: String,
}

#[tauri::command]
async fn comercial_get_conversation_messages(args: GetConvMessagesArgs) -> Result<Vec<Value>> {
    let payload = serde_json::json!({
        "cmd": "get_conversation_messages",
        "convId": args.conv_id,
        "workerBase": args.worker_base,
        "dashboardKey": args.dashboard_key,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("messages").and_then(|v| v.as_array()).cloned().unwrap_or_default())
}

// ─── Comercial R4 ──────────────────────────────────────────────────────────
// NOTE: Commands taking struct args expect TS callers to wrap as `{ args: {...} }`
// (pattern established by R1 Task 4 fix 1708b12). The primitive-arg command below
// (`comercial_get_customer_profile`) takes `{ customerId }` directly without wrap.
// DEFERRED to R5: `comercial_generate_coupon` — pending Task 0 worker endpoint
// confirmation (current /api/coupons/generate uses COUPON_API_KEY + ig_user_id
// dedup, incompatible with the planned customer_id + amount/percent contract).

#[tauri::command]
async fn comercial_get_customer_profile(customer_id: i64) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_customer_profile", "customerId": customer_id });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("profile").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateCustomerArgs {
    pub name: String,
    pub phone: Option<String>,
    pub email: Option<String>,
    pub source: Option<String>,
}

#[tauri::command]
async fn comercial_create_customer(args: CreateCustomerArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "create_customer",
        "name": args.name,
        "phone": args.phone,
        "email": args.email,
        "source": args.source,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateTraitsArgs {
    pub customer_id: i64,
    pub traits_json: Value,
}

#[tauri::command]
async fn comercial_update_customer_traits(args: UpdateTraitsArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "update_customer_traits",
        "customerId": args.customer_id,
        "traitsJson": args.traits_json,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SetBlockedArgs {
    pub customer_id: i64,
    pub blocked: bool,
}

#[tauri::command]
async fn comercial_set_customer_blocked(args: SetBlockedArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "set_customer_blocked",
        "customerId": args.customer_id,
        "blocked": args.blocked,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateSourceArgs {
    pub customer_id: i64,
    pub source: Option<String>,
}

#[tauri::command]
async fn comercial_update_customer_source(args: UpdateSourceArgs) -> Result<()> {
    let payload = serde_json::json!({
        "cmd": "update_customer_source",
        "customerId": args.customer_id,
        "source": args.source,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(())
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateManualOrderArgs {
    pub customer_id: i64,
    pub items: Vec<Value>,
    pub payment_method: String,
    pub fulfillment_status: String,
    pub shipping_fee: Option<f64>,
    pub discount: Option<f64>,
    pub notes: Option<String>,
    // R10 new fields:
    pub modality: Option<String>,
    pub origin: Option<String>,
    pub shipping_method: Option<String>,
    pub shipping_address: Option<Value>,
    pub occurred_at: Option<String>,
}

#[tauri::command]
async fn comercial_create_manual_order(args: CreateManualOrderArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "create_manual_order",
        "customerId": args.customer_id,
        "items": args.items,
        "paymentMethod": args.payment_method,
        "fulfillmentStatus": args.fulfillment_status,
        "shippingFee": args.shipping_fee,
        "discount": args.discount,
        "notes": args.notes,
        "modality": args.modality,
        "origin": args.origin,
        "shippingMethod": args.shipping_method,
        "shippingAddress": args.shipping_address,
        "occurredAt": args.occurred_at,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

// ─── Comercial R10 ─────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SearchCustomersArgs {
    pub query: String,
}

#[tauri::command]
async fn comercial_search_customers(args: SearchCustomersArgs) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "search_customers", "query": args.query });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("customers").cloned().unwrap_or(Value::Array(vec![])))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateSaleArgs {
    pub sale_id: i64,
    pub occurred_at: Option<String>,
    pub modality: Option<String>,
    pub origin: Option<String>,
    pub payment_method: Option<String>,
    pub fulfillment_status: Option<String>,
    pub shipping_method: Option<String>,
    pub tracking_code: Option<String>,
    pub shipping_fee: Option<f64>,
    pub discount: Option<f64>,
    pub notes: Option<String>,
    pub shipping_address: Option<Value>,
    pub customer_id: Option<i64>,
}

#[tauri::command]
async fn comercial_update_sale(args: UpdateSaleArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "update_sale",
        "saleId": args.sale_id,
        "occurredAt": args.occurred_at,
        "modality": args.modality,
        "origin": args.origin,
        "paymentMethod": args.payment_method,
        "fulfillmentStatus": args.fulfillment_status,
        "shippingMethod": args.shipping_method,
        "trackingCode": args.tracking_code,
        "shippingFee": args.shipping_fee,
        "discount": args.discount,
        "notes": args.notes,
        "shippingAddress": args.shipping_address,
        "customerId": args.customer_id,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

// ─── Comercial R5 ──────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SyncMetaAdsArgs {
    pub days: Option<i64>,
    pub date_preset: Option<String>,
}

#[tauri::command]
async fn comercial_sync_meta_ads(args: SyncMetaAdsArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "sync_meta_ads",
        "days": args.days,
        "datePreset": args.date_preset,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListCampaignsArgs {
    pub period_days: Option<i64>,
}

#[tauri::command]
async fn comercial_list_campaigns(args: ListCampaignsArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "list_campaigns",
        "periodDays": args.period_days,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("campaigns").cloned().unwrap_or(Value::Array(vec![])))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetCampaignDetailArgs {
    pub campaign_id: String,
    pub period_days: Option<i64>,
}

#[tauri::command]
async fn comercial_get_campaign_detail(args: GetCampaignDetailArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "get_campaign_detail",
        "campaignId": args.campaign_id,
        "periodDays": args.period_days,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("detail").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetFunnelAwarenessRealArgs {
    pub period_start: Option<String>,
    pub period_end: Option<String>,
}

#[tauri::command]
async fn comercial_get_funnel_awareness_real(args: GetFunnelAwarenessRealArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "get_funnel_awareness_real",
        "periodStart": args.period_start,
        "periodEnd": args.period_end,
    });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("awareness").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GenerateCouponArgs {
    pub customer_id: i64,
    #[serde(rename = "type")]
    pub type_: String,
    pub value: f64,
    pub expires_in_days: Option<i64>,
}

#[tauri::command]
async fn comercial_generate_coupon(args: GenerateCouponArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "generate_coupon",
        "customerId": args.customer_id,
        "type": args.type_,
        "value": args.value,
        "expiresInDays": args.expires_in_days,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

// ─── Comercial R6 ──────────────────────────────────────────────────────────

#[tauri::command]
async fn comercial_backfill_sales_attribution() -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "backfill_sales_attribution" });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[tauri::command]
async fn comercial_get_sale_attribution(sale_id: i64) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_sale_attribution", "saleId": sale_id });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("attribution").cloned().unwrap_or(Value::Null))
}

// ─── Comercial R7 ─────────────────────────────────────────────────────────

#[tauri::command]
async fn comercial_get_conversation_meta(conv_id: String) -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "get_conversation_meta", "convId": conv_id });
    let result = tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))??;
    Ok(result.get("conversation").cloned().unwrap_or(Value::Null))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AttributeSaleArgs {
    pub sale_id: i64,
    pub campaign_id: Option<String>,
    pub note: Option<String>,
}

#[tauri::command]
async fn comercial_attribute_sale(args: AttributeSaleArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "attribute_sale",
        "saleId": args.sale_id,
        "campaignId": args.campaign_id,
        "note": args.note,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[tauri::command]
async fn comercial_import_orders_from_worker() -> Result<Value> {
    let payload = serde_json::json!({ "cmd": "import_orders_from_worker" });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListSalesArgs {
    pub search: Option<String>,
    pub status: Option<String>,
    pub payment_method: Option<String>,
    pub period_days: Option<i64>,
    pub limit: Option<i64>,
    pub offset: Option<i64>,
}

#[tauri::command]
async fn comercial_list_sales(args: ListSalesArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "list_sales",
        "search": args.search,
        "status": args.status,
        "paymentMethod": args.payment_method,
        "periodDays": args.period_days,
        "limit": args.limit,
        "offset": args.offset,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

// ─── Comercial R11 ───────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ReplaceSaleItemsArgs {
    pub sale_id: i64,
    pub items: Vec<Value>,
}

#[tauri::command]
async fn comercial_replace_sale_items(args: ReplaceSaleItemsArgs) -> Result<Value> {
    let payload = serde_json::json!({
        "cmd": "replace_sale_items",
        "saleId": args.sale_id,
        "items": args.items,
    });
    tauri::async_runtime::spawn_blocking(move || run_python_bridge(&payload))
        .await
        .map_err(|e| ErpError::Other(format!("spawn_blocking join: {}", e)))?
}

// ─── Importaciones commands (IMP-R1) ─────────────────────────────────

#[tauri::command]
async fn cmd_list_imports(_app: tauri::AppHandle) -> Result<Vec<Import>> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73) as fx, total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL') as carrier, lead_time_days
         FROM imports
         -- NULLs last via boolean trick, equivalent to NULLS LAST
         ORDER BY paid_at IS NULL, paid_at DESC, created_at DESC"
    )?;

    let rows = stmt.query_map([], |row| {
        Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        })
    })?;

    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}

#[tauri::command]
async fn cmd_get_import(_app: tauri::AppHandle, import_id: String) -> Result<Import> {
    let conn = open_db()?;
    let imp = conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![import_id],
        |row| Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        }),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;
    Ok(imp)
}

#[tauri::command]
async fn cmd_get_import_items(_app: tauri::AppHandle, import_id: String) -> Result<Vec<ImportItem>> {
    let conn = open_db()?;

    // TODO(IMP-R4): replace `is_free_unit` heuristic with JOIN against
    // import_free_unit. Current heuristic flags ANY zero-cost item as free.
    let mut stmt = conn.prepare(
        "SELECT 'sale_items' as source_table, i.item_id as source_id, i.import_id,
                i.family_id, i.jersey_id, i.size,
                json_extract(i.personalization_json, '$.name') as player_name,
                CAST(json_extract(i.personalization_json, '$.number') AS INTEGER) as player_number,
                json_extract(i.personalization_json, '$.patch') as patch,
                i.version,
                i.unit_cost_usd, i.unit_cost,
                s.customer_id, c.name as customer_name,
                CASE WHEN i.unit_cost_usd = 0 OR i.unit_cost = 0 THEN 1 ELSE 0 END as is_free_unit
         FROM sale_items i
         LEFT JOIN sales s ON s.sale_id = i.sale_id
         LEFT JOIN customers c ON c.customer_id = s.customer_id
         WHERE i.import_id = ?1
         UNION ALL
         SELECT 'jerseys' as source_table, j.rowid as source_id, j.import_id,
                j.jersey_id as family_id, j.jersey_id, j.size,
                j.player_name, j.player_number, j.patches as patch, j.variant as version,
                j.unit_cost_usd, j.cost as unit_cost,
                NULL as customer_id, NULL as customer_name,
                0 as is_free_unit
         FROM jerseys j
         WHERE j.import_id = ?1
         ORDER BY source_table, source_id"
    )?;

    let rows = stmt.query_map(rusqlite::params![import_id], |row| {
        Ok(ImportItem {
            source_table:   row.get(0)?,
            source_id:      row.get(1)?,
            import_id:      row.get(2)?,
            family_id:      row.get(3)?,
            jersey_id:      row.get(4)?,
            size:           row.get(5)?,
            player_name:    row.get(6)?,
            player_number:  row.get(7)?,
            patch:          row.get(8)?,
            version:        row.get(9)?,
            unit_cost_usd:  row.get(10)?,
            unit_cost:      row.get(11)?,
            customer_id:    row.get(12)?,
            customer_name:  row.get(13)?,
            is_free_unit:   row.get::<_, i64>(14)? != 0,
        })
    })?;

    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}

#[tauri::command]
async fn cmd_get_import_pulso(_app: tauri::AppHandle) -> Result<ImportPulso> {
    let conn = open_db()?;

    let capital: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status IN ('paid', 'in_transit', 'arrived')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let closed_ytd: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status = 'closed'
           AND substr(arrived_at, 1, 4) = strftime('%Y', 'now', 'localtime')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let avg_landed: Option<f64> = conn.query_row(
        "SELECT AVG(unit_cost) FROM imports WHERE status = 'closed' AND unit_cost IS NOT NULL",
        [], |r| r.get(0),
    ).ok().flatten();

    let lead_avg: Option<f64> = conn.query_row(
        "SELECT AVG(lead_time_days) FROM imports
         WHERE status = 'closed' AND lead_time_days IS NOT NULL",
        [], |r| r.get(0),
    ).ok().flatten();

    let wishlist: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_wishlist WHERE status = 'active'",
        [], |r| r.get(0),
    ).unwrap_or(0);

    let free_unassigned: i64 = conn.query_row(
        "SELECT COUNT(*) FROM import_free_unit WHERE destination = 'unassigned'",
        [], |r| r.get(0),
    ).unwrap_or(0);

    Ok(ImportPulso {
        capital_amarrado_gtq: capital,
        closed_ytd_landed_gtq: closed_ytd,
        avg_landed_unit: avg_landed,
        lead_time_avg_days: lead_avg,
        wishlist_count: wishlist,
        free_units_unassigned: free_unassigned,
    })
}

// ─── Close import (destructive · transactional) ─────────────────────

#[derive(Debug, Serialize)]
pub struct CloseImportResult {
    pub ok: bool,
    pub n_items_updated: usize,
    pub n_jerseys_updated: usize,
    pub total_landed_gtq: f64,
    pub avg_unit_cost: f64,
    pub method: &'static str,
}

/// Closes an import batch, applying D2=B proportional landed cost prorrateo to all
/// linked sale_items + jerseys, and updating the imports row to status='closed'.
///
/// Pre-condition: status != 'closed' AND bruto_usd IS NOT NULL AND shipping_gtq IS NOT NULL.
/// Post-condition: all linked items have `unit_cost` set (GTQ landed) · imports.status='closed'
/// + total_landed_gtq + n_units + unit_cost + lead_time_days populated.
///
/// Refactored 2026-04-28 from inline #[tauri::command] to impl/cmd split per
/// convention block lib.rs:2730-2742 · zero behavior change · prerequisite for
/// R4 free-units auto-create modification (Task 5).
pub async fn impl_close_import_proportional(
    import_id: String,
) -> Result<CloseImportResult> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // 1. Read import row + status check
    let (bruto_usd, shipping_gtq, fx, status): (Option<f64>, Option<f64>, f64, String) = tx.query_row(
        "SELECT bruto_usd, shipping_gtq, COALESCE(fx, 7.73), status FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    if status == "closed" {
        return Err(ErpError::Other(format!("Import {} ya está closed", import_id)));
    }

    let bruto = bruto_usd.ok_or_else(|| ErpError::Other("bruto_usd is null".into()))?;
    let shipping = shipping_gtq.ok_or_else(|| ErpError::Other(
        "shipping_gtq is null · necesita registrar arrival con DHL invoice antes de cerrar".into()
    ))?;

    let total_landed = bruto * fx + shipping;

    // 2. Read all items (sale_items + jerseys) con sus unit_cost_usd
    //    NOTE: sale_items PK is item_id (per Task 3 verification), not id
    let sale_items: Vec<(i64, Option<f64>)> = tx.prepare(
        "SELECT item_id, unit_cost_usd FROM sale_items WHERE import_id = ?1"
    )?.query_map(rusqlite::params![&import_id], |r| Ok((r.get(0)?, r.get(1)?)))?
       .collect::<std::result::Result<Vec<_>, _>>()?;

    let jerseys: Vec<(i64, Option<f64>)> = tx.prepare(
        "SELECT rowid, unit_cost_usd FROM jerseys WHERE import_id = ?1"
    )?.query_map(rusqlite::params![&import_id], |r| Ok((r.get(0)?, r.get(1)?)))?
       .collect::<std::result::Result<Vec<_>, _>>()?;

    let n_total = sale_items.len() + jerseys.len();
    if n_total == 0 {
        return Err(ErpError::Other("No items linkeados a este import".into()));
    }

    // 3. Compute total USD (D2=B). Items con unit_cost_usd null → default uniforme = bruto/n
    let usd_default = bruto / n_total as f64;
    let total_usd_present: f64 = sale_items.iter().chain(jerseys.iter())
        .map(|(_, usd)| usd.unwrap_or(usd_default)).sum();

    // 4. Aplicar prorrateo proporcional al USD chino per item
    for (id, usd_opt) in &sale_items {
        let usd = usd_opt.unwrap_or(usd_default);
        let landed_gtq = (usd / total_usd_present) * total_landed;
        tx.execute(
            "UPDATE sale_items SET unit_cost = ? WHERE item_id = ?",
            rusqlite::params![landed_gtq.round() as i64, id],
        )?;
    }
    for (rowid, usd_opt) in &jerseys {
        let usd = usd_opt.unwrap_or(usd_default);
        let landed_gtq = (usd / total_usd_present) * total_landed;
        tx.execute(
            "UPDATE jerseys SET cost = ? WHERE rowid = ?",
            rusqlite::params![landed_gtq.round() as i64, rowid],
        )?;
    }

    // 5. Update imports row: status, totals, lead time
    let avg_unit = total_landed / n_total as f64;
    let lead_time = tx.query_row(
        "SELECT CAST((julianday(arrived_at) - julianday(paid_at)) AS INTEGER)
         FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |r| r.get::<_, Option<i64>>(0),
    ).unwrap_or(None);

    tx.execute(
        "UPDATE imports SET
            status = 'closed',
            total_landed_gtq = ?,
            n_units = ?,
            unit_cost = ?,
            lead_time_days = ?
         WHERE import_id = ?",
        rusqlite::params![total_landed, n_total as i64, avg_unit.round(), lead_time, import_id],
    )?;

    tx.commit()?;

    Ok(CloseImportResult {
        ok: true,
        n_items_updated: sale_items.len(),
        n_jerseys_updated: jerseys.len(),
        total_landed_gtq: total_landed,
        avg_unit_cost: avg_unit,
        method: "D2=B (proportional by USD)",
    })
}

#[tauri::command]
async fn cmd_close_import_proportional(
    _app: tauri::AppHandle,
    import_id: String,
) -> Result<CloseImportResult> {
    impl_close_import_proportional(import_id).await
}

/// Re-reads canonical Import row by ID. Used by all impl_X commands after tx.commit().
/// Caller must pass the still-open `conn` (post-commit) to avoid WAL footgun.
fn read_import_by_id(conn: &rusqlite::Connection, import_id: &str) -> Result<Import> {
    conn.query_row(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                COALESCE(fx, 7.73), total_landed_gtq, n_units, unit_cost,
                status, notes, created_at,
                tracking_code, COALESCE(carrier, 'DHL'), lead_time_days
         FROM imports WHERE import_id = ?1",
        rusqlite::params![import_id],
        |row| Ok(Import {
            import_id:        row.get(0)?,
            paid_at:          row.get(1)?,
            arrived_at:       row.get(2)?,
            supplier:         row.get(3)?,
            bruto_usd:        row.get(4)?,
            shipping_gtq:     row.get(5)?,
            fx:               row.get(6)?,
            total_landed_gtq: row.get(7)?,
            n_units:          row.get(8)?,
            unit_cost:        row.get(9)?,
            status:           row.get(10)?,
            notes:            row.get(11)?,
            created_at:       row.get(12)?,
            tracking_code:    row.get(13)?,
            carrier:          row.get(14)?,
            lead_time_days:   row.get(15)?,
        }),
    ).map_err(ErpError::from)
}

// ─── R4: Free units ledger ──────────────────────────────────────────
//
// Convention (per lib.rs:2730-2742): impl_X (pub testable) + cmd_X (#[tauri::command] shim).
//
// NULL convention para `destination` (decisión Diego 2026-04-28):
// - destination: None  = sin asignar (default al INSERT desde close_import_proportional)
// - destination: Some(s) = asignada a 'vip' | 'mystery' | 'garantizada' | 'personal'
// - destination_ref: customer_id si destination='vip' · texto libre para los demás
// - cmd_unassign_free_unit resetea destination a NULL (NO a la string 'unassigned')
// - VALID_FREE_DESTINATIONS Rust constant SOLO contiene los 4 destinos reales (no 'unassigned')

const VALID_FREE_DESTINATIONS: &[&str] = &["vip", "mystery", "garantizada", "personal"];

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FreeUnit {
    pub free_unit_id: i64,
    pub import_id: String,
    pub family_id: Option<String>,
    pub jersey_id: Option<String>,
    pub destination: Option<String>,
    pub destination_ref: Option<String>,
    pub assigned_at: Option<String>,
    pub assigned_by: Option<String>,
    pub notes: Option<String>,
    pub created_at: String,
    // Joined fields del import (display sin extra query)
    pub import_supplier: Option<String>,
    pub import_paid_at: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FreeUnitFilter {
    pub import_id: Option<String>,
    pub destination: Option<String>,
    pub status: Option<String>, // 'assigned' (NOT NULL) / 'unassigned' (NULL)
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AssignFreeUnitInput {
    pub free_unit_id: i64,
    pub destination: String,
    pub destination_ref: Option<String>,
    pub family_id: Option<String>,
    pub jersey_id: Option<String>,
    pub notes: Option<String>,
}

/// Reads free units with optional filter. Joins `imports` for supplier/paid_at display.
/// Pure read · no transaction needed.
pub fn impl_list_free_units(filter: Option<FreeUnitFilter>) -> Result<Vec<FreeUnit>> {
    let conn = open_db()?;

    let mut sql = String::from(
        "SELECT fu.free_unit_id, fu.import_id, fu.family_id, fu.jersey_id, \
                fu.destination, fu.destination_ref, fu.assigned_at, fu.assigned_by, \
                fu.notes, fu.created_at, i.supplier, i.paid_at \
         FROM import_free_unit fu \
         LEFT JOIN imports i ON i.import_id = fu.import_id \
         WHERE 1=1"
    );
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    if let Some(ref f) = filter {
        if let Some(ref imp_id) = f.import_id {
            sql.push_str(" AND fu.import_id = ?");
            params.push(Box::new(imp_id.clone()));
        }
        if let Some(ref status) = f.status {
            match status.as_str() {
                "assigned" => sql.push_str(" AND fu.destination IS NOT NULL"),
                "unassigned" => sql.push_str(" AND fu.destination IS NULL"),
                _ => return Err(ErpError::Other(format!("invalid status filter: {}", status))),
            }
        }
        if let Some(ref dest) = f.destination {
            if dest == "unassigned" {
                sql.push_str(" AND fu.destination IS NULL");
            } else {
                sql.push_str(" AND fu.destination = ?");
                params.push(Box::new(dest.clone()));
            }
        }
    }
    sql.push_str(" ORDER BY fu.created_at DESC, fu.free_unit_id DESC");

    let params_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|b| b.as_ref()).collect();
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(params_refs.as_slice(), |row| {
        Ok(FreeUnit {
            free_unit_id: row.get(0)?,
            import_id: row.get(1)?,
            family_id: row.get(2)?,
            jersey_id: row.get(3)?,
            destination: row.get(4)?,
            destination_ref: row.get(5)?,
            assigned_at: row.get(6)?,
            assigned_by: row.get(7)?,
            notes: row.get(8)?,
            created_at: row.get(9)?,
            import_supplier: row.get(10)?,
            import_paid_at: row.get(11)?,
        })
    })?;

    let mut out = Vec::new();
    for r in rows {
        out.push(r?);
    }
    Ok(out)
}

#[tauri::command]
async fn cmd_list_free_units(filter: Option<FreeUnitFilter>) -> Result<Vec<FreeUnit>> {
    impl_list_free_units(filter)
}

/// Assigns a free unit to a destination. Transactional. Validates:
/// - destination must be in VALID_FREE_DESTINATIONS (Rust-enforced · spec sec 7)
/// - free_unit_id must exist + currently unassigned (destination IS NULL)
/// - if destination='vip', destination_ref must be a valid customer_id
pub fn impl_assign_free_unit(input: AssignFreeUnitInput) -> Result<FreeUnit> {
    // 1. validate destination
    if !VALID_FREE_DESTINATIONS.contains(&input.destination.as_str()) {
        return Err(ErpError::Other(format!(
            "invalid destination '{}'; must be one of {:?}",
            input.destination, VALID_FREE_DESTINATIONS
        )));
    }

    // 2. VIP requires destination_ref
    if input.destination == "vip" && input.destination_ref.is_none() {
        return Err(ErpError::Other(
            "destination_ref required when destination='vip' (must be customer_id)".to_string(),
        ));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // 3. fetch + lock current row · ensure exists + unassigned
    let current_dest: Option<String> = tx.query_row(
        "SELECT destination FROM import_free_unit WHERE free_unit_id = ?",
        rusqlite::params![input.free_unit_id],
        |r| r.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            ErpError::NotFound(format!("free_unit_id {}", input.free_unit_id))
        }
        other => other.into(),
    })?;
    if let Some(existing) = current_dest {
        return Err(ErpError::Other(format!(
            "free_unit_id {} already assigned to '{}' · use unassign first",
            input.free_unit_id, existing
        )));
    }

    // 4. if VIP, validate customer_id exists
    if input.destination == "vip" {
        let cust_ref = input.destination_ref.as_ref().unwrap();
        let exists: bool = tx
            .query_row(
                "SELECT 1 FROM customers WHERE customer_id = ?",
                rusqlite::params![cust_ref],
                |_| Ok(true),
            )
            .unwrap_or(false);
        if !exists {
            return Err(ErpError::Other(format!(
                "customer_id '{}' not found",
                cust_ref
            )));
        }
    }

    // 5. UPDATE row
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();
    tx.execute(
        "UPDATE import_free_unit SET \
           destination = ?, destination_ref = ?, family_id = ?, jersey_id = ?, \
           assigned_at = ?, assigned_by = 'diego', notes = COALESCE(?, notes) \
         WHERE free_unit_id = ?",
        rusqlite::params![
            input.destination,
            input.destination_ref,
            input.family_id,
            input.jersey_id,
            now,
            input.notes,
            input.free_unit_id
        ],
    )?;

    tx.commit()?;

    // 6. re-read + return
    let target_id = input.free_unit_id;
    let updated = impl_list_free_units(None)?
        .into_iter()
        .find(|fu| fu.free_unit_id == target_id)
        .ok_or_else(|| ErpError::Other("free unit vanished post-update".to_string()))?;
    Ok(updated)
}

#[tauri::command]
async fn cmd_assign_free_unit(input: AssignFreeUnitInput) -> Result<FreeUnit> {
    impl_assign_free_unit(input)
}

/// Resets a free unit to unassigned state. For correcting mistakes.
/// Idempotent: unassigning an already-unassigned unit returns it unchanged.
pub fn impl_unassign_free_unit(free_unit_id: i64) -> Result<FreeUnit> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // verify exists
    let _: i64 = tx
        .query_row(
            "SELECT free_unit_id FROM import_free_unit WHERE free_unit_id = ?",
            rusqlite::params![free_unit_id],
            |r| r.get(0),
        )
        .map_err(|e| match e {
            rusqlite::Error::QueryReturnedNoRows => {
                ErpError::NotFound(format!("free_unit_id {}", free_unit_id))
            }
            other => other.into(),
        })?;

    tx.execute(
        "UPDATE import_free_unit SET \
           destination = NULL, destination_ref = NULL, \
           assigned_at = NULL, assigned_by = NULL \
         WHERE free_unit_id = ?",
        rusqlite::params![free_unit_id],
    )?;

    tx.commit()?;

    let updated = impl_list_free_units(None)?
        .into_iter()
        .find(|fu| fu.free_unit_id == free_unit_id)
        .ok_or_else(|| ErpError::Other("free unit vanished post-update".to_string()))?;
    Ok(updated)
}

#[tauri::command]
async fn cmd_unassign_free_unit(free_unit_id: i64) -> Result<FreeUnit> {
    impl_unassign_free_unit(free_unit_id)
}

// ─── R2: Wishlist + Promote-to-batch ────
//
// Convention (per lib.rs:2730-2742): impl_X (pub testable) + cmd_X (#[tauri::command] shim).
// All 5 R2 commands (list/create/update/cancel/promote) follow this split.
//
// D7=B: catalog_family_exists() reads catalog.json server-side via catalog_path() (L53).
// Tests override catalog path via env var ELCLUB_CATALOG_PATH for fixture isolation.

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WishlistItem {
    pub wishlist_item_id:      i64,
    pub family_id:             String,
    pub jersey_id:             Option<String>,
    pub size:                  Option<String>,
    pub player_name:           Option<String>,
    pub player_number:         Option<i64>,
    pub patch:                 Option<String>,
    pub version:               Option<String>,
    pub customer_id:           Option<String>,
    pub expected_usd:          Option<f64>,
    pub status:                String,
    pub promoted_to_import_id: Option<String>,
    pub created_at:            String,
    pub notes:                 Option<String>,
}

/// D7=B validation: returns true if `family_id` exists in catalog.json.
/// Overridable via ELCLUB_CATALOG_PATH env var (tests use fixtures).
fn catalog_family_exists(family_id: &str) -> Result<bool> {
    let path = std::env::var("ELCLUB_CATALOG_PATH")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| catalog_path());

    if !path.exists() {
        return Err(ErpError::Other(format!(
            "catalog.json not found at {:?} · cannot validate family_id (D7=B)",
            path
        )));
    }

    let raw = std::fs::read_to_string(&path).map_err(|e| {
        ErpError::Other(format!("failed reading catalog.json: {}", e))
    })?;
    let catalog: serde_json::Value = serde_json::from_str(&raw).map_err(|e| {
        ErpError::Other(format!("invalid catalog.json: {}", e))
    })?;

    let families = catalog.as_array().ok_or_else(|| {
        ErpError::Other("catalog.json root not an array".into())
    })?;

    Ok(families.iter().any(|f| {
        f.get("family_id")
            .and_then(|v| v.as_str())
            .map(|s| s == family_id)
            .unwrap_or(false)
    }))
}

/// Re-reads canonical WishlistItem row by id. Used post-tx by impl_X commands.
fn read_wishlist_item_by_id(conn: &rusqlite::Connection, wishlist_item_id: i64) -> Result<WishlistItem> {
    conn.query_row(
        "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                created_at, notes
         FROM import_wishlist WHERE wishlist_item_id = ?1",
        rusqlite::params![wishlist_item_id],
        |row| Ok(WishlistItem {
            wishlist_item_id:      row.get(0)?,
            family_id:             row.get(1)?,
            jersey_id:             row.get(2)?,
            size:                  row.get(3)?,
            player_name:           row.get(4)?,
            player_number:         row.get(5)?,
            patch:                 row.get(6)?,
            version:               row.get(7)?,
            customer_id:           row.get(8)?,
            expected_usd:          row.get(9)?,
            status:                row.get(10)?,
            promoted_to_import_id: row.get(11)?,
            created_at:            row.get(12)?,
            notes:                 row.get(13)?,
        }),
    ).map_err(ErpError::from)
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ListWishlistInput {
    pub status: Option<String>,  // 'active' | 'promoted' | 'cancelled' | None (all)
}

/// List wishlist items, optionally filtered by status. Default: all items, ordered by created_at DESC.
pub async fn impl_list_wishlist(input: ListWishlistInput) -> Result<Vec<WishlistItem>> {
    let conn = open_db()?;
    let (sql, params): (&str, Vec<Box<dyn rusqlite::ToSql>>) = match input.status.as_deref() {
        Some(s) if !s.is_empty() => (
            "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                    patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                    created_at, notes
             FROM import_wishlist WHERE status = ?1
             ORDER BY created_at DESC, wishlist_item_id DESC",
            vec![Box::new(s.to_string())],
        ),
        _ => (
            "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                    patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                    created_at, notes
             FROM import_wishlist
             ORDER BY created_at DESC, wishlist_item_id DESC",
            vec![],
        ),
    };

    let mut stmt = conn.prepare(sql)?;
    let param_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|b| b.as_ref()).collect();
    let rows = stmt.query_map(&param_refs[..], |row| {
        Ok(WishlistItem {
            wishlist_item_id:      row.get(0)?,
            family_id:             row.get(1)?,
            jersey_id:             row.get(2)?,
            size:                  row.get(3)?,
            player_name:           row.get(4)?,
            player_number:         row.get(5)?,
            patch:                 row.get(6)?,
            version:               row.get(7)?,
            customer_id:           row.get(8)?,
            expected_usd:          row.get(9)?,
            status:                row.get(10)?,
            promoted_to_import_id: row.get(11)?,
            created_at:            row.get(12)?,
            notes:                 row.get(13)?,
        })
    })?;

    let mut items = Vec::new();
    for r in rows {
        items.push(r?);
    }
    Ok(items)
}

#[tauri::command]
async fn cmd_list_wishlist(input: ListWishlistInput) -> Result<Vec<WishlistItem>> {
    impl_list_wishlist(input).await
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateWishlistItemInput {
    pub family_id:     String,
    pub jersey_id:     Option<String>,
    pub size:          Option<String>,
    pub player_name:   Option<String>,
    pub player_number: Option<i64>,
    pub patch:         Option<String>,
    pub version:       Option<String>,
    pub customer_id:   Option<String>,
    pub expected_usd:  Option<f64>,
    pub notes:         Option<String>,
}

/// D7=B: family_id must exist in catalog.json. Validates server-side before INSERT.
pub async fn impl_create_wishlist_item(input: CreateWishlistItemInput) -> Result<WishlistItem> {
    if input.family_id.trim().is_empty() {
        return Err(ErpError::Other("family_id is required".into()));
    }

    // D7=B validation
    if !catalog_family_exists(&input.family_id)? {
        return Err(ErpError::Other(format!(
            "family_id '{}' not in catalog (D7=B) · audit/scrape it first via Vault",
            input.family_id
        )));
    }

    // Validate version if provided
    if let Some(v) = &input.version {
        if !["fan", "fan-w", "player"].contains(&v.as_str()) {
            return Err(ErpError::Other(format!(
                "version must be one of: fan, fan-w, player (got '{}')",
                v
            )));
        }
    }

    // Validate expected_usd if provided
    if let Some(usd) = input.expected_usd {
        if usd < 0.0 {
            return Err(ErpError::Other("expected_usd cannot be negative".into()));
        }
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    tx.execute(
        "INSERT INTO import_wishlist
         (family_id, jersey_id, size, player_name, player_number, patch, version,
          customer_id, expected_usd, status, notes)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'active', ?10)",
        rusqlite::params![
            input.family_id,
            input.jersey_id,
            input.size,
            input.player_name,
            input.player_number,
            input.patch,
            input.version,
            input.customer_id,
            input.expected_usd,
            input.notes,
        ],
    )?;

    let new_id = tx.last_insert_rowid();
    tx.commit()?;

    read_wishlist_item_by_id(&conn, new_id)
}

#[tauri::command]
async fn cmd_create_wishlist_item(input: CreateWishlistItemInput) -> Result<WishlistItem> {
    impl_create_wishlist_item(input).await
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateWishlistItemInput {
    pub wishlist_item_id: i64,
    pub size:             Option<String>,
    pub player_name:      Option<String>,
    pub player_number:    Option<i64>,
    pub patch:            Option<String>,
    pub version:          Option<String>,
    pub customer_id:      Option<String>,
    pub expected_usd:     Option<f64>,
    pub notes:            Option<String>,
    // Note: family_id NOT editable post-create (would require re-validation + status implications)
}

/// Edit a wishlist item. Status guard: only 'active' items can be edited.
pub async fn impl_update_wishlist_item(input: UpdateWishlistItemInput) -> Result<WishlistItem> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM import_wishlist WHERE wishlist_item_id = ?1",
        rusqlite::params![input.wishlist_item_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            ErpError::NotFound(format!("Wishlist item {}", input.wishlist_item_id))
        }
        other => other.into(),
    })?;

    if status != "active" {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot update wishlist item with status '{}' (only 'active' is editable)",
            status
        )));
    }

    if let Some(v) = &input.version {
        if !["fan", "fan-w", "player"].contains(&v.as_str()) {
            tx.rollback()?;
            return Err(ErpError::Other(format!(
                "version must be one of: fan, fan-w, player (got '{}')",
                v
            )));
        }
    }
    if let Some(usd) = input.expected_usd {
        if usd < 0.0 {
            tx.rollback()?;
            return Err(ErpError::Other("expected_usd cannot be negative".into()));
        }
    }

    tx.execute(
        "UPDATE import_wishlist
         SET size          = COALESCE(?1, size),
             player_name   = COALESCE(?2, player_name),
             player_number = COALESCE(?3, player_number),
             patch         = COALESCE(?4, patch),
             version       = COALESCE(?5, version),
             customer_id   = COALESCE(?6, customer_id),
             expected_usd  = COALESCE(?7, expected_usd),
             notes         = COALESCE(?8, notes)
         WHERE wishlist_item_id = ?9",
        rusqlite::params![
            input.size,
            input.player_name,
            input.player_number,
            input.patch,
            input.version,
            input.customer_id,
            input.expected_usd,
            input.notes,
            input.wishlist_item_id,
        ],
    )?;

    tx.commit()?;

    read_wishlist_item_by_id(&conn, input.wishlist_item_id)
}

#[tauri::command]
async fn cmd_update_wishlist_item(input: UpdateWishlistItemInput) -> Result<WishlistItem> {
    impl_update_wishlist_item(input).await
}

/// Soft-delete a wishlist item by setting status='cancelled'.
/// Idempotent: cancelling already-cancelled is OK.
/// Cannot cancel a 'promoted' item (would orphan the linked import row).
pub async fn impl_cancel_wishlist_item(wishlist_item_id: i64) -> Result<WishlistItem> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM import_wishlist WHERE wishlist_item_id = ?1",
        rusqlite::params![wishlist_item_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => {
            ErpError::NotFound(format!("Wishlist item {}", wishlist_item_id))
        }
        other => other.into(),
    })?;

    if status == "promoted" {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot cancel wishlist item already promoted to a batch (use the batch's cancel flow)"
        )));
    }

    if status != "cancelled" {
        tx.execute(
            "UPDATE import_wishlist SET status = 'cancelled' WHERE wishlist_item_id = ?1",
            rusqlite::params![wishlist_item_id],
        )?;
    }

    tx.commit()?;

    read_wishlist_item_by_id(&conn, wishlist_item_id)
}

#[tauri::command]
async fn cmd_cancel_wishlist_item(wishlist_item_id: i64) -> Result<WishlistItem> {
    impl_cancel_wishlist_item(wishlist_item_id).await
}

// ─── R2: Promote Wishlist → Batch (transactional · CORE COMMAND) ────

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PromoteWishlistInput {
    pub wishlist_item_ids: Vec<i64>,
    pub import_id:         String,
    pub status:            String,            // 'paid' (default UI · paid_at required) or 'draft' (paid_at optional)
    pub paid_at:           Option<String>,    // required iff status='paid'
    pub supplier:          Option<String>,
    pub bruto_usd:         f64,               // sum of expected_usd OR manual override (must be > 0)
    pub fx:                f64,
    pub notes:             Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PromoteWishlistResult {
    pub import:             Import,
    pub import_items_count: i64,
}

/// Promote a set of wishlist items to a new import.
///
/// DESTINATION (Diego decision 2026-04-28 ~19:00 · supersedes earlier split):
/// - ALL items go into single table `import_items` (created by R6 apply_imp_schema.py)
/// - customer_id nullable column distinguishes: NULL = stock-future · NOT NULL = assigned
/// - Status defaults to 'pending' on insert (will become 'arrived' on close_import in R4)
/// - sale_item_id and jersey_id_published populated later by Comercial / Inventario flows (v0.5+)
///
/// REASON for single-table redesign: peer review found the earlier split (sale_items vs jerseys)
/// inejecutable due to schema constraints — sale_items.sale_id NOT NULL · sale_items.customer_id
/// doesn't exist · jerseys CHECK constraints (variant in {home,away,third,special}) incompatible.
///
/// STATUS handling (Diego decision 2026-04-28 ~18:30):
/// - Default UI: status='paid' + paid_at=today (Diego pays supplier the moment he promotes most of the time)
/// - Toggle OFF: status='draft' + paid_at=NULL (rare · queue without committing to payment yet)
/// - After 'paid', Diego can manually call `cmd_mark_in_transit` (paid → in_transit) before arrival.
///
/// EVENTS (peer review 2026-04-28 ~19:00): inbox_events table EXISTS in production (Comercial-shipped).
/// We INSERT a synchronous "import_promoted" row inside the same tx · graceful degradation if the
/// table is missing (logged, not raised). Time-based events (wishlist > 20 · assigned > 30d) need
/// cron infrastructure → deferred to post-R6.
///
/// Atomic: either all items get linked + import created + wishlist rows updated + event logged, or nothing.
///
/// Validations:
/// - At least 1 wishlist_item_id provided
/// - import_id format valid (IMP-YYYY-MM-DD)
/// - import_id does not already exist
/// - status in {'paid', 'draft'}
/// - if status='paid' → paid_at REQUIRED (YYYY-MM-DD)
/// - if status='draft' → paid_at can be None
/// - All wishlist items exist AND status='active'
/// - bruto_usd > 0 · fx > 0
///
/// On success:
/// - Inserts imports row (status=input.status, bruto_usd=input.bruto_usd, n_units=count)
/// - Inserts N rows into import_items (one per promoted wishlist item, status='pending')
/// - Updates wishlist rows (status='promoted', promoted_to_import_id=new_id)
/// - Inserts 1 row into inbox_events (type='import_promoted', metadata=summary) · best-effort
pub async fn impl_promote_wishlist_to_batch(input: PromoteWishlistInput) -> Result<PromoteWishlistResult> {
    // Validations BEFORE opening tx
    if input.wishlist_item_ids.is_empty() {
        return Err(ErpError::Other("must select at least 1 wishlist item to promote".into()));
    }
    if !is_valid_import_id(&input.import_id) {
        return Err(ErpError::Other(format!(
            "import_id format inválido: '{}' · esperado IMP-YYYY-MM-DD",
            input.import_id
        )));
    }
    if !["paid", "draft"].contains(&input.status.as_str()) {
        return Err(ErpError::Other(format!(
            "status must be 'paid' or 'draft' · got '{}'",
            input.status
        )));
    }
    if input.status == "paid" {
        match &input.paid_at {
            None => return Err(ErpError::Other(
                "paid_at required when status='paid' (Diego confirmed default toggle ON)".into()
            )),
            Some(d) if chrono::NaiveDate::parse_from_str(d, "%Y-%m-%d").is_err() => {
                return Err(ErpError::Other(format!(
                    "paid_at format inválido: '{}' · esperado YYYY-MM-DD",
                    d
                )));
            }
            _ => {}
        }
    }
    if let Some(d) = &input.paid_at {
        // Even when status='draft', if user provided paid_at it must parse
        if chrono::NaiveDate::parse_from_str(d, "%Y-%m-%d").is_err() {
            return Err(ErpError::Other(format!(
                "paid_at format inválido: '{}' · esperado YYYY-MM-DD",
                d
            )));
        }
    }
    if input.fx <= 0.0 {
        return Err(ErpError::Other(format!("fx must be > 0 · got {}", input.fx)));
    }
    if input.bruto_usd <= 0.0 {
        return Err(ErpError::Other(format!("bruto_usd must be > 0 · got {}", input.bruto_usd)));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // Duplicate import_id guard
    let import_exists: bool = tx.query_row(
        "SELECT EXISTS(SELECT 1 FROM imports WHERE import_id = ?1)",
        rusqlite::params![&input.import_id],
        |row| row.get::<_, i64>(0).map(|n| n != 0),
    )?;
    if import_exists {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "Import {} already exists · choose a different import_id",
            input.import_id
        )));
    }

    // Fetch all wishlist items in one query (Vec<WishlistItem>)
    // Build placeholders for IN clause
    let placeholders: String = (0..input.wishlist_item_ids.len())
        .map(|i| format!("?{}", i + 1))
        .collect::<Vec<_>>()
        .join(",");
    let sql = format!(
        "SELECT wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
                patch, version, customer_id, expected_usd, status, promoted_to_import_id,
                created_at, notes
         FROM import_wishlist
         WHERE wishlist_item_id IN ({})",
        placeholders
    );
    let mut stmt = tx.prepare(&sql)?;
    let params_vec: Vec<Box<dyn rusqlite::ToSql>> = input
        .wishlist_item_ids
        .iter()
        .map(|id| Box::new(*id) as Box<dyn rusqlite::ToSql>)
        .collect();
    let param_refs: Vec<&dyn rusqlite::ToSql> = params_vec.iter().map(|b| b.as_ref()).collect();
    let rows = stmt.query_map(&param_refs[..], |row| {
        Ok(WishlistItem {
            wishlist_item_id:      row.get(0)?,
            family_id:             row.get(1)?,
            jersey_id:             row.get(2)?,
            size:                  row.get(3)?,
            player_name:           row.get(4)?,
            player_number:         row.get(5)?,
            patch:                 row.get(6)?,
            version:               row.get(7)?,
            customer_id:           row.get(8)?,
            expected_usd:          row.get(9)?,
            status:                row.get(10)?,
            promoted_to_import_id: row.get(11)?,
            created_at:            row.get(12)?,
            notes:                 row.get(13)?,
        })
    })?;

    let mut items: Vec<WishlistItem> = Vec::new();
    for r in rows {
        items.push(r?);
    }
    drop(stmt);

    // Verify ALL requested IDs were found
    if items.len() != input.wishlist_item_ids.len() {
        let found_ids: std::collections::HashSet<i64> =
            items.iter().map(|i| i.wishlist_item_id).collect();
        let missing: Vec<i64> = input
            .wishlist_item_ids
            .iter()
            .filter(|id| !found_ids.contains(id))
            .copied()
            .collect();
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "wishlist items not found: {:?}",
            missing
        )));
    }

    // Verify ALL items have status='active'
    let non_active: Vec<(i64, String)> = items
        .iter()
        .filter(|i| i.status != "active")
        .map(|i| (i.wishlist_item_id, i.status.clone()))
        .collect();
    if !non_active.is_empty() {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot promote items not active: {:?} (only 'active' items can be promoted)",
            non_active
        )));
    }

    // Compute aggregate stats
    let n_units: i64 = items.len() as i64;
    let supplier = input
        .supplier
        .as_ref()
        .filter(|s| !s.trim().is_empty())
        .cloned()
        .unwrap_or_else(|| "Bond Soccer Jersey".to_string());
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

    // INSERT imports row · status + bruto_usd come from input (Diego decision: default 'paid', toggle for 'draft')
    tx.execute(
        "INSERT INTO imports
         (import_id, paid_at, supplier, bruto_usd, fx, n_units, status, notes, created_at, carrier)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'DHL')",
        rusqlite::params![
            input.import_id,
            input.paid_at,             // Option<String> — NULL if status='draft' and toggle OFF
            supplier,
            input.bruto_usd,
            input.fx,
            n_units,
            input.status,              // 'paid' or 'draft'
            input.notes,
            now,
        ],
    )?;

    // INSERT all items into single destination table import_items (Diego decision 2026-04-28 ~19:00):
    // - Single table for ALL promoted items (assigned + stock-future)
    // - customer_id nullable column distinguishes them (NULL = stock-future · NOT NULL = assigned)
    // - status='pending' on insert · close_import (R4) flips to 'arrived' + sets unit_cost_usd/gtq
    // - sale_item_id and jersey_id_published get populated by Comercial / Inventario flows later
    let mut import_items_count: i64 = 0;
    let mut n_assigned: i64 = 0;
    let mut n_stock: i64 = 0;
    for item in &items {
        tx.execute(
            "INSERT INTO import_items
             (import_id, wishlist_item_id, family_id, jersey_id, size, player_name, player_number,
              patch, version, customer_id, expected_usd, status, notes)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 'pending', ?12)",
            rusqlite::params![
                input.import_id,
                item.wishlist_item_id,
                item.family_id,
                item.jersey_id,
                item.size,
                item.player_name,
                item.player_number,
                item.patch,
                item.version,
                item.customer_id,        // nullable: NULL = stock-future · NOT NULL = assigned
                item.expected_usd,
                item.notes,
            ],
        )?;
        import_items_count += 1;
        if item.customer_id.is_some() { n_assigned += 1; } else { n_stock += 1; }

        // UPDATE wishlist row · status='promoted' · promoted_to_import_id=new_id
        tx.execute(
            "UPDATE import_wishlist
             SET status = 'promoted',
                 promoted_to_import_id = ?1
             WHERE wishlist_item_id = ?2",
            rusqlite::params![input.import_id, item.wishlist_item_id],
        )?;
    }

    // BONUS: log inbox_events row (type='import_promoted'). Best-effort: if the table doesn't exist
    // (older deployment), we silently skip rather than failing the entire promote.
    // Real production schema: id/type/severity/title/description/module/metadata/action_label/action_target/created_at(unixepoch)/...
    let metadata_json = serde_json::json!({
        "import_id":   &input.import_id,
        "n_items":     import_items_count,
        "n_assigned":  n_assigned,
        "n_stock":     n_stock,
        "supplier":    &supplier,
        "status":      &input.status,
    }).to_string();
    let title = format!("{} promovido", &input.import_id);
    let description = format!(
        "{} items movidos a batch ({} assigned · {} stock-future)",
        import_items_count, n_assigned, n_stock
    );
    let action_target = format!("importaciones:{}", &input.import_id);
    let _ = tx.execute(
        "INSERT INTO inbox_events
         (type, severity, title, description, module, metadata, action_label, action_target)
         VALUES ('import_promoted', 'info', ?1, ?2, 'importaciones', ?3, 'Ver batch', ?4)",
        rusqlite::params![title, description, metadata_json, action_target],
    ); // intentionally swallow error — graceful degradation if inbox_events missing

    tx.commit()?;

    // Re-read canonical Import using same connection
    let import = read_import_by_id(&conn, &input.import_id)?;

    Ok(PromoteWishlistResult {
        import,
        import_items_count,
    })
}

#[tauri::command]
async fn cmd_promote_wishlist_to_batch(input: PromoteWishlistInput) -> Result<PromoteWishlistResult> {
    impl_promote_wishlist_to_batch(input).await
}

/// Mark an import as in_transit (state guard: only allowed from 'paid').
/// Optional `tracking_code` overwrites existing only if Some (COALESCE semantics).
///
/// State machine (full): draft → paid → in_transit → arrived → closed
/// (cancelled available from any active state via cmd_cancel_import).
///
/// Diego decision (2026-04-28): "después del paid puedo manualmente marcar in_transit
/// cuando el chino confirme el envío, antes que registre arrival."
pub async fn impl_mark_in_transit(
    import_id: String,
    tracking_code: Option<String>,
) -> Result<Import> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // 1. Fetch current status (assert exists)
    let current_status: String = tx.query_row(
        "SELECT status FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    // 2. State guard: only 'paid' → 'in_transit' allowed
    if current_status != "paid" {
        tx.rollback()?;
        if current_status == "in_transit" {
            return Err(ErpError::Other(format!(
                "Import {} is already in_transit · this is a one-way state transition",
                import_id
            )));
        }
        return Err(ErpError::Other(format!(
            "Import {} has status '{}' · must be 'paid' to mark in_transit (state machine: draft → paid → in_transit → arrived → closed)",
            import_id, current_status
        )));
    }

    // 3. UPDATE — COALESCE preserves existing tracking_code if input is None
    tx.execute(
        "UPDATE imports
         SET status = 'in_transit',
             tracking_code = COALESCE(?1, tracking_code)
         WHERE import_id = ?2",
        rusqlite::params![tracking_code, import_id],
    )?;

    tx.commit()?;

    // 4. Re-read canonical Import
    read_import_by_id(&conn, &import_id)
}

#[tauri::command]
async fn cmd_mark_in_transit(
    import_id: String,
    tracking_code: Option<String>,
) -> Result<Import> {
    impl_mark_in_transit(import_id, tracking_code).await
}

// ─── R1.5 Completion: Create / Register Arrival / Update / Cancel ────
//
// Convention for IMP-R1.5 commands that need integration testing:
//   pub async fn impl_X(...) — business logic, callable from tests/*.rs binaries
//   #[tauri::command] async fn cmd_X(...) — thin shim, registered in invoke_handler!
//
// Why split: existing convention is `#[tauri::command] async fn` (private to crate).
// Integration tests in tests/*.rs are separate binaries · need pub access.
// The split keeps the registered command name (cmd_X) aligned with adapter contract.
//
// Tasks 3 (cmd_register_arrival), 4 (cmd_update_import), 5 (cmd_cancel_import)
// will reuse this pattern. Tasks 6 (cmd_export_imports_csv) does NOT need impl_X
// split because it has no integration test (smoke-only via SQL script).

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CreateImportInput {
    pub import_id: String,
    pub paid_at: String,
    pub supplier: String,
    pub bruto_usd: f64,
    pub fx: f64,
    pub n_units: i64,
    pub notes: Option<String>,
    pub tracking_code: Option<String>,
    pub carrier: Option<String>,
}

/// Business logic for creating an import — pub so integration tests can call directly.
pub async fn impl_create_import(input: CreateImportInput) -> Result<Import> {
    // Validation
    if !is_valid_import_id(&input.import_id) {
        return Err(ErpError::Other(format!(
            "import_id format inválido: '{}' · esperado IMP-YYYY-MM-DD",
            input.import_id
        )));
    }
    if input.bruto_usd <= 0.0 {
        return Err(ErpError::Other(format!(
            "bruto_usd debe ser > 0 · recibido {}",
            input.bruto_usd
        )));
    }
    if input.fx <= 0.0 {
        return Err(ErpError::Other(format!(
            "fx debe ser > 0 · recibido {}",
            input.fx
        )));
    }
    if input.n_units <= 0 {
        return Err(ErpError::Other(format!(
            "n_units debe ser > 0 · recibido {}",
            input.n_units
        )));
    }
    if chrono::NaiveDate::parse_from_str(&input.paid_at, "%Y-%m-%d").is_err() {
        return Err(ErpError::Other(format!(
            "paid_at format inválido: '{}' · esperado YYYY-MM-DD",
            input.paid_at
        )));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // Duplicate guard
    let exists: bool = tx.query_row(
        "SELECT EXISTS(SELECT 1 FROM imports WHERE import_id = ?1)",
        rusqlite::params![&input.import_id],
        |row| row.get::<_, i64>(0).map(|n| n != 0),
    )?;
    if exists {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "Import {} already exists",
            input.import_id
        )));
    }

    let supplier = if input.supplier.trim().is_empty() {
        "Bond Soccer Jersey".to_string()
    } else {
        input.supplier.clone()
    };
    let carrier = input.carrier.clone().unwrap_or_else(|| "DHL".to_string());
    let now = chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

    tx.execute(
        "INSERT INTO imports
         (import_id, paid_at, supplier, bruto_usd, fx, n_units, notes,
          tracking_code, carrier, status, created_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'paid', ?10)",
        rusqlite::params![
            input.import_id,
            input.paid_at,
            supplier,
            input.bruto_usd,
            input.fx,
            input.n_units,
            input.notes,
            input.tracking_code,
            carrier,
            now,
        ],
    )?;

    tx.commit()?;

    // Re-read to return canonical Import (using same conn — WAL footgun avoided)
    read_import_by_id(&conn, &input.import_id)
}

/// Tauri command — delegates to impl_create_import.
#[tauri::command]
async fn cmd_create_import(input: CreateImportInput) -> Result<Import> {
    impl_create_import(input).await
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterArrivalInput {
    pub import_id: String,
    pub arrived_at: String,
    pub shipping_gtq: f64,
    pub tracking_code: Option<String>,
}

/// Business logic for registering arrival on an existing import.
/// pub so integration tests can call directly.
pub async fn impl_register_arrival(input: RegisterArrivalInput) -> Result<Import> {
    if input.shipping_gtq < 0.0 {
        return Err(ErpError::Other("shipping_gtq cannot be negative".into()));
    }
    // Validate arrived_at format
    if chrono::NaiveDate::parse_from_str(&input.arrived_at, "%Y-%m-%d").is_err() {
        return Err(ErpError::Other(format!(
            "arrived_at format inválido: '{}' · esperado YYYY-MM-DD",
            input.arrived_at
        )));
    }

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let (status, paid_at, existing_lead_time): (String, Option<String>, Option<i64>) = tx.query_row(
        "SELECT status, paid_at, lead_time_days FROM imports WHERE import_id = ?1",
        rusqlite::params![&input.import_id],
        |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", input.import_id)),
        other => other.into(),
    })?;

    if status == "closed" || status == "cancelled" {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot register arrival on import with status '{}'",
            status
        )));
    }

    // Auto-calc lead_time_days from paid_at to arrived_at.
    // Idempotency: preserve existing lead_time_days when re-registering on 'arrived' status
    // (otherwise editing arrived_at later silently mutates the derived metric).
    let lead_time_days = if status == "arrived" {
        existing_lead_time
    } else {
        paid_at.as_ref().and_then(|p| {
            let pd = chrono::NaiveDate::parse_from_str(p, "%Y-%m-%d").ok()?;
            let ad = chrono::NaiveDate::parse_from_str(&input.arrived_at, "%Y-%m-%d").ok()?;
            Some((ad - pd).num_days() as i64)
        })
    };

    // Guard: reject negative lead_time_days (arrived_at before paid_at means data error)
    if let Some(days) = lead_time_days {
        if days < 0 {
            tx.rollback()?;
            return Err(ErpError::Other(format!(
                "arrived_at ({}) is before paid_at ({}) · refusing negative lead_time_days",
                input.arrived_at, paid_at.as_deref().unwrap_or("")
            )));
        }
    }

    tx.execute(
        "UPDATE imports
         SET arrived_at = ?1,
             shipping_gtq = ?2,
             tracking_code = COALESCE(?3, tracking_code),
             lead_time_days = ?4,
             status = 'arrived'
         WHERE import_id = ?5",
        rusqlite::params![
            input.arrived_at,
            input.shipping_gtq,
            input.tracking_code,
            lead_time_days,
            input.import_id,
        ],
    )?;

    tx.commit()?;

    // Re-read canonical Import using same connection (avoid WAL footgun)
    read_import_by_id(&conn, &input.import_id)
}

/// Tauri command — delegates to impl_register_arrival.
#[tauri::command]
async fn cmd_register_arrival(input: RegisterArrivalInput) -> Result<Import> {
    impl_register_arrival(input).await
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateImportInput {
    pub import_id: String,
    pub notes: Option<String>,
    pub tracking_code: Option<String>,
    pub carrier: Option<String>,
}

/// Business logic for editing notes/tracking_code/carrier on an existing import.
/// Status guard: cannot update if status='closed' or 'cancelled'.
/// pub so integration tests can call directly (Task 4 has smoke-only · this future-proofs).
pub async fn impl_update_import(input: UpdateImportInput) -> Result<Import> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM imports WHERE import_id = ?1",
        rusqlite::params![&input.import_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", input.import_id)),
        other => other.into(),
    })?;

    if status == "closed" || status == "cancelled" {
        tx.rollback()?;
        return Err(ErpError::Other(format!(
            "cannot update import with status '{}'",
            status
        )));
    }

    tx.execute(
        "UPDATE imports
         SET notes = COALESCE(?1, notes),
             tracking_code = COALESCE(?2, tracking_code),
             carrier = COALESCE(?3, carrier)
         WHERE import_id = ?4",
        rusqlite::params![
            input.notes,
            input.tracking_code,
            input.carrier,
            input.import_id,
        ],
    )?;

    tx.commit()?;

    // Re-read using same conn (avoid WAL footgun)
    read_import_by_id(&conn, &input.import_id)
}

/// Tauri command — delegates to impl_update_import.
#[tauri::command]
async fn cmd_update_import(input: UpdateImportInput) -> Result<Import> {
    impl_update_import(input).await
}

/// Business logic for cancelling an import.
/// Idempotent: re-cancelling already-cancelled is OK.
/// Status guard: cannot cancel 'closed' (terminal state · use admin re-open).
/// pub so integration tests can call directly.
pub async fn impl_cancel_import(import_id: String) -> Result<Import> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let status: String = tx.query_row(
        "SELECT status FROM imports WHERE import_id = ?1",
        rusqlite::params![&import_id],
        |row| row.get(0),
    ).map_err(|e| match e {
        rusqlite::Error::QueryReturnedNoRows => ErpError::NotFound(format!("Import {}", import_id)),
        other => other.into(),
    })?;

    // Cannot cancel closed (terminal opposite state)
    // Idempotent: cancelling 'cancelled' is no-op
    if status == "closed" {
        tx.rollback()?;
        return Err(ErpError::Other(
            "cannot cancel import with status 'closed' (use admin re-open if needed)".into()
        ));
    }

    if status != "cancelled" {
        tx.execute(
            "UPDATE imports SET status = 'cancelled' WHERE import_id = ?1",
            rusqlite::params![&import_id],
        )?;
    }

    tx.commit()?;

    // Re-read using same conn (avoid WAL footgun)
    read_import_by_id(&conn, &import_id)
}

/// Tauri command — delegates to impl_cancel_import.
#[tauri::command]
async fn cmd_cancel_import(import_id: String) -> Result<Import> {
    impl_cancel_import(import_id).await
}

#[tauri::command]
async fn cmd_export_imports_csv() -> Result<String> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT import_id, paid_at, arrived_at, supplier, bruto_usd, shipping_gtq,
                fx, total_landed_gtq, n_units, unit_cost, status,
                tracking_code, carrier, lead_time_days, notes, created_at
         FROM imports ORDER BY paid_at IS NULL, paid_at DESC, created_at DESC"
    )?;

    // UTF-8 BOM for Excel auto-detection of charset (Spanish accents in notes/supplier survive)
    // CRLF line endings per RFC 4180 §2.1
    let mut csv = String::from(
        "\u{FEFF}import_id,paid_at,arrived_at,supplier,bruto_usd,shipping_gtq,fx,total_landed_gtq,n_units,unit_cost,status,tracking_code,carrier,lead_time_days,notes,created_at\r\n"
    );

    let rows = stmt.query_map([], |row| {
        Ok(format!(
            "{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}",
            csv_escape(&row.get::<_, String>(0)?),
            csv_escape(&row.get::<_, Option<String>>(1)?.unwrap_or_default()),
            csv_escape(&row.get::<_, Option<String>>(2)?.unwrap_or_default()),
            csv_escape(&row.get::<_, String>(3)?),
            row.get::<_, Option<f64>>(4)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(5)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(6)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(7)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<i64>>(8)?.map(|v| v.to_string()).unwrap_or_default(),
            row.get::<_, Option<f64>>(9)?.map(|v| v.to_string()).unwrap_or_default(),
            csv_escape(&row.get::<_, String>(10)?),
            csv_escape(&row.get::<_, Option<String>>(11)?.unwrap_or_default()),
            csv_escape(&row.get::<_, Option<String>>(12)?.unwrap_or_else(|| "DHL".into())),
            row.get::<_, Option<i64>>(13)?.map(|v| v.to_string()).unwrap_or_default(),
            csv_escape(&row.get::<_, Option<String>>(14)?.unwrap_or_default()),
            csv_escape(&row.get::<_, String>(15)?),
        ))
    })?;

    for row in rows {
        csv.push_str(&row?);
        csv.push_str("\r\n");
    }

    Ok(csv)
}

/// Escape a CSV cell · quotes the field if it contains commas, quotes, or newlines.
fn csv_escape(s: &str) -> String {
    if s.contains(',') || s.contains('"') || s.contains('\n') || s.contains('\r') {
        format!("\"{}\"", s.replace('"', "\"\""))
    } else {
        s.to_string()
    }
}

// ─── Finanzas (FIN-R1) — structs ─────────────────────────────────────

#[derive(Debug, Serialize, Deserialize)]
pub struct Expense {
    pub expense_id: i64,
    pub amount_gtq: f64,
    pub amount_native: Option<f64>,
    pub currency: String,
    pub fx_used: f64,
    pub category: String,
    pub payment_method: String,
    pub paid_at: String,
    pub notes: Option<String>,
    pub source: String,
    pub source_ref: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Deserialize)]
pub struct ExpenseInput {
    pub amount_native: f64,
    pub currency: String,
    pub fx_used: Option<f64>,
    pub category: String,
    pub payment_method: String,
    pub paid_at: String,
    pub notes: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct ProfitSnapshot {
    pub period_start: String,
    pub period_end: String,
    pub period_label: String,
    pub revenue_gtq: f64,
    pub cogs_gtq: f64,
    pub marketing_gtq: f64,
    pub opex_gtq: f64,
    pub profit_operativo: f64,
    pub prev_period_profit: Option<f64>,
    pub trend_pct: Option<f64>,
}

#[derive(Debug, Serialize)]
pub struct HomeSnapshot {
    pub profit: ProfitSnapshot,
    pub cash_business_gtq: Option<f64>,
    pub cash_synced_at: Option<String>,
    pub cash_stale_days: Option<i64>,
    pub capital_amarrado_gtq: f64,
    pub shareholder_loan_balance: f64,
    pub shareholder_loan_trend_30d: f64,
}

#[derive(Debug, Serialize)]
pub struct RecentExpenseRow {
    pub expense_id: i64,
    pub paid_at: String,
    pub category: String,
    pub payment_method: String,
    pub amount_gtq: f64,
    pub notes: Option<String>,
}

// ─── Finanzas commands (FIN-R1) ───────────────────────────────────────

#[tauri::command]
async fn cmd_compute_profit_snapshot(
    _app: tauri::AppHandle,
    period_start: String,
    period_end: String,
    period_label: String,
    prev_start: Option<String>,
    prev_end: Option<String>,
) -> Result<ProfitSnapshot> {
    let conn = open_db()?;

    // Revenue: cash basis · sales fulfilled (shipped or delivered) in range
    let revenue: f64 = conn.query_row(
        "SELECT COALESCE(CAST(SUM(total) AS REAL), 0) FROM sales
         WHERE fulfillment_status IN ('shipped','delivered')
           AND date(COALESCE(shipped_at, occurred_at)) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // COGS: sale_items.unit_cost of fulfilled sales in range
    let cogs: f64 = conn.query_row(
        "SELECT COALESCE(CAST(SUM(si.unit_cost) AS REAL), 0)
         FROM sale_items si
         JOIN sales s ON s.sale_id = si.sale_id
         WHERE s.fulfillment_status IN ('shipped','delivered')
           AND date(COALESCE(s.shipped_at, s.occurred_at)) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // Marketing: expenses category=marketing in range
    let marketing_logged: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
         WHERE category = 'marketing'
           AND date(paid_at) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    // Opex: expenses NOT (marketing, owner_draw)
    let opex: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
         WHERE category NOT IN ('marketing','owner_draw')
           AND date(paid_at) BETWEEN date(?1) AND date(?2)",
        rusqlite::params![&period_start, &period_end],
        |r| r.get(0),
    ).unwrap_or(0.0);

    let profit = revenue - cogs - marketing_logged - opex;

    let prev_profit = if let (Some(ps), Some(pe)) = (prev_start, prev_end) {
        let prev_rev: f64 = conn.query_row(
            "SELECT COALESCE(CAST(SUM(total) AS REAL), 0) FROM sales
             WHERE fulfillment_status IN ('shipped','delivered')
               AND date(COALESCE(shipped_at, occurred_at)) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        let prev_cogs: f64 = conn.query_row(
            "SELECT COALESCE(CAST(SUM(si.unit_cost) AS REAL), 0)
             FROM sale_items si JOIN sales s ON s.sale_id = si.sale_id
             WHERE s.fulfillment_status IN ('shipped','delivered')
               AND date(COALESCE(s.shipped_at, s.occurred_at)) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        let prev_mkt: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
             WHERE category = 'marketing' AND date(paid_at) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        let prev_opex: f64 = conn.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM expenses
             WHERE category NOT IN ('marketing','owner_draw') AND date(paid_at) BETWEEN date(?1) AND date(?2)",
            rusqlite::params![&ps, &pe], |r| r.get(0),
        ).unwrap_or(0.0);
        Some(prev_rev - prev_cogs - prev_mkt - prev_opex)
    } else {
        None
    };

    let trend_pct = match prev_profit {
        Some(prev) if prev != 0.0 => Some(((profit - prev) / prev.abs()) * 100.0),
        _ => None,
    };

    Ok(ProfitSnapshot {
        period_start, period_end, period_label,
        revenue_gtq: revenue, cogs_gtq: cogs,
        marketing_gtq: marketing_logged, opex_gtq: opex,
        profit_operativo: profit,
        prev_period_profit: prev_profit, trend_pct,
    })
}

#[tauri::command]
async fn cmd_get_home_snapshot(
    app: tauri::AppHandle,
    period_start: String,
    period_end: String,
    period_label: String,
    prev_start: Option<String>,
    prev_end: Option<String>,
) -> Result<HomeSnapshot> {
    let profit = cmd_compute_profit_snapshot(
        app, period_start.clone(), period_end.clone(), period_label.clone(),
        prev_start, prev_end,
    ).await?;

    let conn = open_db()?;

    // Cash business: latest balance entry
    let cash_row: Option<(f64, String)> = conn.query_row(
        "SELECT balance_gtq, synced_at FROM cash_balance_history
         WHERE account = 'el_club_business'
         ORDER BY synced_at DESC LIMIT 1",
        [],
        |r| Ok((r.get(0)?, r.get(1)?)),
    ).ok();

    let (cash_business_gtq, cash_synced_at, cash_stale_days) = match cash_row {
        Some((bal, synced)) => {
            let stale: i64 = conn.query_row(
                "SELECT CAST(julianday('now', 'localtime') - julianday(?1) AS INTEGER)",
                rusqlite::params![&synced],
                |r| r.get(0),
            ).unwrap_or(0);
            (Some(bal), Some(synced), Some(stale))
        }
        None => (None, None, None),
    };

    // Capital amarrado: imports with status='paid' (pre-close, capital still tied up)
    let capital: f64 = conn.query_row(
        "SELECT COALESCE(SUM(total_landed_gtq), 0) FROM imports
         WHERE status = 'paid'",
        [],
        |r| r.get(0),
    ).unwrap_or(0.0);

    let loan_balance: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    let loan_trend: f64 = conn.query_row(
        "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements
         WHERE date(movement_date) >= date('now', 'localtime', '-30 days')",
        [], |r| r.get(0),
    ).unwrap_or(0.0);

    Ok(HomeSnapshot {
        profit,
        cash_business_gtq, cash_synced_at, cash_stale_days,
        capital_amarrado_gtq: capital,
        shareholder_loan_balance: loan_balance,
        shareholder_loan_trend_30d: loan_trend,
    })
}

#[tauri::command]
async fn cmd_create_expense(
    _app: tauri::AppHandle,
    input: ExpenseInput,
) -> Result<i64> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    let fx = input.fx_used.unwrap_or(7.73);
    let amount_gtq = match input.currency.as_str() {
        "USD" => input.amount_native * fx,
        "GTQ" => input.amount_native,
        _ => return Err(ErpError::Other(format!("Invalid currency: {}", input.currency))),
    };

    tx.execute(
        "INSERT INTO expenses (amount_gtq, amount_native, currency, fx_used, category, payment_method, paid_at, notes, source)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'manual')",
        rusqlite::params![
            amount_gtq, input.amount_native, input.currency, fx,
            input.category, input.payment_method, input.paid_at, input.notes
        ],
    )?;
    let expense_id = tx.last_insert_rowid();

    // Auto-trigger shareholder_loan_movement if paid with TDC personal
    if input.payment_method == "tdc_personal" {
        let current_balance: f64 = tx.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements",
            [], |r| r.get(0),
        ).unwrap_or(0.0);
        let new_balance = current_balance + amount_gtq;

        tx.execute(
            "INSERT INTO shareholder_loan_movements (amount_gtq, source_type, source_ref, movement_date, loan_balance_after, notes)
             VALUES (?1, 'expense_tdc', ?2, ?3, ?4, ?5)",
            rusqlite::params![
                amount_gtq, expense_id.to_string(), input.paid_at, new_balance, input.notes
            ],
        )?;
    }

    tx.commit()?;
    Ok(expense_id)
}

#[tauri::command]
async fn cmd_list_expenses(
    _app: tauri::AppHandle,
    period_start: Option<String>,
    period_end: Option<String>,
    category: Option<String>,
    payment_method: Option<String>,
    limit: Option<i64>,
) -> Result<Vec<Expense>> {
    let conn = open_db()?;

    let mut where_clauses: Vec<String> = vec!["1=1".to_string()];
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    if let Some(s) = period_start.as_ref() {
        where_clauses.push("date(paid_at) >= date(?)".to_string());
        params.push(Box::new(s.clone()));
    }
    if let Some(e) = period_end.as_ref() {
        where_clauses.push("date(paid_at) <= date(?)".to_string());
        params.push(Box::new(e.clone()));
    }
    if let Some(c) = category.as_ref() {
        where_clauses.push("category = ?".to_string());
        params.push(Box::new(c.clone()));
    }
    if let Some(pm) = payment_method.as_ref() {
        where_clauses.push("payment_method = ?".to_string());
        params.push(Box::new(pm.clone()));
    }

    let limit_v = limit.unwrap_or(500);
    let sql = format!(
        "SELECT expense_id, amount_gtq, amount_native, currency, fx_used, category, payment_method, paid_at, notes, source, source_ref, created_at
         FROM expenses WHERE {} ORDER BY paid_at DESC, expense_id DESC LIMIT {}",
        where_clauses.join(" AND "), limit_v
    );

    let params_refs: Vec<&dyn rusqlite::ToSql> = params.iter().map(|p| p.as_ref()).collect();
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map(&params_refs[..], |row| {
        Ok(Expense {
            expense_id: row.get(0)?,
            amount_gtq: row.get(1)?,
            amount_native: row.get(2)?,
            currency: row.get(3)?,
            fx_used: row.get(4)?,
            category: row.get(5)?,
            payment_method: row.get(6)?,
            paid_at: row.get(7)?,
            notes: row.get(8)?,
            source: row.get(9)?,
            source_ref: row.get(10)?,
            created_at: row.get(11)?,
        })
    })?;
    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}

#[tauri::command]
async fn cmd_delete_expense(_app: tauri::AppHandle, expense_id: i64) -> Result<()> {
    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    tx.execute(
        "DELETE FROM shareholder_loan_movements
         WHERE source_type = 'expense_tdc' AND source_ref = ?1",
        rusqlite::params![expense_id.to_string()],
    )?;

    tx.execute(
        "DELETE FROM expenses WHERE expense_id = ?1",
        rusqlite::params![expense_id],
    )?;

    tx.commit()?;
    Ok(())
}

#[tauri::command]
async fn cmd_update_expense(
    _app: tauri::AppHandle,
    expense_id: i64,
    input: ExpenseInput,
) -> Result<()> {
    // Validate currency before opening tx (avoids holding a write lock for nothing)
    let fx = input.fx_used.unwrap_or(7.73);
    let amount_gtq = match input.currency.as_str() {
        "USD" => input.amount_native * fx,
        "GTQ" => input.amount_native,
        _ => return Err(ErpError::Other(format!("Invalid currency: {}", input.currency))),
    };

    let mut conn = open_db()?;
    let tx = conn.transaction()?;

    // Drop any existing shareholder_loan_movement linked to this expense_id.
    // If the new payment_method is also tdc_personal, we'll re-insert below.
    tx.execute(
        "DELETE FROM shareholder_loan_movements
         WHERE source_type = 'expense_tdc' AND source_ref = ?1",
        rusqlite::params![expense_id.to_string()],
    )?;

    // Update expense in place (preserves expense_id + created_at)
    let updated = tx.execute(
        "UPDATE expenses
         SET amount_gtq = ?1, amount_native = ?2, currency = ?3, fx_used = ?4,
             category = ?5, payment_method = ?6, paid_at = ?7, notes = ?8
         WHERE expense_id = ?9",
        rusqlite::params![
            amount_gtq, input.amount_native, input.currency, fx,
            input.category, input.payment_method, input.paid_at, input.notes,
            expense_id
        ],
    )?;

    if updated == 0 {
        // Roll back implicitly by not committing — drop the tx.
        return Err(ErpError::Other(format!("expense {} not found", expense_id)));
    }

    // If new payment_method is tdc_personal, re-create the loan movement
    if input.payment_method == "tdc_personal" {
        let current_balance: f64 = tx.query_row(
            "SELECT COALESCE(SUM(amount_gtq), 0) FROM shareholder_loan_movements",
            [], |r| r.get(0),
        ).unwrap_or(0.0);
        let new_balance = current_balance + amount_gtq;

        tx.execute(
            "INSERT INTO shareholder_loan_movements (amount_gtq, source_type, source_ref, movement_date, loan_balance_after, notes)
             VALUES (?1, 'expense_tdc', ?2, ?3, ?4, ?5)",
            rusqlite::params![
                amount_gtq, expense_id.to_string(), input.paid_at, new_balance, input.notes
            ],
        )?;
    }

    tx.commit()?;
    Ok(())
}

#[tauri::command]
async fn cmd_recent_expenses(
    _app: tauri::AppHandle,
    limit: Option<i64>,
) -> Result<Vec<RecentExpenseRow>> {
    let conn = open_db()?;
    let limit_v = limit.unwrap_or(6);
    let mut stmt = conn.prepare(
        "SELECT expense_id, paid_at, category, payment_method, amount_gtq, notes
         FROM expenses ORDER BY paid_at DESC, expense_id DESC LIMIT ?1"
    )?;
    let rows = stmt.query_map(rusqlite::params![limit_v], |row| {
        Ok(RecentExpenseRow {
            expense_id: row.get(0)?,
            paid_at: row.get(1)?,
            category: row.get(2)?,
            payment_method: row.get(3)?,
            amount_gtq: row.get(4)?,
            notes: row.get(5)?,
        })
    })?;
    Ok(rows.collect::<std::result::Result<Vec<_>, _>>()?)
}

#[tauri::command]
async fn cmd_set_cash_balance(
    _app: tauri::AppHandle,
    balance_gtq: f64,
    source: String,
    notes: Option<String>,
) -> Result<i64> {
    let conn = open_db()?;
    conn.execute(
        "INSERT INTO cash_balance_history (account, balance_gtq, synced_at, source, notes)
         VALUES ('el_club_business', ?1, datetime('now', 'localtime'), ?2, ?3)",
        rusqlite::params![balance_gtq, source, notes],
    )?;
    Ok(conn.last_insert_rowid())
}

// ═══════════════════════════════════════════════════════════════════════
// ADMIN WEB R7 — Tauri commands para el modulo Admin Web
// ═══════════════════════════════════════════════════════════════════════
// Spec: overhaul/docs/superpowers/specs/admin-web/. Schema: 26 tablas
// nuevas + 4 cols en audit_decisions (T1.1). Tipos TS: lib/data/admin-web.ts
// + adapter/types.ts AdminWebTauriCommands. Estos commands son invocados via
// adminWebTauri en lib/adapter/tauri.ts.
//
// Convencion: structs serializan/deserializan con default serde (snake_case)
// porque el JS adapter envia args/recibe results en snake_case (el spec
// AdminWebTauriCommands usa snake_case para campos).

#[derive(Debug, Serialize)]
pub struct HomeKpis {
    pub publicados_total: i64,
    pub stock_live: i64,
    pub queue_count: i64,
    pub scheduled_30d: i64,
    pub activity_month: i64,
    pub supplier_gaps: i64,
    pub hours_since_last_scrap: i64,
    pub dirty_count: i64,
    pub sparklines: std::collections::HashMap<String, Vec<f64>>,
}

#[derive(Debug, Deserialize)]
pub struct ListInboxEventsArgs {
    #[serde(default)]
    pub include_dismissed: Option<bool>,
    #[serde(default)]
    pub severity_filter: Option<Vec<String>>,
}

#[derive(Debug, Serialize)]
pub struct InboxEventOut {
    pub id: i64,
    pub r#type: String,
    pub severity: String,
    pub title: String,
    pub description: Option<String>,
    pub action_label: Option<String>,
    pub action_target: Option<String>,
    pub module: String,
    pub metadata: Option<Value>,
    pub created_at: i64,
    pub dismissed_at: Option<i64>,
    pub resolved_at: Option<i64>,
    pub expires_at: Option<i64>,
}

fn count_supplier_gaps_in_catalog(catalog: &[Value]) -> i64 {
    catalog
        .iter()
        .filter(|f| {
            // status='deleted' zombies fuera
            let status = f.get("status").and_then(|v| v.as_str()).unwrap_or("");
            if status == "deleted" {
                return false;
            }
            f.get("supplier_gap").and_then(|v| v.as_bool()).unwrap_or(false)
        })
        .count() as i64
}

fn load_sparklines(conn: &rusqlite::Connection) -> Result<std::collections::HashMap<String, Vec<f64>>> {
    // Lee últimos 7 puntos de kpi_snapshots por kpi_key.
    // Si no hay datos (la tabla está vacía hasta que el cron daily corra),
    // devuelve vacío — la UI maneja el caso "sin sparkline".
    let mut out = std::collections::HashMap::<String, Vec<f64>>::new();
    let kpi_keys = [
        "publicados_total",
        "stock_live",
        "queue_count",
        "scheduled_30d",
        "activity_month",
        "supplier_gaps",
        "hours_since_last_scrap",
        "dirty_count",
    ];
    for key in kpi_keys {
        let mut stmt = conn.prepare(
            "SELECT value FROM kpi_snapshots WHERE kpi_key = ?1 ORDER BY date DESC LIMIT 7",
        )?;
        let rows = stmt.query_map([key], |row| row.get::<_, f64>(0))?;
        let mut values: Vec<f64> = rows.filter_map(|r| r.ok()).collect();
        values.reverse(); // chronological: oldest → newest
        if !values.is_empty() {
            out.insert(key.to_string(), values);
        }
    }
    Ok(out)
}

#[tauri::command]
fn get_admin_web_kpis(state: tauri::State<AppState>) -> Result<HomeKpis> {
    let conn = open_db()?;
    let catalog = load_catalog(&state)?;

    let publicados_total: i64 = conn.query_row(
        "SELECT COUNT(*) FROM audit_decisions WHERE status='verified' AND final_verified=1 AND archived_at IS NULL",
        [],
        |row| row.get(0),
    )?;

    let queue_count: i64 = conn.query_row(
        "SELECT COUNT(*) FROM audit_decisions WHERE status='pending'",
        [],
        |row| row.get(0),
    )?;

    let stock_live: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM v_stock_status WHERE computed_status='live'",
            [],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let scheduled_30d: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM stock_overrides WHERE publish_at IS NOT NULL
                AND publish_at > unixepoch()
                AND publish_at < unixepoch() + 60*60*24*30",
            [],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let activity_month: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM system_audit_log
                WHERE timestamp > unixepoch() - 60*60*24*30",
            [],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let dirty_count: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM audit_decisions WHERE dirty_flag=1",
            [],
            |row| row.get(0),
        )
        .unwrap_or(0);

    // Last scrap: max(started_at) en scrap_history. Si no hay rows, 0 (=> 999h).
    let last_scrap_at: Option<i64> = conn
        .query_row(
            "SELECT MAX(started_at) FROM scrap_history WHERE status='success'",
            [],
            |row| row.get::<_, Option<i64>>(0),
        )
        .unwrap_or(None);
    let now = chrono::Utc::now().timestamp();
    let hours_since_last_scrap = last_scrap_at
        .map(|ts| (now - ts) / 3600)
        .unwrap_or(999); // sin scrap registrado

    let supplier_gaps = count_supplier_gaps_in_catalog(&catalog);

    let sparklines = load_sparklines(&conn).unwrap_or_default();

    Ok(HomeKpis {
        publicados_total,
        stock_live,
        queue_count,
        scheduled_30d,
        activity_month,
        supplier_gaps,
        hours_since_last_scrap,
        dirty_count,
        sparklines,
    })
}

#[tauri::command]
fn get_module_stats(module: String) -> Result<Value> {
    // Mini-stats por modulo para el sidebar/Home tiles. Devuelve JSON libre.
    // No toma AppState hoy (todas las queries son SQLite directas) pero si en
    // R7.1+ los stats requieren catalog.json, agregar tauri::State<AppState>.
    let conn = open_db()?;
    let mut stats = serde_json::Map::new();

    match module.as_str() {
        "vault" => {
            let queue: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM audit_decisions WHERE status='pending'",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            let publicados: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM audit_decisions WHERE status='verified' AND final_verified=1",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            stats.insert("queue".to_string(), Value::from(queue));
            stats.insert("publicados".to_string(), Value::from(publicados));
        }
        "stock" => {
            let live: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM v_stock_status WHERE computed_status='live'",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            let scheduled: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM v_stock_status WHERE computed_status='scheduled'",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            stats.insert("live".to_string(), Value::from(live));
            stats.insert("scheduled".to_string(), Value::from(scheduled));
        }
        "mystery" => {
            let live: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM v_mystery_status WHERE computed_status='live'",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            let total: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM mystery_overrides",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            stats.insert("live".to_string(), Value::from(live));
            stats.insert("total".to_string(), Value::from(total));
        }
        "site" => {
            let pages: i64 = conn
                .query_row("SELECT COUNT(*) FROM site_pages", [], |row| row.get(0))
                .unwrap_or(0);
            let live_pages: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM site_pages WHERE status='live'",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            stats.insert("pages".to_string(), Value::from(pages));
            stats.insert("live_pages".to_string(), Value::from(live_pages));
        }
        "sistema" => {
            let jobs: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM scheduled_jobs WHERE enabled=1",
                    [],
                    |row| row.get(0),
                )
                .unwrap_or(0);
            let backups: i64 = conn
                .query_row("SELECT COUNT(*) FROM backups", [], |row| row.get(0))
                .unwrap_or(0);
            stats.insert("jobs".to_string(), Value::from(jobs));
            stats.insert("backups".to_string(), Value::from(backups));
        }
        _ => {
            // Modulo desconocido — devuelvo vacio
        }
    }

    Ok(Value::Object(stats))
}

#[tauri::command]
fn list_inbox_events(args: Option<ListInboxEventsArgs>) -> Result<Vec<InboxEventOut>> {
    let conn = open_db()?;
    let args = args.unwrap_or(ListInboxEventsArgs {
        include_dismissed: None,
        severity_filter: None,
    });

    let include_dismissed = args.include_dismissed.unwrap_or(false);

    let mut q = String::from(
        "SELECT id, type, severity, title, description, action_label, action_target,
                module, metadata, created_at, dismissed_at, resolved_at, expires_at
         FROM inbox_events
         WHERE resolved_at IS NULL
           AND (expires_at IS NULL OR expires_at > unixepoch())",
    );
    if !include_dismissed {
        q.push_str(" AND dismissed_at IS NULL");
    }
    if let Some(ref sevs) = args.severity_filter {
        if !sevs.is_empty() {
            let placeholders: Vec<String> = (0..sevs.len()).map(|_| "?".to_string()).collect();
            q.push_str(&format!(" AND severity IN ({})", placeholders.join(",")));
        }
    }
    q.push_str(" ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'important' THEN 1 ELSE 2 END, created_at DESC");

    let mut stmt = conn.prepare(&q)?;

    let params: Vec<&dyn rusqlite::ToSql> = if let Some(ref sevs) = args.severity_filter {
        sevs.iter().map(|s| s as &dyn rusqlite::ToSql).collect()
    } else {
        vec![]
    };

    let rows = stmt.query_map(params.as_slice(), |row| {
        let metadata_str: Option<String> = row.get("metadata")?;
        let metadata: Option<Value> = metadata_str.and_then(|s| serde_json::from_str(&s).ok());
        Ok(InboxEventOut {
            id: row.get("id")?,
            r#type: row.get("type")?,
            severity: row.get("severity")?,
            title: row.get("title")?,
            description: row.get("description").ok(),
            action_label: row.get("action_label").ok(),
            action_target: row.get("action_target").ok(),
            module: row.get("module")?,
            metadata,
            created_at: row.get("created_at")?,
            dismissed_at: row.get("dismissed_at").ok(),
            resolved_at: row.get("resolved_at").ok(),
            expires_at: row.get("expires_at").ok(),
        })
    })?;

    let events: Vec<InboxEventOut> = rows.filter_map(|r| r.ok()).collect();
    Ok(events)
}

// Auto-dismiss days por severity — match con AUTO_DISMISS_DAYS de TS.
// None = no expira (critical persiste hasta resolverse manualmente).
fn auto_dismiss_seconds(severity: &str) -> Option<i64> {
    match severity {
        "critical" => None,
        "important" => Some(7 * 86400),
        "info" => Some(3 * 86400),
        _ => Some(7 * 86400),
    }
}

// Insert un evento si no existe uno active del mismo type+module sin
// dismiss/resolve. Si ya existe, hace UPDATE de title/description (refrescar
// counts) en lugar de duplicar.
fn upsert_event(
    conn: &rusqlite::Connection,
    event_type: &str,
    module: &str,
    severity: &str,
    title: &str,
    description: Option<&str>,
    action_label: Option<&str>,
    action_target: Option<&str>,
) -> Result<bool> {
    // Existe activo?
    let existing_id: Option<i64> = conn
        .query_row(
            "SELECT id FROM inbox_events
             WHERE type = ?1 AND module = ?2
               AND dismissed_at IS NULL AND resolved_at IS NULL
             LIMIT 1",
            rusqlite::params![event_type, module],
            |row| row.get(0),
        )
        .ok();

    if let Some(id) = existing_id {
        // Refresh título y descripción (los counts pueden cambiar)
        conn.execute(
            "UPDATE inbox_events SET title = ?1, description = ?2 WHERE id = ?3",
            rusqlite::params![title, description, id],
        )?;
        return Ok(false); // no creó uno nuevo
    }

    // Insert nuevo
    let expires_at = auto_dismiss_seconds(severity)
        .map(|secs| chrono::Utc::now().timestamp() + secs);

    conn.execute(
        "INSERT INTO inbox_events
            (type, severity, title, description, action_label, action_target,
             module, expires_at)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        rusqlite::params![
            event_type,
            severity,
            title,
            description,
            action_label,
            action_target,
            module,
            expires_at
        ],
    )?;
    Ok(true)
}

// Resolve cualquier evento active del type+module dado.
fn resolve_events_of_type(
    conn: &rusqlite::Connection,
    event_type: &str,
    module: &str,
) -> Result<u64> {
    let count = conn.execute(
        "UPDATE inbox_events SET resolved_at = unixepoch()
         WHERE type = ?1 AND module = ?2
           AND dismissed_at IS NULL AND resolved_at IS NULL",
        rusqlite::params![event_type, module],
    )? as u64;
    Ok(count)
}

#[tauri::command]
fn detect_events_now(state: tauri::State<AppState>) -> Result<serde_json::Value> {
    // T3.5: detector que corre los queries del catálogo y upsertea eventos.
    // Implementa subset de los 36 eventos del spec — los más críticos para
    // el día a día. El resto (banner_expires, ab_test_significant, nps_dropped,
    // etc) requieren tablas/integraciones que viven en el worker (T7+) y se
    // suman cuando estén disponibles.
    let conn = open_db()?;
    let mut events_created: u64 = 0;
    let mut events_resolved: u64 = 0;

    // ─── VAULT — queue_pending ──────────────────────────────────────
    {
        let queue_count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM audit_decisions WHERE status='pending'",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if queue_count > 0 {
            let title = format!("{} jerseys esperando audit", queue_count);
            let description = if queue_count >= 30 {
                format!("Queue alto · {} pendientes", queue_count)
            } else {
                format!("{} pendientes en cola", queue_count)
            };
            let severity = if queue_count >= 30 { "critical" } else { "info" };
            if upsert_event(
                &conn,
                "queue_pending",
                "vault",
                severity,
                &title,
                Some(&description),
                Some("QUEUE"),
                Some("/admin-web/vault/queue"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "queue_pending", "vault")?;
        }
    }

    // ─── VAULT — dirty_detected ─────────────────────────────────────
    {
        let dirty_count: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM audit_decisions WHERE dirty_flag=1",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if dirty_count > 0 {
            let title = format!("{} jerseys con foto rota", dirty_count);
            let severity = if dirty_count >= 10 { "critical" } else { "important" };
            if upsert_event(
                &conn,
                "dirty_detected",
                "vault",
                severity,
                &title,
                Some("Detector encontró galleries rotas / CDN stale"),
                Some("REVISAR"),
                Some("/admin-web/vault/universo"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "dirty_detected", "vault")?;
        }
    }

    // ─── VAULT — orphan_drafts ──────────────────────────────────────
    // Drafts (status NOT pending/verified/deleted) sin actividad > 30d
    {
        let orphans: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM audit_decisions
                 WHERE status NOT IN ('pending','verified','deleted')
                   AND archived_at IS NULL
                   AND (decided_at IS NULL OR decided_at < datetime('now', '-30 days'))",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if orphans > 5 {
            let title = format!("{} drafts huérfanos > 30d", orphans);
            if upsert_event(
                &conn,
                "orphan_drafts",
                "vault",
                "important",
                &title,
                Some("DRAFTs sin actividad reciente — revisar o archivar"),
                Some("REVISAR"),
                Some("/admin-web/vault/universo"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "orphan_drafts", "vault")?;
        }
    }

    // ─── VAULT — supplier_gap (count en catalog.json) ───────────────
    {
        let catalog = load_catalog(&state).unwrap_or_default();
        let gaps = count_supplier_gaps_in_catalog(&catalog);
        if gaps >= 15 {
            let title = format!("{} jerseys sin proveedor", gaps);
            let severity = if gaps >= 50 { "critical" } else { "important" };
            if upsert_event(
                &conn,
                "supplier_gap_new",
                "vault",
                severity,
                &title,
                Some("Catalog tiene supplier_gap=true sin resolver — escalar a Diego/HB"),
                Some("VER"),
                Some("/admin-web/vault/universo"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "supplier_gap_new", "vault")?;
        }
    }

    // ─── STOCK — drop_starting_24h ──────────────────────────────────
    {
        let starting: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM stock_overrides
                 WHERE publish_at IS NOT NULL
                   AND publish_at > unixepoch()
                   AND publish_at < unixepoch() + 86400",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if starting > 0 {
            let title = format!("{} drop(s) Stock arrancan en 24h", starting);
            if upsert_event(
                &conn,
                "stock_drop_starting_24h",
                "stock",
                "info",
                &title,
                None,
                Some("CALENDARIO"),
                Some("/admin-web/stock/calendario"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "stock_drop_starting_24h", "stock")?;
        }
    }

    // ─── MYSTERY — pool_low ─────────────────────────────────────────
    {
        let pool: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM v_mystery_status WHERE computed_status='live'",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if pool == 0 {
            if upsert_event(
                &conn,
                "mystery_pool_empty",
                "mystery",
                "critical",
                "Pool Mystery vacío",
                Some("Sin jerseys live en pool — agregar urgente o pausar producto"),
                Some("POOL"),
                Some("/admin-web/mystery/pool"),
            )? {
                events_created += 1;
            }
            events_resolved += resolve_events_of_type(&conn, "mystery_pool_low", "mystery")?;
        } else if pool < 5 {
            let title = format!("Pool Mystery con solo {} jerseys", pool);
            if upsert_event(
                &conn,
                "mystery_pool_low",
                "mystery",
                "important",
                &title,
                Some("Pool bajo — agregar más antes de que se quede en cero"),
                Some("POOL"),
                Some("/admin-web/mystery/pool"),
            )? {
                events_created += 1;
            }
            events_resolved += resolve_events_of_type(&conn, "mystery_pool_empty", "mystery")?;
        } else {
            events_resolved += resolve_events_of_type(&conn, "mystery_pool_low", "mystery")?;
            events_resolved += resolve_events_of_type(&conn, "mystery_pool_empty", "mystery")?;
        }
    }

    // ─── SISTEMA — last_backup_old ──────────────────────────────────
    {
        let last_backup: Option<i64> = conn
            .query_row(
                "SELECT MAX(created_at) FROM backups",
                [],
                |row| row.get::<_, Option<i64>>(0),
            )
            .unwrap_or(None);
        let stale = match last_backup {
            None => true, // never backed up
            Some(ts) => chrono::Utc::now().timestamp() - ts > 7 * 86400,
        };
        if stale {
            if upsert_event(
                &conn,
                "last_backup_old",
                "sistema",
                "important",
                "Sin backup en > 7d",
                Some("El último backup tiene > 7 días — crear nuevo manual o revisar cron"),
                Some("BACKUPS"),
                Some("/admin-web/sistema/operaciones"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "last_backup_old", "sistema")?;
        }
    }

    // ─── SISTEMA — cron_job_failed ──────────────────────────────────
    {
        let failed: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM scheduled_jobs WHERE last_status='failed'",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if failed > 0 {
            let title = format!("{} cron job(s) fallaron", failed);
            if upsert_event(
                &conn,
                "cron_job_failed",
                "sistema",
                "important",
                &title,
                Some("Revisar last_error en scheduled_jobs y volver a correr o fix"),
                Some("OPS"),
                Some("/admin-web/sistema/operaciones"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "cron_job_failed", "sistema")?;
        }
    }

    // ─── COMUNIDAD — reviews_pending_moderation ─────────────────────
    {
        let pending_reviews: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM reviews WHERE status='pending'",
                [],
                |row| row.get(0),
            )
            .unwrap_or(0);
        if pending_reviews > 0 {
            let title = format!("{} review(s) sin moderar", pending_reviews);
            if upsert_event(
                &conn,
                "reviews_pending_moderation",
                "site",
                "info",
                &title,
                Some("Reviews esperando aprobación/rechazo"),
                Some("MODERAR"),
                Some("/admin-web/site/comunidad"),
            )? {
                events_created += 1;
            }
        } else {
            events_resolved += resolve_events_of_type(&conn, "reviews_pending_moderation", "site")?;
        }
    }

    // Auto-expire: cualquier evento con expires_at vencido se resolve
    let auto_expired = conn.execute(
        "UPDATE inbox_events SET resolved_at = unixepoch()
         WHERE expires_at IS NOT NULL AND expires_at < unixepoch()
           AND dismissed_at IS NULL AND resolved_at IS NULL",
        [],
    )? as u64;

    Ok(serde_json::json!({
        "events_created": events_created,
        "events_resolved": events_resolved + auto_expired,
        "auto_expired": auto_expired
    }))
}

#[tauri::command]
fn dismiss_event(id: i64) -> Result<()> {
    let conn = open_db()?;
    conn.execute(
        "UPDATE inbox_events SET dismissed_at = unixepoch() WHERE id = ?1 AND dismissed_at IS NULL",
        rusqlite::params![id],
    )?;
    Ok(())
}

#[tauri::command]
fn resolve_event(id: i64) -> Result<()> {
    let conn = open_db()?;
    conn.execute(
        "UPDATE inbox_events SET resolved_at = unixepoch() WHERE id = ?1 AND resolved_at IS NULL",
        rusqlite::params![id],
    )?;
    Ok(())
}

// ═══════════════════════════════════════════════════════════════════════
// ADMIN WEB R7 — Vault Publicados (T4.3) + promote/archive/dirty
// ═══════════════════════════════════════════════════════════════════════

#[derive(Debug, Deserialize)]
pub struct ListPublishedArgs {
    /// 'all' | 'attention' | 'recent' | 'scheduled' | 'no_tags' | 'old'
    pub filter: Option<String>,
    pub pagination: Option<PaginationArgs>,
}

#[derive(Debug, Deserialize, Default)]
pub struct PaginationArgs {
    pub page: Option<u32>,
    pub per_page: Option<u32>,
}

#[tauri::command]
fn list_published(
    args: Option<ListPublishedArgs>,
    state: tauri::State<AppState>,
) -> Result<Vec<Value>> {
    let args = args.unwrap_or(ListPublishedArgs {
        filter: None,
        pagination: None,
    });
    let filter = args.filter.as_deref().unwrap_or("all");
    let p = args.pagination.unwrap_or_default();
    let per_page = p.per_page.unwrap_or(50).min(200) as i64;
    let page = p.page.unwrap_or(1).max(1) as i64;
    let offset = (page - 1) * per_page;

    let conn = open_db()?;
    let catalog = load_catalog(&state)?;

    // Mapa family_id → catalog row para enriquecer.
    let catalog_by_id: std::collections::HashMap<String, &Value> = catalog
        .iter()
        .filter_map(|f| {
            f.get("family_id")
                .and_then(|v| v.as_str())
                .map(|id| (id.to_string(), f))
        })
        .collect();

    // Filtros compartidos: PUBLISHED = verified+final_verified=1+archived_at IS NULL
    // (excluye REJECTED status='deleted' y ARCHIVED via archived_at).
    let base = "FROM audit_decisions ad
                WHERE ad.status='verified' AND ad.final_verified=1 AND ad.archived_at IS NULL";

    // Filtros derivados
    let extra_where = match filter {
        "attention" => " AND ad.dirty_flag=1",
        "recent" => " AND ad.reviewed_at > datetime('now', '-7 days')",
        "scheduled" => {
            " AND ad.family_id IN (
                SELECT family_id FROM stock_overrides
                WHERE publish_at > unixepoch() AND publish_at < unixepoch() + 60*60*24*30
                UNION
                SELECT family_id FROM mystery_overrides
                WHERE publish_at > unixepoch() AND publish_at < unixepoch() + 60*60*24*30
            )"
        }
        "no_tags" => {
            " AND ad.family_id NOT IN (SELECT DISTINCT family_id FROM jersey_tags)"
        }
        "old" => " AND (ad.reviewed_at IS NULL OR ad.reviewed_at < datetime('now', '-180 days'))",
        _ => "", // 'all' default
    };

    let q = format!(
        "SELECT ad.family_id, ad.tier, ad.dirty_flag, ad.dirty_reason,
                ad.qa_priority, ad.archived_at,
                ad.decided_at, ad.reviewed_at
         {} {}
         ORDER BY ad.reviewed_at DESC NULLS LAST, ad.family_id ASC
         LIMIT ?1 OFFSET ?2",
        base, extra_where
    );

    let mut stmt = conn.prepare(&q)?;
    let rows = stmt.query_map(rusqlite::params![per_page, offset], |row| {
        let family_id: String = row.get("family_id")?;
        let tier: Option<String> = row.get("tier").ok();
        let dirty_flag: i64 = row.get::<_, Option<i64>>("dirty_flag")?.unwrap_or(0);
        let dirty_reason: Option<String> = row.get("dirty_reason").ok();
        let qa_priority: i64 = row.get::<_, Option<i64>>("qa_priority")?.unwrap_or(0);
        let archived_at: Option<i64> = row.get("archived_at").ok();
        let decided_at: Option<String> = row.get("decided_at").ok();
        let reviewed_at: Option<String> = row.get("reviewed_at").ok();
        Ok((
            family_id,
            tier,
            dirty_flag,
            dirty_reason,
            qa_priority,
            archived_at,
            decided_at,
            reviewed_at,
        ))
    })?;

    let mut out: Vec<Value> = vec![];
    for row in rows.flatten() {
        let (family_id, tier, dirty_flag, dirty_reason, qa_priority, archived_at, decided_at, reviewed_at) =
            row;
        let cat_row = catalog_by_id.get(&family_id);
        let team = cat_row
            .and_then(|f| f.get("team").and_then(|v| v.as_str()))
            .unwrap_or("")
            .to_string();
        let season = cat_row
            .and_then(|f| f.get("season").and_then(|v| v.as_str()))
            .unwrap_or("")
            .to_string();
        let variant = cat_row
            .and_then(|f| f.get("variant").and_then(|v| v.as_str()))
            .unwrap_or("")
            .to_string();
        let hero = cat_row
            .and_then(|f| f.get("hero_thumbnail").and_then(|v| v.as_str()))
            .map(|s| s.to_string());
        let gallery = cat_row
            .and_then(|f| f.get("gallery"))
            .cloned()
            .unwrap_or(Value::Array(vec![]));
        let sku = cat_row
            .and_then(|f| f.get("sku").and_then(|v| v.as_str()))
            .unwrap_or(family_id.as_str())
            .to_string();

        let mut o = serde_json::Map::new();
        o.insert("family_id".into(), Value::from(family_id));
        o.insert("sku".into(), Value::from(sku));
        o.insert("team".into(), Value::from(team));
        o.insert("season".into(), Value::from(season));
        o.insert("variant".into(), Value::from(variant));
        o.insert("hero_thumbnail".into(), hero.map(Value::from).unwrap_or(Value::Null));
        o.insert("gallery".into(), gallery);
        o.insert("tier".into(), tier.map(Value::from).unwrap_or(Value::Null));
        o.insert("state".into(), Value::from("PUBLISHED"));
        let mut flags = serde_json::Map::new();
        flags.insert("dirty".into(), Value::from(dirty_flag == 1));
        flags.insert("dirty_reason".into(), dirty_reason.map(Value::from).unwrap_or(Value::Null));
        flags.insert("qa_priority".into(), Value::from(qa_priority));
        o.insert("flags".into(), Value::Object(flags));
        o.insert(
            "archived_at".into(),
            archived_at.map(Value::from).unwrap_or(Value::Null),
        );
        o.insert("decided_at".into(), decided_at.map(Value::from).unwrap_or(Value::Null));
        o.insert(
            "reviewed_at".into(),
            reviewed_at.map(Value::from).unwrap_or(Value::Null),
        );
        out.push(Value::Object(o));
    }

    Ok(out)
}

#[derive(Debug, Deserialize)]
pub struct ToggleDirtyFlagArgs {
    pub family_id: String,
    pub dirty: bool,
    pub reason: Option<String>,
}

#[tauri::command]
fn toggle_dirty_flag(args: ToggleDirtyFlagArgs) -> Result<()> {
    let conn = open_db()?;
    if args.dirty {
        conn.execute(
            "UPDATE audit_decisions
             SET dirty_flag = 1, dirty_reason = ?1, dirty_detected_at = unixepoch()
             WHERE family_id = ?2",
            rusqlite::params![args.reason, args.family_id],
        )?;
    } else {
        conn.execute(
            "UPDATE audit_decisions
             SET dirty_flag = 0, dirty_reason = NULL, dirty_detected_at = NULL
             WHERE family_id = ?1",
            rusqlite::params![args.family_id],
        )?;
    }
    Ok(())
}

#[derive(Debug, Deserialize)]
pub struct ArchiveJerseyArgs {
    pub family_id: String,
}

#[tauri::command]
fn archive_jersey(args: ArchiveJerseyArgs) -> Result<()> {
    let conn = open_db()?;
    conn.execute(
        "UPDATE audit_decisions SET archived_at = unixepoch()
         WHERE family_id = ?1 AND archived_at IS NULL",
        rusqlite::params![args.family_id],
    )?;
    Ok(())
}

#[derive(Debug, Deserialize)]
pub struct ReviveArchivedArgs {
    pub family_id: String,
    pub scheduled_at: Option<i64>,
}

#[tauri::command]
fn revive_archived(args: ReviveArchivedArgs) -> Result<()> {
    let conn = open_db()?;
    conn.execute(
        "UPDATE audit_decisions SET archived_at = NULL WHERE family_id = ?1",
        rusqlite::params![args.family_id],
    )?;
    // Si scheduled_at: crear stock_override scheduled (asumimos Stock por default)
    if let Some(ts) = args.scheduled_at {
        conn.execute(
            "INSERT INTO stock_overrides (family_id, publish_at, status, priority)
             VALUES (?1, ?2, 'scheduled', 5)",
            rusqlite::params![args.family_id, ts],
        )?;
    }
    Ok(())
}

#[derive(Debug, Deserialize)]
pub struct PromoteOverridePayload {
    pub publish_at: Option<i64>,
    pub unpublish_at: Option<i64>,
    pub price_override: Option<i64>,
    pub badge: Option<String>,
    pub copy_override: Option<String>,
    pub priority: Option<i64>,
    pub pool_weight: Option<f64>,
}

// JS pasa { family_id, override }. Rust necesita renombrar 'override' (palabra
// reservada) → serde_rename = "override" para deserializar correctamente.
#[derive(Debug, Deserialize)]
pub struct PromoteToStockJsonArgs {
    pub family_id: String,
    #[serde(rename = "override")]
    pub override_: PromoteOverridePayload,
}

#[derive(Debug, Deserialize)]
pub struct PromoteToMysteryJsonArgs {
    pub family_id: String,
    #[serde(rename = "override")]
    pub override_: PromoteOverridePayload,
}

#[tauri::command]
fn promote_to_stock(args: PromoteToStockJsonArgs) -> Result<Value> {
    let conn = open_db()?;
    let o = &args.override_;
    let priority = o.priority.unwrap_or(5).clamp(1, 10);
    let status = if o.publish_at.is_none() {
        "draft"
    } else if o.publish_at.unwrap() > chrono::Utc::now().timestamp() {
        "scheduled"
    } else {
        "live"
    };
    conn.execute(
        "INSERT INTO stock_overrides
            (family_id, publish_at, unpublish_at, price_override, badge,
             copy_override, priority, status, created_by)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'diego')",
        rusqlite::params![
            args.family_id,
            o.publish_at,
            o.unpublish_at,
            o.price_override,
            o.badge,
            o.copy_override,
            priority,
            status,
        ],
    )?;
    let id = conn.last_insert_rowid();
    Ok(serde_json::json!({
        "id": id,
        "family_id": args.family_id,
        "publish_at": o.publish_at,
        "unpublish_at": o.unpublish_at,
        "price_override": o.price_override,
        "badge": o.badge,
        "copy_override": o.copy_override,
        "priority": priority,
        "status": status,
        "computed_status": status,
    }))
}

#[tauri::command]
fn promote_to_mystery(args: PromoteToMysteryJsonArgs) -> Result<Value> {
    let conn = open_db()?;
    let o = &args.override_;
    let pool_weight = o.pool_weight.unwrap_or(1.0);
    let status = if o.publish_at.is_none() {
        "draft"
    } else if o.publish_at.unwrap() > chrono::Utc::now().timestamp() {
        "scheduled"
    } else {
        "live"
    };
    conn.execute(
        "INSERT INTO mystery_overrides
            (family_id, publish_at, unpublish_at, pool_weight, status, created_by)
         VALUES (?1, ?2, ?3, ?4, ?5, 'diego')",
        rusqlite::params![
            args.family_id,
            o.publish_at,
            o.unpublish_at,
            pool_weight,
            status,
        ],
    )?;
    let id = conn.last_insert_rowid();
    Ok(serde_json::json!({
        "id": id,
        "family_id": args.family_id,
        "publish_at": o.publish_at,
        "unpublish_at": o.unpublish_at,
        "pool_weight": pool_weight,
        "status": status,
        "computed_status": status,
    }))
}

// ═══════════════════════════════════════════════════════════════════════
// ADMIN WEB R7 — Tags system (T5.1 + T5.2)
// ═══════════════════════════════════════════════════════════════════════

#[derive(Debug, Serialize)]
pub struct TagTypeOut {
    pub id: i64,
    pub slug: String,
    pub display_name: String,
    pub icon: Option<String>,
    pub cardinality: String,
    pub display_order: i64,
    pub conditional_rule: Option<Value>,
    pub description: Option<String>,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Serialize)]
pub struct TagOut {
    pub id: i64,
    pub type_id: i64,
    pub type_slug: String,
    pub slug: String,
    pub display_name: String,
    pub icon: Option<String>,
    pub color: Option<String>,
    pub is_auto_derived: bool,
    pub derivation_rule: Option<Value>,
    pub is_deleted: bool,
    pub display_order: i64,
    pub count: i64,
    pub created_at: i64,
    pub updated_at: i64,
}

#[tauri::command]
fn list_tag_types() -> Result<Vec<TagTypeOut>> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT id, slug, display_name, icon, cardinality, display_order,
                conditional_rule, description, created_at, updated_at
         FROM tag_types ORDER BY display_order ASC, display_name ASC",
    )?;
    let rows = stmt.query_map([], |row| {
        let conditional_rule_str: Option<String> = row.get("conditional_rule").ok();
        let conditional_rule: Option<Value> =
            conditional_rule_str.and_then(|s| serde_json::from_str(&s).ok());
        Ok(TagTypeOut {
            id: row.get("id")?,
            slug: row.get("slug")?,
            display_name: row.get("display_name")?,
            icon: row.get("icon").ok(),
            cardinality: row.get("cardinality")?,
            display_order: row.get("display_order")?,
            conditional_rule,
            description: row.get("description").ok(),
            created_at: row.get("created_at")?,
            updated_at: row.get("updated_at")?,
        })
    })?;
    Ok(rows.filter_map(|r| r.ok()).collect())
}

#[derive(Debug, Deserialize, Default)]
pub struct ListTagsArgs {
    pub type_id: Option<i64>,
    pub include_deleted: Option<bool>,
}

#[tauri::command]
fn list_tags(args: Option<ListTagsArgs>) -> Result<Vec<TagOut>> {
    let conn = open_db()?;
    let args = args.unwrap_or_default();
    let include_deleted = args.include_deleted.unwrap_or(false);

    // LEFT JOIN para count + JOIN tag_types para slug
    let mut q = String::from(
        "SELECT t.id, t.type_id, tt.slug AS type_slug, t.slug, t.display_name,
                t.icon, t.color, t.is_auto_derived, t.derivation_rule,
                t.is_deleted, t.display_order,
                COUNT(jt.tag_id) AS count, t.created_at, t.updated_at
         FROM tags t
         JOIN tag_types tt ON tt.id = t.type_id
         LEFT JOIN jersey_tags jt ON jt.tag_id = t.id
         WHERE 1=1",
    );
    if !include_deleted {
        q.push_str(" AND t.is_deleted = 0");
    }
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];
    if let Some(tid) = args.type_id {
        q.push_str(" AND t.type_id = ?");
        params.push(Box::new(tid));
    }
    q.push_str(" GROUP BY t.id ORDER BY tt.display_order ASC, t.display_order ASC, t.display_name ASC");

    let mut stmt = conn.prepare(&q)?;
    let param_refs: Vec<&dyn rusqlite::ToSql> =
        params.iter().map(|p| p.as_ref() as &dyn rusqlite::ToSql).collect();
    let rows = stmt.query_map(param_refs.as_slice(), |row| {
        let derivation_rule_str: Option<String> = row.get("derivation_rule").ok();
        let derivation_rule: Option<Value> =
            derivation_rule_str.and_then(|s| serde_json::from_str(&s).ok());
        Ok(TagOut {
            id: row.get("id")?,
            type_id: row.get("type_id")?,
            type_slug: row.get("type_slug")?,
            slug: row.get("slug")?,
            display_name: row.get("display_name")?,
            icon: row.get("icon").ok(),
            color: row.get("color").ok(),
            is_auto_derived: row.get::<_, Option<i64>>("is_auto_derived")?.unwrap_or(0) == 1,
            derivation_rule,
            is_deleted: row.get::<_, Option<i64>>("is_deleted")?.unwrap_or(0) == 1,
            display_order: row.get("display_order")?,
            count: row.get("count")?,
            created_at: row.get("created_at")?,
            updated_at: row.get("updated_at")?,
        })
    })?;
    Ok(rows.filter_map(|r| r.ok()).collect())
}

#[derive(Debug, Deserialize)]
pub struct CreateTagArgs {
    pub type_id: i64,
    pub slug: String,
    pub display_name: String,
    pub icon: Option<String>,
    pub color: Option<String>,
}

#[tauri::command]
fn create_tag(args: CreateTagArgs) -> Result<TagOut> {
    let conn = open_db()?;
    conn.execute(
        "INSERT INTO tags (type_id, slug, display_name, icon, color)
         VALUES (?1, ?2, ?3, ?4, ?5)",
        rusqlite::params![args.type_id, args.slug, args.display_name, args.icon, args.color],
    )?;
    let id = conn.last_insert_rowid();
    let type_slug: String = conn.query_row(
        "SELECT slug FROM tag_types WHERE id = ?1",
        rusqlite::params![args.type_id],
        |row| row.get(0),
    )?;
    Ok(TagOut {
        id,
        type_id: args.type_id,
        type_slug,
        slug: args.slug,
        display_name: args.display_name,
        icon: args.icon,
        color: args.color,
        is_auto_derived: false,
        derivation_rule: None,
        is_deleted: false,
        display_order: 0,
        count: 0,
        created_at: chrono::Utc::now().timestamp(),
        updated_at: chrono::Utc::now().timestamp(),
    })
}

#[derive(Debug, Deserialize)]
pub struct UpdateTagArgs {
    pub id: i64,
    pub updates: Value, // partial Tag — solo se aplican campos conocidos
}

#[tauri::command]
fn update_tag(args: UpdateTagArgs) -> Result<()> {
    let conn = open_db()?;
    // Build dynamic UPDATE based on present fields. Whitelist para seguridad.
    let mut sets: Vec<String> = vec!["updated_at = unixepoch()".to_string()];
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    let update_obj = args.updates.as_object().ok_or_else(|| {
        ErpError::Other("updates must be an object".to_string())
    })?;

    let allowed = [
        "display_name",
        "icon",
        "color",
        "display_order",
    ];
    for key in allowed {
        if let Some(v) = update_obj.get(key) {
            sets.push(format!("{} = ?", key));
            match v {
                Value::String(s) => params.push(Box::new(s.clone())),
                Value::Number(n) if n.is_i64() => params.push(Box::new(n.as_i64().unwrap())),
                Value::Null => params.push(Box::new(Option::<String>::None)),
                _ => return Err(ErpError::Other(format!("invalid value for {}", key))),
            }
        }
    }
    if sets.len() == 1 {
        // solo updated_at, nada que hacer
        return Ok(());
    }
    let q = format!("UPDATE tags SET {} WHERE id = ?", sets.join(", "));
    params.push(Box::new(args.id));
    let param_refs: Vec<&dyn rusqlite::ToSql> =
        params.iter().map(|p| p.as_ref() as &dyn rusqlite::ToSql).collect();
    conn.execute(&q, param_refs.as_slice())?;
    Ok(())
}

#[tauri::command]
fn soft_delete_tag(id: i64) -> Result<()> {
    let conn = open_db()?;
    conn.execute(
        "UPDATE tags SET is_deleted = 1, updated_at = unixepoch() WHERE id = ?1",
        rusqlite::params![id],
    )?;
    Ok(())
}

// ─── Tag assignment (T5.2) ───────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct ListJerseyTagsArgs {
    pub family_id: String,
}

#[tauri::command]
fn list_jersey_tags(args: ListJerseyTagsArgs) -> Result<Vec<TagOut>> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT t.id, t.type_id, tt.slug AS type_slug, t.slug, t.display_name,
                t.icon, t.color, t.is_auto_derived, t.derivation_rule,
                t.is_deleted, t.display_order, 0 AS count,
                t.created_at, t.updated_at
         FROM jersey_tags jt
         JOIN tags t ON t.id = jt.tag_id
         JOIN tag_types tt ON tt.id = t.type_id
         WHERE jt.family_id = ?1 AND t.is_deleted = 0
         ORDER BY tt.display_order, t.display_name",
    )?;
    let rows = stmt.query_map([&args.family_id], |row| {
        let derivation_rule_str: Option<String> = row.get("derivation_rule").ok();
        let derivation_rule: Option<Value> =
            derivation_rule_str.and_then(|s| serde_json::from_str(&s).ok());
        Ok(TagOut {
            id: row.get("id")?,
            type_id: row.get("type_id")?,
            type_slug: row.get("type_slug")?,
            slug: row.get("slug")?,
            display_name: row.get("display_name")?,
            icon: row.get("icon").ok(),
            color: row.get("color").ok(),
            is_auto_derived: row.get::<_, Option<i64>>("is_auto_derived")?.unwrap_or(0) == 1,
            derivation_rule,
            is_deleted: row.get::<_, Option<i64>>("is_deleted")?.unwrap_or(0) == 1,
            display_order: row.get("display_order")?,
            count: 0,
            created_at: row.get("created_at")?,
            updated_at: row.get("updated_at")?,
        })
    })?;
    Ok(rows.filter_map(|r| r.ok()).collect())
}

#[derive(Debug, Deserialize)]
pub struct ValidateTagAssignmentArgs {
    pub family_id: String,
    pub tag_id: i64,
}

#[derive(Debug, Serialize)]
pub struct TagAssignmentValidationOut {
    pub valid: bool,
    pub reason: Option<String>,
    pub conflicting_tags: Option<Vec<TagOut>>,
    pub message: Option<String>,
}

#[tauri::command]
fn validate_tag_assignment(args: ValidateTagAssignmentArgs) -> Result<TagAssignmentValidationOut> {
    let conn = open_db()?;

    // Tag existe y no esta deleted?
    let tag_info: Option<(i64, i64, String)> = conn
        .query_row(
            "SELECT t.id, t.type_id, tt.cardinality
             FROM tags t JOIN tag_types tt ON tt.id = t.type_id
             WHERE t.id = ?1 AND t.is_deleted = 0",
            rusqlite::params![args.tag_id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )
        .ok();

    if tag_info.is_none() {
        return Ok(TagAssignmentValidationOut {
            valid: false,
            reason: Some("tag_deleted".into()),
            conflicting_tags: None,
            message: Some("El tag no existe o está soft-deleted".into()),
        });
    }
    let (_tag_id, type_id, cardinality) = tag_info.unwrap();

    // Cardinality 'one': si ya hay un tag de este type para esta jersey, conflict
    if cardinality == "one" {
        let mut stmt = conn.prepare(
            "SELECT t.id, t.type_id, tt.slug AS type_slug, t.slug, t.display_name,
                    t.icon, t.color, t.is_auto_derived, t.derivation_rule,
                    t.is_deleted, t.display_order, 0 AS count,
                    t.created_at, t.updated_at
             FROM jersey_tags jt
             JOIN tags t ON t.id = jt.tag_id
             JOIN tag_types tt ON tt.id = t.type_id
             WHERE jt.family_id = ?1 AND t.type_id = ?2 AND t.id != ?3
               AND t.is_deleted = 0",
        )?;
        let rows = stmt.query_map(
            rusqlite::params![args.family_id, type_id, args.tag_id],
            |row| {
                Ok(TagOut {
                    id: row.get("id")?,
                    type_id: row.get("type_id")?,
                    type_slug: row.get("type_slug")?,
                    slug: row.get("slug")?,
                    display_name: row.get("display_name")?,
                    icon: row.get("icon").ok(),
                    color: row.get("color").ok(),
                    is_auto_derived: row.get::<_, Option<i64>>("is_auto_derived")?.unwrap_or(0)
                        == 1,
                    derivation_rule: None,
                    is_deleted: false,
                    display_order: row.get("display_order")?,
                    count: 0,
                    created_at: row.get("created_at")?,
                    updated_at: row.get("updated_at")?,
                })
            },
        )?;
        let conflicting: Vec<TagOut> = rows.filter_map(|r| r.ok()).collect();
        if !conflicting.is_empty() {
            return Ok(TagAssignmentValidationOut {
                valid: false,
                reason: Some("cardinality_violation".into()),
                conflicting_tags: Some(conflicting),
                message: Some(
                    "Tipo cardinality 'one' — ya hay un tag de este tipo asignado".into(),
                ),
            });
        }
    }

    Ok(TagAssignmentValidationOut {
        valid: true,
        reason: None,
        conflicting_tags: None,
        message: None,
    })
}

#[derive(Debug, Deserialize)]
pub struct AssignTagArgs {
    pub family_id: String,
    pub tag_id: i64,
    pub force_replace: Option<bool>,
}

#[tauri::command]
fn assign_tag(args: AssignTagArgs) -> Result<()> {
    let conn = open_db()?;
    let validation = validate_tag_assignment(ValidateTagAssignmentArgs {
        family_id: args.family_id.clone(),
        tag_id: args.tag_id,
    })?;
    if !validation.valid {
        if validation.reason.as_deref() == Some("cardinality_violation")
            && args.force_replace.unwrap_or(false)
        {
            // Remover conflicting tags
            if let Some(conflicting) = validation.conflicting_tags {
                for ct in conflicting {
                    conn.execute(
                        "DELETE FROM jersey_tags WHERE family_id = ?1 AND tag_id = ?2",
                        rusqlite::params![args.family_id, ct.id],
                    )?;
                }
            }
        } else {
            return Err(ErpError::Other(
                validation
                    .message
                    .unwrap_or_else(|| "validation failed".to_string()),
            ));
        }
    }
    conn.execute(
        "INSERT OR IGNORE INTO jersey_tags (family_id, tag_id, assigned_by)
         VALUES (?1, ?2, 'manual')",
        rusqlite::params![args.family_id, args.tag_id],
    )?;
    Ok(())
}

#[derive(Debug, Deserialize)]
pub struct RemoveTagArgs {
    pub family_id: String,
    pub tag_id: i64,
}

#[tauri::command]
fn remove_tag(args: RemoveTagArgs) -> Result<()> {
    let conn = open_db()?;
    conn.execute(
        "DELETE FROM jersey_tags WHERE family_id = ?1 AND tag_id = ?2",
        rusqlite::params![args.family_id, args.tag_id],
    )?;
    Ok(())
}

#[derive(Debug, Deserialize)]
pub struct ListJerseysByTagArgs {
    pub tag_id: i64,
    pub pagination: Option<PaginationArgs>,
}

#[tauri::command]
fn list_jerseys_by_tag(
    args: ListJerseysByTagArgs,
    state: tauri::State<AppState>,
) -> Result<Vec<Value>> {
    let conn = open_db()?;
    let p = args.pagination.unwrap_or_default();
    let per_page = p.per_page.unwrap_or(50).min(200) as i64;
    let page = p.page.unwrap_or(1).max(1) as i64;
    let offset = (page - 1) * per_page;

    let catalog = load_catalog(&state)?;
    let catalog_by_id: std::collections::HashMap<String, &Value> = catalog
        .iter()
        .filter_map(|f| {
            f.get("family_id")
                .and_then(|v| v.as_str())
                .map(|id| (id.to_string(), f))
        })
        .collect();

    let mut stmt = conn.prepare(
        "SELECT family_id FROM jersey_tags
         WHERE tag_id = ?1
         ORDER BY assigned_at DESC
         LIMIT ?2 OFFSET ?3",
    )?;
    let rows = stmt.query_map(
        rusqlite::params![args.tag_id, per_page, offset],
        |row| {
            let fid: String = row.get(0)?;
            Ok(fid)
        },
    )?;

    let mut out: Vec<Value> = vec![];
    for fid_res in rows {
        if let Ok(fid) = fid_res {
            if let Some(catalog_row) = catalog_by_id.get(&fid) {
                let mut o = serde_json::Map::new();
                o.insert("family_id".into(), Value::from(fid.clone()));
                o.insert(
                    "sku".into(),
                    catalog_row
                        .get("sku")
                        .cloned()
                        .unwrap_or(Value::from(fid.clone())),
                );
                o.insert(
                    "team".into(),
                    catalog_row.get("team").cloned().unwrap_or(Value::Null),
                );
                o.insert(
                    "season".into(),
                    catalog_row.get("season").cloned().unwrap_or(Value::Null),
                );
                o.insert(
                    "hero_thumbnail".into(),
                    catalog_row
                        .get("hero_thumbnail")
                        .cloned()
                        .unwrap_or(Value::Null),
                );
                out.push(Value::Object(o));
            }
        }
    }
    Ok(out)
}

// ═══════════════════════════════════════════════════════════════════════
// ADMIN WEB R7 — Vault Universo (T6.1) + bulk actions (T6.6)
// ═══════════════════════════════════════════════════════════════════════

#[derive(Debug, Deserialize, Default)]
pub struct UniversoFiltersArgs {
    pub states: Option<Vec<String>>, // ['DRAFT','QUEUE','PUBLISHED','REJECTED','ARCHIVED']
    pub flags: Option<Value>,        // partial Record<flag, bool>
    pub tags: Option<Vec<i64>>,      // tag IDs
    pub coverage_min: Option<i64>,
    pub coverage_max: Option<i64>,
    pub last_action: Option<String>, // 'today' | 'week' | 'month' | 'older'
    pub search: Option<String>,
}

#[derive(Debug, Deserialize, Default)]
pub struct SortConfigArgs {
    pub column: Option<String>,
    pub direction: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ListUniversoArgs {
    pub filters: Option<UniversoFiltersArgs>,
    pub sort: Option<SortConfigArgs>,
    pub pagination: PaginationArgs,
}

#[derive(Debug, Serialize)]
pub struct UniversoQueryResultOut {
    pub rows: Vec<Value>,
    pub total: i64,
    pub filters_counts: Value,
}

#[tauri::command]
fn list_universo(
    args: ListUniversoArgs,
    state: tauri::State<AppState>,
) -> Result<UniversoQueryResultOut> {
    let conn = open_db()?;
    let f = args.filters.unwrap_or_default();
    let p = args.pagination;
    let per_page = p.per_page.unwrap_or(50).min(500) as i64;
    let page = p.page.unwrap_or(1).max(1) as i64;
    let offset = (page - 1) * per_page;

    // Construir WHERE dinámico
    let mut wheres: Vec<String> = vec!["1=1".to_string()];
    let mut params: Vec<Box<dyn rusqlite::ToSql>> = vec![];

    // States: usar v_jersey_state computed
    if let Some(states) = &f.states {
        if !states.is_empty() {
            let placeholders: Vec<String> = (0..states.len()).map(|_| "?".to_string()).collect();
            wheres.push(format!(
                "vjs.state IN ({})",
                placeholders.join(",")
            ));
            for s in states {
                params.push(Box::new(s.clone()));
            }
        }
    }

    // Flags
    if let Some(flags) = &f.flags {
        if flags.is_object() {
            if flags.get("dirty").and_then(|v| v.as_bool()) == Some(true) {
                wheres.push("ad.dirty_flag = 1".into());
            }
            if flags.get("qa_priority").and_then(|v| v.as_bool()) == Some(true) {
                wheres.push("ad.qa_priority = 1".into());
            }
        }
    }

    // Search: SKU o family_id contains
    if let Some(search) = &f.search {
        if !search.trim().is_empty() {
            wheres.push("(ad.family_id LIKE ?)".into());
            params.push(Box::new(format!("%{}%", search.trim())));
        }
    }

    // Last action
    if let Some(la) = &f.last_action {
        let cutoff = match la.as_str() {
            "today" => Some("-1 days"),
            "week" => Some("-7 days"),
            "month" => Some("-30 days"),
            "older" => None,
            _ => None,
        };
        if let Some(c) = cutoff {
            wheres.push(format!("(ad.reviewed_at > datetime('now', '{}'))", c));
        } else if la == "older" {
            wheres.push("(ad.reviewed_at IS NULL OR ad.reviewed_at < datetime('now', '-30 days'))".into());
        }
    }

    // Tags (any of)
    if let Some(tag_ids) = &f.tags {
        if !tag_ids.is_empty() {
            let placeholders: Vec<String> = (0..tag_ids.len()).map(|_| "?".to_string()).collect();
            wheres.push(format!(
                "ad.family_id IN (SELECT family_id FROM jersey_tags WHERE tag_id IN ({}))",
                placeholders.join(",")
            ));
            for id in tag_ids {
                params.push(Box::new(*id));
            }
        }
    }

    let where_clause = wheres.join(" AND ");

    // Total count first (para pagination)
    let count_q = format!(
        "SELECT COUNT(*) FROM audit_decisions ad
         JOIN v_jersey_state vjs ON vjs.family_id = ad.family_id
         WHERE {}",
        where_clause
    );
    let param_refs: Vec<&dyn rusqlite::ToSql> =
        params.iter().map(|p| p.as_ref() as &dyn rusqlite::ToSql).collect();
    let total: i64 = conn.query_row(&count_q, param_refs.as_slice(), |row| row.get(0))?;

    // Sort
    let sort = args.sort.unwrap_or_default();
    let sort_col = match sort.column.as_deref().unwrap_or("reviewed_at") {
        "family_id" => "ad.family_id",
        "tier" => "ad.tier",
        "decided_at" => "ad.decided_at",
        "reviewed_at" => "ad.reviewed_at",
        "state" => "vjs.state",
        _ => "ad.reviewed_at",
    };
    let sort_dir = match sort.direction.as_deref().unwrap_or("desc") {
        "asc" => "ASC",
        _ => "DESC",
    };

    // Main query
    let main_q = format!(
        "SELECT ad.family_id, ad.tier, ad.dirty_flag, ad.dirty_reason,
                ad.qa_priority, ad.archived_at, ad.decided_at, ad.reviewed_at,
                vjs.state
         FROM audit_decisions ad
         JOIN v_jersey_state vjs ON vjs.family_id = ad.family_id
         WHERE {}
         ORDER BY {} {} NULLS LAST
         LIMIT ? OFFSET ?",
        where_clause, sort_col, sort_dir
    );
    let mut stmt = conn.prepare(&main_q)?;
    let mut all_params = params;
    all_params.push(Box::new(per_page));
    all_params.push(Box::new(offset));
    let all_param_refs: Vec<&dyn rusqlite::ToSql> = all_params
        .iter()
        .map(|p| p.as_ref() as &dyn rusqlite::ToSql)
        .collect();

    let rows_iter = stmt.query_map(all_param_refs.as_slice(), |row| {
        let family_id: String = row.get("family_id")?;
        let tier: Option<String> = row.get("tier").ok();
        let dirty_flag: i64 = row.get::<_, Option<i64>>("dirty_flag")?.unwrap_or(0);
        let qa_priority: i64 = row.get::<_, Option<i64>>("qa_priority")?.unwrap_or(0);
        let archived_at: Option<i64> = row.get("archived_at").ok();
        let decided_at: Option<String> = row.get("decided_at").ok();
        let reviewed_at: Option<String> = row.get("reviewed_at").ok();
        let state: String = row.get("state")?;
        Ok((
            family_id,
            tier,
            dirty_flag,
            qa_priority,
            archived_at,
            decided_at,
            reviewed_at,
            state,
        ))
    })?;

    let catalog = load_catalog(&state)?;
    let catalog_by_id: std::collections::HashMap<String, &Value> = catalog
        .iter()
        .filter_map(|cf| {
            cf.get("family_id")
                .and_then(|v| v.as_str())
                .map(|id| (id.to_string(), cf))
        })
        .collect();

    let mut rows: Vec<Value> = vec![];
    for row_res in rows_iter {
        let (family_id, tier, dirty_flag, qa_priority, archived_at, decided_at, reviewed_at, state_str) =
            match row_res {
                Ok(t) => t,
                Err(_) => continue,
            };
        let cat = catalog_by_id.get(&family_id);
        let mut o = serde_json::Map::new();
        o.insert("family_id".into(), Value::from(family_id.clone()));
        o.insert(
            "sku".into(),
            cat.and_then(|f| f.get("sku")).cloned().unwrap_or(Value::Null),
        );
        o.insert(
            "team".into(),
            cat.and_then(|f| f.get("team")).cloned().unwrap_or(Value::Null),
        );
        o.insert(
            "season".into(),
            cat.and_then(|f| f.get("season")).cloned().unwrap_or(Value::Null),
        );
        o.insert(
            "variant".into(),
            cat.and_then(|f| f.get("variant")).cloned().unwrap_or(Value::Null),
        );
        o.insert(
            "hero_thumbnail".into(),
            cat.and_then(|f| f.get("hero_thumbnail"))
                .cloned()
                .unwrap_or(Value::Null),
        );
        let coverage = cat
            .and_then(|f| f.get("gallery"))
            .and_then(|g| g.as_array())
            .map(|a| a.len() as i64)
            .unwrap_or(0);
        o.insert("coverage".into(), Value::from(coverage));
        o.insert("tier".into(), tier.map(Value::from).unwrap_or(Value::Null));
        o.insert("state".into(), Value::from(state_str));
        let mut flags = serde_json::Map::new();
        flags.insert("dirty".into(), Value::from(dirty_flag == 1));
        flags.insert("qa_priority".into(), Value::from(qa_priority));
        o.insert("flags".into(), Value::Object(flags));
        o.insert(
            "archived_at".into(),
            archived_at.map(Value::from).unwrap_or(Value::Null),
        );
        o.insert(
            "decided_at".into(),
            decided_at.map(Value::from).unwrap_or(Value::Null),
        );
        o.insert(
            "reviewed_at".into(),
            reviewed_at.map(Value::from).unwrap_or(Value::Null),
        );
        rows.push(Value::Object(o));
    }

    // Filter counts (state breakdown — útil para sidebar)
    let mut state_counts = serde_json::Map::new();
    let mut count_stmt = conn.prepare(
        "SELECT state, COUNT(*) FROM v_jersey_state GROUP BY state",
    )?;
    let state_rows = count_stmt.query_map([], |row| {
        let s: String = row.get(0)?;
        let c: i64 = row.get(1)?;
        Ok((s, c))
    })?;
    for r in state_rows.flatten() {
        state_counts.insert(r.0, Value::from(r.1));
    }

    let filters_counts =
        Value::Object({ let mut m = serde_json::Map::new(); m.insert("by_state".into(), Value::Object(state_counts)); m });

    Ok(UniversoQueryResultOut {
        rows,
        total,
        filters_counts,
    })
}

// ─── Bulk actions (T6.6) ────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct BulkActionArgs {
    pub family_ids: Vec<String>,
    pub action: String, // 'tag' | 'archive' | 're_fetch' | 'delete'
    pub payload: Option<Value>,
}

#[derive(Debug, Serialize)]
pub struct BulkActionResult {
    pub affected: i64,
    pub errors: Vec<String>,
}

#[tauri::command]
fn bulk_action(args: BulkActionArgs) -> Result<BulkActionResult> {
    let conn = open_db()?;
    let mut affected = 0i64;
    let mut errors: Vec<String> = vec![];

    match args.action.as_str() {
        "archive" => {
            for fid in &args.family_ids {
                match conn.execute(
                    "UPDATE audit_decisions SET archived_at = unixepoch()
                     WHERE family_id = ?1 AND archived_at IS NULL",
                    rusqlite::params![fid],
                ) {
                    Ok(n) => affected += n as i64,
                    Err(e) => errors.push(format!("{}: {}", fid, e)),
                }
            }
        }
        "tag" => {
            // payload: { tag_id: number }
            let tag_id = args
                .payload
                .as_ref()
                .and_then(|v| v.get("tag_id"))
                .and_then(|v| v.as_i64())
                .ok_or_else(|| ErpError::Other("payload.tag_id requerido para action='tag'".into()))?;
            for fid in &args.family_ids {
                match conn.execute(
                    "INSERT OR IGNORE INTO jersey_tags (family_id, tag_id, assigned_by)
                     VALUES (?1, ?2, 'bulk:diego')",
                    rusqlite::params![fid, tag_id],
                ) {
                    Ok(n) => affected += n as i64,
                    Err(e) => errors.push(format!("{}: {}", fid, e)),
                }
            }
        }
        "delete" => {
            // Soft delete: status='deleted'
            for fid in &args.family_ids {
                match conn.execute(
                    "UPDATE audit_decisions SET status='deleted' WHERE family_id = ?1",
                    rusqlite::params![fid],
                ) {
                    Ok(n) => affected += n as i64,
                    Err(e) => errors.push(format!("{}: {}", fid, e)),
                }
            }
        }
        "re_fetch" => {
            // Marca dirty para que el detector lo recoja en el siguiente ciclo
            for fid in &args.family_ids {
                match conn.execute(
                    "UPDATE audit_decisions SET dirty_flag = 1, dirty_reason = 're_fetch_requested',
                                                 dirty_detected_at = unixepoch()
                     WHERE family_id = ?1",
                    rusqlite::params![fid],
                ) {
                    Ok(n) => affected += n as i64,
                    Err(e) => errors.push(format!("{}: {}", fid, e)),
                }
            }
        }
        _ => {
            return Err(ErpError::Other(format!("bulk action desconocida: {}", args.action)));
        }
    }

    Ok(BulkActionResult { affected, errors })
}

// ─── Saved views (T6.4) ─────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct ListSavedViewsArgs {
    pub module: String,
}

#[derive(Debug, Serialize)]
pub struct SavedViewOut {
    pub id: i64,
    pub module: String,
    pub slug: String,
    pub display_name: String,
    pub icon: Option<String>,
    pub filters: Value,
    pub sort: Option<Value>,
    pub columns: Option<Value>,
    pub is_factory: bool,
    pub display_order: i64,
    pub created_at: i64,
}

#[tauri::command]
fn list_saved_views(args: ListSavedViewsArgs) -> Result<Vec<SavedViewOut>> {
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT id, module, slug, display_name, icon, filters, sort, columns,
                is_factory, display_order, created_at
         FROM saved_views WHERE module = ?1
         ORDER BY display_order ASC, display_name ASC",
    )?;
    let rows = stmt.query_map([&args.module], |row| {
        let filters_str: String = row.get("filters")?;
        let filters: Value = serde_json::from_str(&filters_str).unwrap_or(Value::Null);
        let sort_str: Option<String> = row.get("sort").ok();
        let sort: Option<Value> = sort_str.and_then(|s| serde_json::from_str(&s).ok());
        let cols_str: Option<String> = row.get("columns").ok();
        let columns: Option<Value> = cols_str.and_then(|s| serde_json::from_str(&s).ok());
        Ok(SavedViewOut {
            id: row.get("id")?,
            module: row.get("module")?,
            slug: row.get("slug")?,
            display_name: row.get("display_name")?,
            icon: row.get("icon").ok(),
            filters,
            sort,
            columns,
            is_factory: row.get::<_, Option<i64>>("is_factory")?.unwrap_or(0) == 1,
            display_order: row.get("display_order")?,
            created_at: row.get("created_at")?,
        })
    })?;
    Ok(rows.filter_map(|r| r.ok()).collect())
}

// ─── App entry ───────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            list_families,
            get_family,
            get_decision,
            list_decisions,
            get_photo_actions,
            set_decision_status,
            set_final_verified,
            set_family_published,
            set_family_featured,
            set_family_archived,
            set_family_variant,
            set_primary_modelo_idx,
            set_modelo_sold_out,
            set_modelo_field,
            update_gallery_order,
            remove_modelo_photos,
            invoke_watermark,
            python_ping,
            delete_sku,
            edit_modelo_type,
            move_modelo,
            delete_family,
            backfill_meta,
            invalidate_cache,
            batch_clean_family,
            open_msi_folder,
            commit_and_push,
            git_status,
            erp_health,
            // Comercial R1
            comercial_list_events,
            comercial_set_event_status,
            comercial_get_order,
            comercial_mark_order_shipped,
            comercial_list_sales_in_range,
            comercial_list_leads_in_range,
            comercial_list_ad_spend_in_range,
            comercial_insert_event,
            // Comercial R2
            comercial_sync_manychat,
            comercial_list_leads,
            comercial_list_conversations,
            comercial_list_customers,
            comercial_get_meta_sync,
            comercial_get_conversation_messages,
            // Comercial R4
            comercial_get_customer_profile,
            comercial_create_customer,
            comercial_update_customer_traits,
            comercial_set_customer_blocked,
            comercial_update_customer_source,
            comercial_create_manual_order,
            // Comercial R5
            comercial_sync_meta_ads,
            comercial_list_campaigns,
            comercial_get_campaign_detail,
            comercial_get_funnel_awareness_real,
            comercial_generate_coupon,
            // Comercial R6
            comercial_backfill_sales_attribution,
            comercial_get_sale_attribution,
            // Comercial R7
            comercial_get_conversation_meta,
            comercial_attribute_sale,
            // Comercial R9
            comercial_import_orders_from_worker,
            comercial_list_sales,
            // Comercial R10
            comercial_search_customers,
            comercial_update_sale,
            // Comercial R11
            comercial_replace_sale_items,
            // Importaciones R1
            cmd_list_imports,
            cmd_get_import,
            cmd_get_import_items,
            cmd_get_import_pulso,
            cmd_close_import_proportional,
            // Importaciones R1.5
            cmd_create_import,
            cmd_register_arrival,
            cmd_update_import,
            cmd_cancel_import,
            cmd_export_imports_csv,
            // Importaciones R2 (Wishlist + Promote-to-batch + state machine)
            cmd_list_wishlist,
            cmd_create_wishlist_item,
            cmd_update_wishlist_item,
            cmd_cancel_wishlist_item,
            cmd_promote_wishlist_to_batch,
            cmd_mark_in_transit,
            // Importaciones R4 (Free units ledger)
            cmd_list_free_units,
            cmd_assign_free_unit,
            cmd_unassign_free_unit,
            // Finanzas R1
            cmd_compute_profit_snapshot,
            cmd_get_home_snapshot,
            cmd_create_expense,
            cmd_list_expenses,
            cmd_delete_expense,
            cmd_update_expense,
            cmd_recent_expenses,
            cmd_set_cash_balance,
            // Admin Web R7 (T3.1 + T3.5)
            get_admin_web_kpis,
            get_module_stats,
            list_inbox_events,
            dismiss_event,
            resolve_event,
            detect_events_now,
            // Admin Web R7 (T4.3)
            list_published,
            toggle_dirty_flag,
            archive_jersey,
            revive_archived,
            promote_to_stock,
            promote_to_mystery,
            // Admin Web R7 (T5.1 + T5.2) — Tags + Assignment
            list_tag_types,
            list_tags,
            create_tag,
            update_tag,
            soft_delete_tag,
            list_jersey_tags,
            list_jerseys_by_tag,
            validate_tag_assignment,
            assign_tag,
            remove_tag,
            // Admin Web R7 (T6.1 + T6.4 + T6.6) — Universo + bulk + saved views
            list_universo,
            bulk_action,
            list_saved_views,
        ])
        .run(tauri::generate_context!())
        .expect("error while running El Club ERP");
}

#[cfg(test)]
mod imp_r15_helper_tests {
    use super::*;

    #[test]
    fn test_valid_import_id_format() {
        assert!(is_valid_import_id("IMP-2026-04-28"));
        assert!(is_valid_import_id("IMP-2025-12-31"));
        assert!(is_valid_import_id("IMP-2026-01-01"));
    }

    #[test]
    fn test_invalid_import_id_format() {
        assert!(!is_valid_import_id(""));
        assert!(!is_valid_import_id("IMP-2026-04-7"));     // single digit day
        assert!(!is_valid_import_id("imp-2026-04-28"));   // lowercase
        assert!(!is_valid_import_id("IMP-2026-13-01"));   // month 13 invalid
        assert!(!is_valid_import_id("IMP-2026-02-30"));   // feb 30 invalid
        assert!(!is_valid_import_id("IMP-2026-04-28-001")); // suffix
        assert!(!is_valid_import_id("IMP-202X-04-28"));   // letter in year
        assert!(!is_valid_import_id("IMP_2026_04_28"));   // underscores
    }

    #[test]
    fn test_csv_escape_plain() {
        assert_eq!(csv_escape("hello"), "hello");
        assert_eq!(csv_escape(""), "");
    }

    #[test]
    fn test_csv_escape_with_comma() {
        assert_eq!(csv_escape("a,b,c"), "\"a,b,c\"");
    }

    #[test]
    fn test_csv_escape_with_quote() {
        assert_eq!(csv_escape("say \"hi\""), "\"say \"\"hi\"\"\"");
    }

    #[test]
    fn test_csv_escape_with_newline() {
        assert_eq!(csv_escape("line1\nline2"), "\"line1\nline2\"");
        assert_eq!(csv_escape("crlf\r\n"), "\"crlf\r\n\"");
    }
}

#[cfg(test)]
mod imp_r2_helper_tests {
    use super::*;
    use std::sync::Mutex;

    // Race-fix: ELCLUB_CATALOG_PATH is process-global. Without serialization,
    // parallel test threads pollute each other's env (e.g., the missing-file
    // test sets a bad path and the known/unknown tests then fail intermittently).
    // ENV_LOCK serializes any test that mutates this env var.
    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn fixture_path() -> std::path::PathBuf {
        let mut p = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
        p.push("tests/fixtures/catalog_minimal.json");
        p
    }

    #[test]
    fn test_catalog_family_exists_known() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|p| p.into_inner());
        std::env::set_var("ELCLUB_CATALOG_PATH", fixture_path());
        assert!(catalog_family_exists("ARG-2026-L-FS").unwrap());
        assert!(catalog_family_exists("FRA-2026-L-FS").unwrap());
    }

    #[test]
    fn test_catalog_family_exists_unknown() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|p| p.into_inner());
        std::env::set_var("ELCLUB_CATALOG_PATH", fixture_path());
        assert!(!catalog_family_exists("FAKE-XXXX-X-XX").unwrap());
        assert!(!catalog_family_exists("").unwrap());
    }

    #[test]
    fn test_catalog_family_exists_missing_file() {
        let _guard = ENV_LOCK.lock().unwrap_or_else(|p| p.into_inner());
        std::env::set_var("ELCLUB_CATALOG_PATH", "/nonexistent/path.json");
        let result = catalog_family_exists("ARG-2026-L-FS");
        assert!(result.is_err());
        assert!(format!("{:?}", result.unwrap_err()).contains("not found"));
    }
}

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

#[tauri::command]
async fn cmd_close_import_proportional(
    _app: tauri::AppHandle,
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
    app: tauri::AppHandle,
    expense_id: i64,
    input: ExpenseInput,
) -> Result<()> {
    cmd_delete_expense(app.clone(), expense_id).await?;
    cmd_create_expense(app, input).await?;
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
            // Finanzas R1
            cmd_compute_profit_snapshot,
            cmd_get_home_snapshot,
            cmd_create_expense,
            cmd_list_expenses,
            cmd_delete_expense,
            cmd_update_expense,
            cmd_recent_expenses,
            cmd_set_cash_balance,
        ])
        .run(tauri::generate_context!())
        .expect("error while running El Club ERP");
}

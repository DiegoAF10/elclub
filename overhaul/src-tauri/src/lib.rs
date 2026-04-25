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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);
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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);
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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);
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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);
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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);
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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);

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
    write_catalog_atomic(&catalog)?;
    invalidate_catalog(&state);
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

    let erp_dir = erp_scripts_dir();
    let script = erp_dir.join("scripts").join("erp_rust_bridge.py");
    if !script.exists() {
        return Err(ErpError::Other(format!(
            "Python bridge no encontrado en {:?}",
            script
        )));
    }

    let mut child = Command::new(python_exe())
        .arg(script.as_os_str())
        .current_dir(&erp_dir)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
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
        ])
        .run(tauri::generate_context!())
        .expect("error while running El Club ERP");
}

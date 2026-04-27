// overhaul/src/lib/data/manychatSync.ts
import { adapter } from '$lib/adapter';

const SOURCE = 'manychat';
const WORKER_BASE = 'https://ventus-backoffice.ventusgt.workers.dev';

// IMPORTANT: hardcoded for R2-combo. R6 polish: load from a config file.
// This is the DASHBOARD_KEY of ventus-backoffice (NOT el-club's worker).
// Verified value as of 2026-04-26.
const DASHBOARD_KEY = 'ventus-dash-2026-secreto';

export interface SyncResult {
  ok: boolean;
  leadsUpserted: number;
  conversationsUpserted: number;
  lastSyncAt: string;
  error?: string;
}

/**
 * Hace UN sync inmediato: lee el last_sync_at de meta_sync, llama al worker desde ese punto,
 * upsertea leads + conversations, actualiza meta_sync.
 */
export async function runSync(): Promise<SyncResult> {
  let since: string | null = null;
  try {
    const meta = await adapter.getMetaSync(SOURCE);
    since = meta.lastSyncAt;
  } catch (e) {
    console.warn('[manychat-sync] failed to read meta_sync, doing full backfill', e);
  }

  try {
    const result = await adapter.syncManychatData({
      since,
      workerBase: WORKER_BASE,
      dashboardKey: DASHBOARD_KEY,
    });
    return result;
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e);
    return {
      ok: false,
      leadsUpserted: 0,
      conversationsUpserted: 0,
      lastSyncAt: since ?? '',
      error: err,
    };
  }
}

/**
 * Inicia el loop de sync c/1h. Retorna función para detener el loop.
 * El sync corre INMEDIATAMENTE en mount, luego cada hora.
 */
export function startSyncLoop(onResult?: (result: SyncResult) => void): () => void {
  async function runOnce() {
    const r = await runSync();
    if (onResult) onResult(r);
    if (!r.ok) console.warn('[manychat-sync] failed:', r.error);
  }
  void runOnce();
  const interval = setInterval(runOnce, 60 * 60 * 1000);
  return () => clearInterval(interval);
}

export const SYNC_CONSTANTS = { WORKER_BASE, DASHBOARD_KEY, SOURCE };

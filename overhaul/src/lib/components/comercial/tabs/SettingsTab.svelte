<script lang="ts">
  import { adapter } from '$lib/adapter';
  import { runSync, type SyncResult } from '$lib/data/manychatSync';
  import type { MetaSyncStatus, MetaSyncResult } from '$lib/data/comercial';
  import { RefreshCw, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-svelte';

  let metaSync = $state<MetaSyncStatus | null>(null);
  let syncing = $state(false);
  let lastResult = $state<SyncResult | null>(null);

  let metaSyncing = $state(false);
  let metaResult = $state<MetaSyncResult | null>(null);
  let metaError = $state<string | null>(null);

  async function syncMetaAds() {
    if (metaSyncing) return;
    metaSyncing = true;
    metaError = null;
    try {
      const result = await adapter.syncMetaAds({ days: 30 });
      metaResult = result;
      if (!result.ok) metaError = result.errors.join('; ') || 'Error desconocido';
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e);
    } finally {
      metaSyncing = false;
    }
  }

  async function loadMeta() {
    try {
      metaSync = await adapter.getMetaSync('manychat');
    } catch (e) {
      console.warn('[settings] meta load failed', e);
    }
  }

  async function handleSync() {
    if (syncing) return;
    syncing = true;
    try {
      lastResult = await runSync();
      await loadMeta();
    } finally {
      syncing = false;
    }
  }

  $effect(() => {
    void loadMeta();
  });

  function fmtDate(iso: string | null): string {
    if (!iso) return 'nunca';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }
</script>

<div class="px-6 py-4">
  <h1 class="mb-4 text-[18px] font-semibold">Settings</h1>

  <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4">
    <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">ManyChat sync</div>

    <div class="mb-3 space-y-1 text-[11.5px]">
      <div class="flex justify-between">
        <span class="text-[var(--color-text-tertiary)]">Última sync</span>
        <span class="text-mono">{fmtDate(metaSync?.lastSyncAt ?? null)}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-[var(--color-text-tertiary)]">Status</span>
        <span class="text-mono">
          {#if metaSync?.lastStatus === 'ok'}
            <span style="color: var(--color-accent);">● OK</span>
          {:else if metaSync?.lastStatus === 'error'}
            <span style="color: var(--color-danger);">● ERROR</span>
          {:else}
            <span style="color: var(--color-text-muted);">—</span>
          {/if}
        </span>
      </div>
      {#if metaSync?.lastError}
        <div class="text-[10.5px] text-[var(--color-danger)]">⚠ {metaSync.lastError}</div>
      {/if}
    </div>

    <button
      type="button"
      onclick={handleSync}
      disabled={syncing}
      class="flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
    >
      {#if syncing}
        <RefreshCw size={12} strokeWidth={2} class="animate-spin" /> Sincronizando…
      {:else}
        <RefreshCw size={12} strokeWidth={2} /> Sincronizar ahora
      {/if}
    </button>

    {#if lastResult}
      <div class="mt-3 text-[10.5px]">
        {#if lastResult.ok}
          <span style="color: var(--color-accent);">✓ {lastResult.leadsUpserted} leads · {lastResult.conversationsUpserted} conversations actualizadas</span>
        {:else}
          <span style="color: var(--color-danger);">⚠ Falló: {lastResult.error}</span>
        {/if}
      </div>
    {/if}
  </div>

  <div class="mt-6 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-4">
    <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Meta Ads</div>
    <div class="flex items-center justify-between gap-3">
      <div class="flex-1">
        <div class="text-[12px] font-medium">Sincronizar Meta Ads</div>
        <div class="text-[10px] text-[var(--color-text-tertiary)]">Pull insights últimos 30d → campaigns_snapshot</div>
        {#if metaResult}
          <div class="mt-1 text-[10px]" style="color: {metaResult.ok ? 'var(--color-accent)' : 'var(--color-danger)'};">
            ✓ {metaResult.campaignsSynced} campañas · {new Date(metaResult.syncedAt).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' })}
            {#if metaResult.errors.length > 0}
              <span style="color: var(--color-warning);">· {metaResult.errors.length} errores</span>
            {/if}
          </div>
        {/if}
        {#if metaError}
          <div class="mt-1 text-[10px]" style="color: var(--color-danger);">⚠ {metaError}</div>
        {/if}
      </div>
      <button
        type="button"
        onclick={syncMetaAds}
        disabled={metaSyncing}
        class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if metaSyncing}
          <Loader2 size={12} class="animate-spin" /> Sincronizando…
        {:else}
          <RefreshCw size={12} strokeWidth={2} /> Sincronizar
        {/if}
      </button>
    </div>
  </div>

  <div class="mt-4 text-[10.5px] text-[var(--color-text-muted)]">
    Más settings (umbrales, notifications, integrations) en R6.
  </div>
</div>

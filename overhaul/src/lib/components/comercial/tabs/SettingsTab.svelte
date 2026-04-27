<script lang="ts">
  import { adapter } from '$lib/adapter';
  import { runSync, type SyncResult } from '$lib/data/manychatSync';
  import type { MetaSyncStatus } from '$lib/data/comercial';
  import { RefreshCw, CheckCircle2, AlertTriangle } from 'lucide-svelte';

  let metaSync = $state<MetaSyncStatus | null>(null);
  let syncing = $state(false);
  let lastResult = $state<SyncResult | null>(null);

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

  <div class="mt-4 text-[10.5px] text-[var(--color-text-muted)]">
    Más settings (umbrales, notifications, integrations) en R6.
  </div>
</div>

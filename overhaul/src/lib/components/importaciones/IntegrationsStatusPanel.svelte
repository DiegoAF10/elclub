<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { IntegrationsStatus } from '$lib/adapter/types';

  let status = $state<IntegrationsStatus | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    (async () => {
      try {
        status = await adapter.getIntegrationsStatus();
      } catch (e: any) {
        error = e?.message ?? String(e);
      } finally {
        loading = false;
      }
    })();
  });
</script>

{#if loading}
  <div class="skeleton">Cargando integraciones…</div>
{:else if error}
  <div class="err">⚠️ {error}</div>
{:else if status}
  <div class="rows">
    {#each status.integrations as int}
      <div class="int-row">
        <span class="pill" class:active={int.status === 'active'}>● {int.status.toUpperCase()}</span>
        <div class="body">
          <div class="name">{int.name}</div>
          {#if int.lastReadAt}<div class="meta">Last read: {int.lastReadAt}</div>{/if}
          {#if int.note}<div class="note">{int.note}</div>{/if}
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .skeleton { padding: 12px; color: var(--text-3, #777); font-style: italic; }
  .err { color: var(--alert, #f43f5e); padding: 8px; }
  .rows { display: flex; flex-direction: column; gap: 10px; }
  .int-row {
    display: flex; gap: 12px; align-items: flex-start;
    padding: 10px; background: var(--surface-2, #16161b);
    border-radius: 3px; border: 1px solid var(--border, #22222a);
  }
  .pill {
    font-size: 10px; padding: 2px 8px; border-radius: 10px;
    background: var(--surface-3, #1e1e24); color: var(--text-3, #777);
    text-transform: uppercase; letter-spacing: 0.06em; flex-shrink: 0;
  }
  .pill.active { color: var(--terminal, #4ade80); }
  .name { font-weight: 600; font-size: 13px; }
  .meta, .note { font-size: 11px; color: var(--text-3, #777); margin-top: 2px; }
  .meta { font-family: 'JetBrains Mono', monospace; }
</style>

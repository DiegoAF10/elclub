<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { MigrationLog } from '$lib/adapter/types';

  let log = $state<MigrationLog | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  $effect(() => {
    (async () => {
      try {
        log = await adapter.getMigrationLog();
      } catch (e: any) {
        error = e?.message ?? String(e);
      } finally {
        loading = false;
      }
    })();
  });
</script>

{#if loading}
  <div class="skeleton">Cargando migration log…</div>
{:else if error}
  <div class="err">⚠️ {error}</div>
{:else if log}
  <table class="log-table">
    <tbody>
      <tr><td>Última migración (proxy)</td><td class="num">{log.lastMigrationRunAt ?? '—'}</td></tr>
      <tr><td>Imports</td><td class="num">{log.importsCount}</td></tr>
      <tr><td>Sale items linked</td><td class="num">{log.saleItemsLinked}</td></tr>
      <tr><td>Jerseys linked</td><td class="num">{log.jerseysLinked}</td></tr>
      <tr><td>Wishlist rows</td><td class="num">{log.wishlistCount}</td></tr>
      <tr><td>Free units rows</td><td class="num">{log.freeUnitsCount}</td></tr>
    </tbody>
  </table>
  <button class="resync-btn" disabled title="Deshabilitado en v0.4.0 · v0.5 future con merge logic">
    Re-sync ahora (disabled)
  </button>
  {#if log.importsCount === 0}
    <p class="empty">Sin migraciones todavía. R1 ya migró schema initial · counts crecen al usar el módulo.</p>
  {/if}
{/if}

<style>
  .skeleton { padding: 12px; color: var(--text-3, #777); font-style: italic; }
  .err { color: var(--alert, #f43f5e); padding: 8px; }
  .log-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .log-table td { padding: 6px 8px; border-bottom: 1px solid var(--border, #22222a); }
  .log-table td:first-child { color: var(--text-2, #aaa); text-transform: uppercase; letter-spacing: 0.05em; font-size: 11px; }
  .num { font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; text-align: right; }
  .resync-btn {
    margin-top: 12px; padding: 6px 12px; background: var(--surface-2, #16161b);
    border: 1px solid var(--border, #22222a); color: var(--text-3, #777);
    border-radius: 3px; cursor: not-allowed;
  }
  .empty { margin-top: 8px; font-size: 11px; color: var(--text-3, #777); font-style: italic; }
</style>

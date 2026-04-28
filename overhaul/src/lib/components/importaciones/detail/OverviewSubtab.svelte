<script lang="ts">
  import type { Import, ImportItem } from '$lib/data/importaciones';

  interface Props {
    imp: Import;
    items: ImportItem[];
  }

  let { imp, items }: Props = $props();

  let leadDays = $derived(computeLeadDays(imp));
  let totalLandedEst = $derived(imp.total_landed_gtq ?? estimateLanded(imp));
  let landedPerUnit = $derived(imp.unit_cost ?? estimatePerUnit(imp));

  function computeLeadDays(i: Import): number | null {
    if (!i.paid_at) return null;
    const paid = new Date(i.paid_at);
    const end = i.arrived_at ? new Date(i.arrived_at) : new Date();
    return Math.round((end.getTime() - paid.getTime()) / (1000 * 60 * 60 * 24));
  }

  function estimateLanded(i: Import): number | null {
    if (!i.bruto_usd || !i.fx) return null;
    return i.bruto_usd * i.fx + (i.shipping_gtq ?? 0);
  }

  function estimatePerUnit(i: Import): number | null {
    const total = estimateLanded(i);
    if (!total || !i.n_units) return null;
    return total / i.n_units;
  }

  function fmtUsd(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `$${n.toFixed(2)}`;
  }

  function fmtQ(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return `Q${Math.round(n).toLocaleString('es-GT')}`;
  }
</script>

<div class="p-6 overflow-y-auto">
  <!-- Stats strip 6 KPIs -->
  <div class="grid grid-cols-6 gap-px bg-[var(--color-border)] border border-[var(--color-border)] rounded-[4px] overflow-hidden mb-6">
    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Bruto USD</div>
      <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-text-primary)]">{fmtUsd(imp.bruto_usd)}</div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">PayPal · 4.4% incl.</div>
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">DHL door-to-door</div>
      {#if imp.shipping_gtq !== null}
        <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-text-primary)]">{fmtQ(imp.shipping_gtq)}</div>
        <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">arrived ✓</div>
      {:else}
        <div class="text-mono text-[16px] font-bold text-[var(--color-warning)]">— pendiente</div>
        <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">cuando arrive</div>
      {/if}
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Días desde paid</div>
      {#if leadDays !== null}
        <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-accent)]">{leadDays}d</div>
        <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">{imp.status === 'closed' ? 'lead time real' : 'en pipeline'}</div>
      {:else}
        <div class="text-mono text-[16px] font-bold text-[var(--color-text-tertiary)]">—</div>
      {/if}
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Total landed est</div>
      <div class="text-mono text-[16px] font-bold tabular-nums {imp.total_landed_gtq !== null ? 'text-[var(--color-live)]' : 'text-[var(--color-warning)]'}">
        {imp.total_landed_gtq !== null ? fmtQ(imp.total_landed_gtq) : `~${fmtQ(totalLandedEst)}?`}
      </div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">{imp.total_landed_gtq !== null ? 'real · post-close' : 'est · sin DHL real'}</div>
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Units</div>
      <div class="text-mono text-[16px] font-bold tabular-nums text-[var(--color-text-primary)]">{imp.n_units ?? 0}</div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">items linkeados</div>
    </div>

    <div class="bg-[var(--color-surface-1)] p-3.5">
      <div class="text-mono text-[9px] uppercase mb-1 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">Landed / unidad</div>
      <div class="text-mono text-[16px] font-bold tabular-nums {imp.unit_cost !== null ? 'text-[var(--color-live)]' : 'text-[var(--color-warning)]'}">
        {imp.unit_cost !== null ? fmtQ(imp.unit_cost) : `~${fmtQ(landedPerUnit)}`}
      </div>
      <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1">{imp.unit_cost !== null ? 'prorrateo D2=B' : 'estimado pre-cierre'}</div>
    </div>
  </div>

  <!-- Items preview (5 first) -->
  <div class="mb-6">
    <div class="text-mono text-[10.5px] uppercase font-semibold text-[var(--color-text-secondary)] mb-2.5 pb-2 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.08em;">
      ▸ Items del batch · preview <span class="text-[var(--color-text-tertiary)] normal-case">(ver todo en tab Items)</span>
    </div>

    {#if items.length === 0}
      <div class="text-sm text-[var(--color-text-tertiary)] italic py-4 text-center">Sin items linkeados a este batch</div>
    {:else}
      <table class="w-full text-[11.5px] border-collapse">
        <thead>
          <tr>
            <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">SKU</th>
            <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Spec</th>
            <th class="text-left text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Cliente</th>
            <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">USD</th>
            <th class="text-right text-mono text-[9.5px] uppercase text-[var(--color-text-tertiary)] py-2 px-2.5 border-b border-[var(--color-border)]" style="letter-spacing: 0.08em;">Landed Q</th>
          </tr>
        </thead>
        <tbody>
          {#each items.slice(0, 5) as item}
            <tr class="border-b border-[var(--color-surface-2)] hover:bg-[var(--color-surface-1)]">
              <td class="py-1.5 px-2.5 text-mono text-[var(--color-text-primary)]">{item.family_id ?? item.jersey_id ?? '—'}{item.is_free_unit ? ' 🎁' : ''}</td>
              <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">
                {item.size ?? ''} · {item.player_name ?? '—'}{item.player_number ? ` ${item.player_number}` : ''}
              </td>
              <td class="py-1.5 px-2.5 text-[var(--color-text-secondary)]">{item.customer_name ?? '—'}</td>
              <td class="py-1.5 px-2.5 text-right text-mono">{fmtUsd(item.unit_cost_usd)}</td>
              <td class="py-1.5 px-2.5 text-right text-mono text-[var(--color-live)] font-semibold">{fmtQ(item.unit_cost)}</td>
            </tr>
          {/each}
          {#if items.length > 5}
            <tr><td colspan="5" class="text-center py-2 text-[var(--color-text-tertiary)] italic text-xs">+ {items.length - 5} items más · ver tab Items</td></tr>
          {/if}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Timeline (6 stages) -->
  <div class="mb-6">
    <div class="text-mono text-[10.5px] uppercase font-semibold text-[var(--color-text-secondary)] mb-2.5 pb-2 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.08em;">
      ▸ Timeline del batch
    </div>

    <div class="pl-1.5">
      <!-- DRAFT -->
      <div class="flex gap-3 py-2 relative">
        <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
        <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-live)] border-2 border-[var(--color-live)] flex-shrink-0 mt-1.5 z-10"></div>
        <div class="flex-1">
          <div class="flex items-baseline gap-2.5">
            <span class="text-[12.5px] text-[var(--color-text-secondary)] font-semibold">DRAFT creado</span>
            <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">{imp.created_at?.split(' ')[0] ?? '—'}</span>
          </div>
        </div>
      </div>

      <!-- PAID -->
      {#if imp.paid_at}
        <div class="flex gap-3 py-2 relative">
          <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
          <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-live)] border-2 border-[var(--color-live)] flex-shrink-0 mt-1.5 z-10"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] text-[var(--color-text-secondary)] font-semibold">PAID</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">{imp.paid_at}</span>
            </div>
            <div class="text-[11px] text-[var(--color-text-secondary)] mt-0.5">PayPal · {fmtUsd(imp.bruto_usd)}</div>
          </div>
        </div>
      {/if}

      <!-- IN_TRANSIT (active si paid sin arrived) -->
      {#if imp.paid_at && !imp.arrived_at}
        <div class="flex gap-3 py-2 relative">
          <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
          <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-warning)] border-2 border-[var(--color-warning)] flex-shrink-0 mt-1.5 z-10 pulse-live"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] text-[var(--color-text-primary)] font-semibold">IN_TRANSIT</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">esperando DHL</span>
              <span class="text-mono text-[10px] text-[var(--color-warning)] px-1.5 py-0.5 bg-[rgba(245,165,36,0.10)] rounded-[2px]">{leadDays}d desde paid</span>
            </div>
          </div>
        </div>
      {/if}

      <!-- ARRIVED -->
      {#if imp.arrived_at}
        <div class="flex gap-3 py-2 relative">
          <div class="absolute left-[5px] top-[20px] bottom-[-8px] w-px bg-[var(--color-border)]"></div>
          <div class="w-[11px] h-[11px] rounded-full {imp.status === 'closed' ? 'bg-[var(--color-live)] border-2 border-[var(--color-live)]' : 'bg-[var(--color-warning)] border-2 border-[var(--color-warning)] pulse-live'} flex-shrink-0 mt-1.5 z-10"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] {imp.status === 'closed' ? 'text-[var(--color-text-secondary)]' : 'text-[var(--color-text-primary)]'} font-semibold">ARRIVED</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">{imp.arrived_at}</span>
            </div>
          </div>
        </div>
      {/if}

      <!-- CLOSED -->
      {#if imp.status === 'closed'}
        <div class="flex gap-3 py-2 relative">
          <div class="w-[11px] h-[11px] rounded-full bg-[var(--color-live)] border-2 border-[var(--color-live)] flex-shrink-0 mt-1.5 z-10"></div>
          <div class="flex-1">
            <div class="flex items-baseline gap-2.5">
              <span class="text-[12.5px] text-[var(--color-text-secondary)] font-semibold">CLOSED</span>
              <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]">prorrateo aplicado</span>
            </div>
            <div class="text-[11px] text-[var(--color-text-secondary)] mt-0.5">unit_cost {fmtQ(imp.unit_cost)} aplicado a sale_items + jerseys</div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

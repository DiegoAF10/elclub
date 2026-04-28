<script lang="ts">
  import type { Import, ImportItem } from '$lib/data/importaciones';

  interface Props { imp: Import; items: ImportItem[]; }
  let { imp, items }: Props = $props();

  let totalUsd = $derived(items.reduce((s, i) => s + (i.unit_cost_usd ?? 0), 0));
  let payPalFee = $derived(imp.bruto_usd ? imp.bruto_usd * 0.044 : 0);
  let totalLanded = $derived(imp.total_landed_gtq ?? (imp.bruto_usd && imp.fx ? imp.bruto_usd * imp.fx + (imp.shipping_gtq ?? 0) : null));

  function fmtUsd(n: number | null | undefined): string { return n === null || n === undefined ? '—' : `$${n.toFixed(2)} USD`; }
  function fmtQ(n: number | null | undefined): string { return n === null || n === undefined ? '—' : `Q${Math.round(n).toLocaleString('es-GT')}`; }
</script>

<div class="p-6 max-w-[800px]">
  <div class="text-mono text-[10.5px] uppercase font-semibold text-[var(--color-text-secondary)] mb-3 pb-2 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.08em;">
    ▸ Cost flow · cómo se llega al landed cost
  </div>

  <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[4px] p-4">
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">PayPal bruto al supplier</span>
      <span class="text-mono text-[var(--color-text-primary)] tabular-nums">{fmtUsd(imp.bruto_usd)}</span>
    </div>
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">PayPal fee (~4.4% incluido en bruto)</span>
      <span class="text-mono text-[var(--color-text-tertiary)] tabular-nums">~{fmtUsd(payPalFee)}</span>
    </div>
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">DHL door-to-door (shipping + impuestos GT)</span>
      <span class="text-mono tabular-nums {imp.shipping_gtq !== null ? 'text-[var(--color-text-primary)]' : 'text-[var(--color-warning)]'}">
        {imp.shipping_gtq !== null ? fmtQ(imp.shipping_gtq) : '— pendiente'}
      </span>
    </div>
    <div class="flex justify-between py-1.5 text-[12px]">
      <span class="text-[var(--color-text-secondary)]">FX USD → GTQ</span>
      <span class="text-mono text-[var(--color-text-primary)] tabular-nums">× {imp.fx.toFixed(2)}</span>
    </div>

    <div class="flex justify-between pt-2.5 mt-1.5 border-t border-dashed border-[var(--color-border)] text-[12px]">
      <span class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] italic">{fmtUsd(imp.bruto_usd)} × {imp.fx.toFixed(2)} + DHL = total_landed</span>
      <span class="text-mono text-[var(--color-text-primary)] tabular-nums">{fmtUsd(imp.bruto_usd)} × {imp.fx.toFixed(2)} = {fmtQ(imp.bruto_usd ? imp.bruto_usd * imp.fx : null)}</span>
    </div>

    <div class="flex justify-between pt-2.5 mt-1 border-t border-[var(--color-border)] text-[12px]">
      <span class="text-[var(--color-text-primary)] font-semibold">
        Total landed batch <span class="text-mono text-[10px] text-[var(--color-text-tertiary)] font-normal">(D2=B prorrateo proporcional al USD per item)</span>
      </span>
      <span class="text-mono text-[14px] font-bold text-[var(--color-live)] tabular-nums">{fmtQ(totalLanded)}</span>
    </div>
  </div>

  <div class="mt-4 text-mono text-[10.5px] text-[var(--color-text-tertiary)] italic">
    Nota: prorrateo D2=B aplicado al close usa el USD chino per item (de chat WA `11+2=13`). Items con USD null reciben default uniforme = bruto/n_units.
  </div>
</div>

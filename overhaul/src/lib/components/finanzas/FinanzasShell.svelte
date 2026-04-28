<script lang="ts">
  import FinanzasTabs from './FinanzasTabs.svelte';
  import PeriodStrip from './PeriodStrip.svelte';
  import HomeTab from './tabs/HomeTab.svelte';
  import EstadoResultadosTab from './tabs/EstadoResultadosTab.svelte';
  import ProductosTab from './tabs/ProductosTab.svelte';
  import GastosTab from './tabs/GastosTab.svelte';
  import CuentaBusinessTab from './tabs/CuentaBusinessTab.svelte';
  import InterCuentaTab from './tabs/InterCuentaTab.svelte';
  import SettingsTab from './tabs/SettingsTab.svelte';
  import { periodToDateRange } from '$lib/data/finanzasPeriods';
  import type { Period } from '$lib/data/finanzas';

  type TabId = 'home' | 'edr' | 'productos' | 'gastos' | 'cuenta' | 'inter' | 'settings';

  const TAB_KEY = 'fin.tab';
  const PERIOD_KEY = 'fin.period';

  function readStored<T extends string>(key: string, fallback: T): T {
    if (typeof localStorage === 'undefined') return fallback;
    const v = localStorage.getItem(key);
    return (v as T) ?? fallback;
  }

  let activeTab = $state<TabId>(readStored<TabId>(TAB_KEY, 'home'));
  let period = $state<Period>(readStored<Period>(PERIOD_KEY, 'month'));

  let periodRange = $derived(periodToDateRange(period));

  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(TAB_KEY, activeTab);
      localStorage.setItem(PERIOD_KEY, period);
    }
  });
</script>

<div class="flex h-full flex-col bg-[var(--color-bg)]">
  <div class="flex items-center gap-4 border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6 py-3">
    <div>
      <div class="text-[18px] font-semibold text-[var(--color-text-primary)]">Finanzas</div>
      <div class="text-mono text-[10.5px] text-[var(--color-text-tertiary)]" style="letter-spacing: 0.05em;">
        salud financiera de El Club · ingresos ← Comercial · COGS ← Importaciones · gastos local
      </div>
    </div>
    <div class="ml-auto flex gap-2">
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-[11px] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]" disabled>⇣ Export CSV</button>
      <button class="text-mono rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[11px] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)]" disabled>📋 Estado Resultados</button>
      <button class="text-mono rounded-[3px] bg-[var(--color-accent)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-bg)] hover:bg-[var(--color-accent-hover)]" onclick={() => activeTab = 'gastos'}>+ Nuevo gasto</button>
    </div>
  </div>

  <FinanzasTabs bind:activeTab />
  <PeriodStrip bind:period {periodRange} />

  <div class="flex flex-1 min-h-0">
    {#if activeTab === 'home'}
      <HomeTab {periodRange} />
    {:else if activeTab === 'edr'}
      <EstadoResultadosTab />
    {:else if activeTab === 'productos'}
      <ProductosTab />
    {:else if activeTab === 'gastos'}
      <GastosTab {periodRange} />
    {:else if activeTab === 'cuenta'}
      <CuentaBusinessTab />
    {:else if activeTab === 'inter'}
      <InterCuentaTab />
    {:else if activeTab === 'settings'}
      <SettingsTab />
    {/if}
  </div>
</div>

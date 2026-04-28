<script lang="ts">
  type TabId = 'home' | 'edr' | 'productos' | 'gastos' | 'cuenta' | 'inter' | 'settings';

  let { activeTab = $bindable<TabId>() }: { activeTab: TabId } = $props();

  const TABS: Array<{ id: TabId; label: string; icon: string }> = [
    { id: 'home',      label: 'Home',                icon: '🏠' },
    { id: 'edr',       label: 'Estado de Resultados', icon: '📊' },
    { id: 'productos', label: 'Productos',           icon: '🏷' },
    { id: 'gastos',    label: 'Gastos',              icon: '💸' },
    { id: 'cuenta',    label: 'Cuenta business',     icon: '🏦' },
    { id: 'inter',     label: 'Inter-cuenta',        icon: '🔄' },
    { id: 'settings',  label: 'Settings',            icon: '⚙' },
  ];
</script>

<div class="flex border-b border-[var(--color-border)] bg-[var(--color-surface-1)] px-6">
  {#each TABS as tab (tab.id)}
    {@const isLast = tab.id === 'settings'}
    {@const isActive = activeTab === tab.id}
    <button
      type="button"
      class="text-mono inline-flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-[11px] uppercase transition-colors"
      class:ml-auto={isLast}
      class:border-transparent={!isActive}
      class:text-[var(--color-text-tertiary)]={!isActive && isLast}
      class:text-[var(--color-text-secondary)]={!isActive && !isLast}
      class:!text-[var(--color-accent)]={isActive}
      class:!border-[var(--color-accent)]={isActive}
      style="letter-spacing: 0.05em;"
      onclick={() => activeTab = tab.id}
    >
      <span aria-hidden="true">{tab.icon}</span>
      <span>{tab.label}</span>
    </button>
  {/each}
</div>

<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { WishlistItem } from '$lib/data/wishlist';
  import type { ModeloOption } from '$lib/adapter/types';

  interface Props {
    open: boolean;
    mode: 'create' | 'edit';
    item: WishlistItem | null;     // null when mode='create'
    onClose: () => void;
    onSaved: (item: WishlistItem) => void;
  }

  let { open, mode, item, onClose, onSaved }: Props = $props();

  // Form state — initialized from item on open in edit mode
  let familyId = $state('');           // stores modelo SKU (e.g. "ARG-2026-L-FS")
  let jerseyId = $state('');
  let size = $state('');
  let playerName = $state('');
  let playerNumber = $state<number | null>(null);
  let patch = $state('');
  let version = $state('');            // auto-populated from modelo (type/sleeve)
  let customerId = $state('');
  let expectedUsd = $state<number | null>(null);
  let notes = $state('');

  // Cascade picker state
  let modelos = $state<ModeloOption[]>([]);
  let catalogLoading = $state(false);
  let catalogError = $state<string | null>(null);
  let selectedTipo = $state('');           // "UEFA"/"Conmebol"/"CAF"/"Concacaf"/"AFC"/"Clubes"
  let selectedTeam = $state('');
  let teamSearch = $state('');
  let manualMode = $state(false);          // edit mode fallback when modelo not found in catalog

  let submitting = $state(false);
  let errorMsg = $state<string | null>(null);

  const TIPO_OPTIONS = ['UEFA', 'Conmebol', 'CAF', 'Concacaf', 'AFC', 'Clubes'];

  // Group key for a modelo: confederation or "Clubes" if null/empty
  function tipoOf(m: ModeloOption): string {
    return m.confederation && m.confederation.length > 0 ? m.confederation : 'Clubes';
  }

  // Load catalog on open (create mode + edit fallback for reverse-lookup)
  $effect(() => {
    if (open && modelos.length === 0 && !catalogLoading && !catalogError) {
      void loadCatalog();
    }
  });

  async function loadCatalog() {
    catalogLoading = true;
    catalogError = null;
    try {
      modelos = await adapter.listCatalogModelos();
    } catch (e) {
      catalogError = e instanceof Error ? e.message : String(e);
    } finally {
      catalogLoading = false;
    }
  }

  // Self-clean on close + initialize from item on open (R1.5 modal pattern)
  $effect(() => {
    if (!open) {
      reset();
    } else if (mode === 'edit' && item) {
      familyId = item.family_id;
      jerseyId = item.jersey_id ?? '';
      size = item.size ?? '';
      playerName = item.player_name ?? '';
      playerNumber = item.player_number;
      patch = item.patch ?? '';
      version = item.version ?? '';
      customerId = item.customer_id ?? '';
      expectedUsd = item.expected_usd;
      notes = item.notes ?? '';
    }
  });

  // Reverse-lookup: when catalog loads in edit mode, try to find the modelo by SKU
  $effect(() => {
    if (mode === 'edit' && item && modelos.length > 0 && !selectedTeam) {
      const found = modelos.find((m) => m.sku === item.family_id);
      if (found) {
        selectedTipo = tipoOf(found);
        selectedTeam = found.team;
        manualMode = false;
      } else {
        // Legacy data: SKU not found in current catalog
        manualMode = true;
      }
    }
  });

  // Derived: unique tipos available (max 6 — plus respects only those that have entries)
  let availableTipos = $derived.by(() => {
    const set = new Set<string>();
    for (const m of modelos) set.add(tipoOf(m));
    return TIPO_OPTIONS.filter((t) => set.has(t));
  });

  // Derived: teams filtered by tipo, alphabetical, with optional search filter
  let teamsForTipo = $derived.by(() => {
    if (!selectedTipo) return [];
    const teams = new Set<string>();
    for (const m of modelos) {
      if (tipoOf(m) === selectedTipo) teams.add(m.team);
    }
    const arr = Array.from(teams).sort((a, b) => a.localeCompare(b, 'es'));
    if (!teamSearch.trim()) return arr;
    const q = teamSearch.trim().toLowerCase();
    return arr.filter((t) => t.toLowerCase().includes(q));
  });

  // Derived: modelos for selected team, sorted (season DESC, variant ASC, type, sleeve)
  let modelosForTeam = $derived.by(() => {
    if (!selectedTeam) return [];
    const list = modelos.filter((m) => m.team === selectedTeam);
    return list.sort((a, b) => {
      const sa = a.season ?? '';
      const sb = b.season ?? '';
      if (sa !== sb) return sb.localeCompare(sa);             // season DESC
      const va = a.variant ?? '';
      const vb = b.variant ?? '';
      if (va !== vb) return va.localeCompare(vb);             // variant ASC
      const ta = a.modeloType ?? '';
      const tb = b.modeloType ?? '';
      if (ta !== tb) return ta.localeCompare(tb);             // type ASC
      const sla = a.sleeve ?? '';
      const slb = b.sleeve ?? '';
      return sla.localeCompare(slb);                          // sleeve ASC
    });
  });

  // Derived: the modelo currently selected (matches familyId === sku)
  let selectedModelo = $derived(
    familyId ? (modelos.find((m) => m.sku === familyId) ?? null) : null
  );

  function formatModeloLabel(m: ModeloOption): string {
    const season = m.season ?? '?';
    const variant = m.variant ?? '?';
    const type = m.modeloType ?? '?';
    const sleeve = m.sleeve ? `/${m.sleeve}` : '';
    return `${m.sku} · ${season} ${variant} · ${type}${sleeve}`;
  }

  function formatModeloVersion(m: ModeloOption): string {
    const type = m.modeloType ?? '';
    const sleeve = m.sleeve ? `/${m.sleeve}` : '';
    return `${type}${sleeve}`;
  }

  function onTipoChange() {
    selectedTeam = '';
    teamSearch = '';
    familyId = '';
    version = '';
  }

  function onTeamChange() {
    familyId = '';
    version = '';
  }

  function onModeloChange(sku: string) {
    const m = modelos.find((x) => x.sku === sku);
    if (m) {
      familyId = m.sku;
      version = formatModeloVersion(m);
    } else {
      familyId = '';
      version = '';
    }
  }

  let canSubmit = $derived(
    familyId.trim().length > 0 &&
    (expectedUsd === null || expectedUsd >= 0) &&
    !submitting
  );

  async function handleSubmit() {
    if (!canSubmit) {
      if (familyId.trim().length === 0) errorMsg = 'Seleccioná un modelo';
      return;
    }
    submitting = true;
    errorMsg = null;
    try {
      let saved: WishlistItem;
      if (mode === 'create') {
        saved = await adapter.createWishlistItem({
          familyId: familyId.trim(),
          jerseyId: jerseyId.trim() || undefined,
          size: size.trim() || undefined,
          playerName: playerName.trim() || undefined,
          playerNumber: playerNumber ?? undefined,
          patch: patch.trim() || undefined,
          version: (version.trim() || undefined) as any,
          customerId: customerId.trim() || undefined,
          expectedUsd: expectedUsd ?? undefined,
          notes: notes.trim() || undefined,
        });
      } else {
        if (!item) throw new Error('edit mode requires item prop');
        saved = await adapter.updateWishlistItem({
          wishlistItemId: item.wishlist_item_id,
          size: size.trim() || undefined,
          playerName: playerName.trim() || undefined,
          playerNumber: playerNumber ?? undefined,
          patch: patch.trim() || undefined,
          version: (version.trim() || undefined) as any,
          customerId: customerId.trim() || undefined,
          expectedUsd: expectedUsd ?? undefined,
          notes: notes.trim() || undefined,
        });
      }
      onSaved(saved);
      onClose();
    } catch (e) {
      errorMsg = e instanceof Error ? e.message : String(e);
    } finally {
      submitting = false;
    }
  }

  function reset() {
    familyId = '';
    jerseyId = '';
    size = '';
    playerName = '';
    playerNumber = null;
    patch = '';
    version = '';
    customerId = '';
    expectedUsd = null;
    notes = '';
    selectedTipo = '';
    selectedTeam = '';
    teamSearch = '';
    manualMode = false;
    errorMsg = null;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && !submitting) onClose();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    onclick={(e) => { if (e.target === e.currentTarget && !submitting) onClose(); }}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 w-[520px] max-h-[90vh] overflow-y-auto shadow-2xl">
      <h2 class="text-[16px] font-semibold text-[var(--color-text-primary)] mb-1">
        {mode === 'create' ? '+ Nuevo wishlist item' : 'Editar wishlist item'}
      </h2>
      <p class="text-mono text-[10.5px] text-[var(--color-text-tertiary)] mb-4" style="letter-spacing: 0.05em;">
        D7=B · modelo SKU debe existir en catalog.json
      </p>

      <form onsubmit={(e) => { e.preventDefault(); handleSubmit(); }} class="space-y-3">
        <!-- ─── Cascade: Tipo → Equipo → Modelo ─── -->
        {#if mode === 'edit' && manualMode}
          <!-- Edit-mode legacy fallback: modelo not in current catalog -->
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Family ID (SKU) — modelo desconocido · entrar manualmente
            </label>
            <input
              type="text"
              bind:value={familyId}
              disabled
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-warning)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]"
            />
            <p class="text-[10.5px] text-[var(--color-warning)] mt-1">⚠️ SKU no encontrado en catalog · legacy data · family_id no editable</p>
          </div>
        {:else if catalogLoading}
          <div class="text-mono text-[11px] text-[var(--color-text-tertiary)] px-3 py-4 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-center">
            Cargando catálogo…
          </div>
        {:else if catalogError}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ No se pudo cargar el catálogo · {catalogError}
            <button type="button" onclick={() => loadCatalog()} class="text-mono text-[10.5px] underline ml-2 hover:text-[var(--color-warning)]">
              reintentar
            </button>
          </div>
        {:else}
          <!-- Tipo de equipo -->
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
              Tipo de equipo *
            </label>
            <select
              bind:value={selectedTipo}
              onchange={onTipoChange}
              disabled={mode === 'edit' || submitting}
              class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]"
            >
              <option value="">— elegí tipo —</option>
              {#each availableTipos as tipo}
                <option value={tipo}>
                  {tipo === 'UEFA' || tipo === 'Conmebol' || tipo === 'CAF' || tipo === 'Concacaf' || tipo === 'AFC' ? `Selecciones ${tipo}` : tipo}
                </option>
              {/each}
            </select>
          </div>

          <!-- Equipo -->
          {#if selectedTipo}
            <div>
              <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
                Equipo * <span class="text-[var(--color-text-tertiary)] normal-case" style="letter-spacing: 0;">({teamsForTipo.length})</span>
              </label>
              <input
                type="search"
                bind:value={teamSearch}
                placeholder="Buscar equipo…"
                disabled={mode === 'edit' || submitting}
                class="text-mono w-full px-3 py-2 mb-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[12px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
              />
              <select
                bind:value={selectedTeam}
                onchange={onTeamChange}
                disabled={mode === 'edit' || submitting}
                size={Math.min(8, Math.max(3, teamsForTipo.length))}
                class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
              >
                {#each teamsForTipo as team}
                  <option value={team}>{team}</option>
                {/each}
              </select>
            </div>
          {/if}

          <!-- Modelo -->
          {#if selectedTeam}
            <div>
              <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">
                Modelo (SKU) * <span class="text-[var(--color-text-tertiary)] normal-case" style="letter-spacing: 0;">({modelosForTeam.length})</span>
              </label>
              <select
                value={familyId}
                onchange={(e) => onModeloChange((e.target as HTMLSelectElement).value)}
                disabled={mode === 'edit' || submitting}
                class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[12px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
              >
                <option value="">— elegí modelo —</option>
                {#each modelosForTeam as m}
                  <option value={m.sku}>{formatModeloLabel(m)}</option>
                {/each}
              </select>
            </div>
          {/if}

          <!-- Preview -->
          {#if selectedModelo}
            <div class="bg-[var(--color-surface-2)] border border-[var(--color-terminal)] rounded-[3px] px-3 py-2">
              <div class="text-mono text-[10px] uppercase text-[var(--color-terminal)] mb-1" style="letter-spacing: 0.08em;">● Selección</div>
              <div class="text-[12px] text-[var(--color-text-primary)]">
                {selectedModelo.team} · {selectedModelo.season ?? '?'} {selectedModelo.variant ?? '?'} · {formatModeloVersion(selectedModelo)}
              </div>
              <div class="text-mono text-[11px] text-[var(--color-text-secondary)] tabular-nums mt-0.5">
                SKU: {selectedModelo.sku}
              </div>
            </div>
          {/if}
        {/if}

        <!-- ─── Detalles del item (no cambia con cascade) ─── -->
        <!-- Player name + number -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Player name</label>
            <input type="text" bind:value={playerName} placeholder="Messi" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Number</label>
            <input type="number" bind:value={playerNumber} placeholder="10" min="0" max="99" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
        </div>

        <!-- Size + Patch -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Size</label>
            <select bind:value={size} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">—</option>
              <option value="S">S</option>
              <option value="M">M</option>
              <option value="L">L</option>
              <option value="XL">XL</option>
              <option value="XXL">XXL</option>
            </select>
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Patch</label>
            <select bind:value={patch} disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]">
              <option value="">— sin patch</option>
              <option value="WC">WC (World Cup)</option>
              <option value="Champions">Champions</option>
            </select>
          </div>
        </div>

        <!-- Expected USD + Customer -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Expected USD</label>
            <input type="number" bind:value={expectedUsd} placeholder="15.00" step="0.01" min="0" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] tabular-nums" />
          </div>
          <div>
            <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Customer ID</label>
            <input type="text" bind:value={customerId} placeholder="cust-xyz (vacío = stock)" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
          </div>
        </div>

        <!-- Jersey ID (solo) -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Jersey ID (variant) <span class="text-[var(--color-text-tertiary)] normal-case" style="letter-spacing: 0;">opcional</span></label>
          <input type="text" bind:value={jerseyId} placeholder="opcional" disabled={submitting} class="text-mono w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)]" />
        </div>

        <!-- Notes -->
        <div>
          <label class="text-mono text-[10px] uppercase text-[var(--color-text-tertiary)] block mb-1" style="letter-spacing: 0.08em;">Notes</label>
          <textarea bind:value={notes} rows="2" disabled={submitting} class="w-full px-3 py-2 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[3px] text-[13px] text-[var(--color-text-primary)] resize-none"></textarea>
        </div>

        {#if errorMsg}
          <div class="text-[11px] text-[var(--color-danger)] bg-[rgba(244,63,94,0.10)] border border-[rgba(244,63,94,0.3)] rounded-[3px] px-3 py-2">
            ⚠️ {errorMsg}
          </div>
        {/if}

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-2 border-t border-[var(--color-surface-2)]">
          <button type="button" onclick={() => { if (!submitting) onClose(); }} disabled={submitting} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] bg-transparent border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]">
            Cancelar
          </button>
          <button type="submit" disabled={!canSubmit} class="text-mono text-[11px] px-4 py-1.5 rounded-[3px] font-semibold transition-colors"
            class:bg-[var(--color-accent)]={canSubmit}
            class:text-[var(--color-bg)]={canSubmit}
            class:bg-[var(--color-surface-2)]={!canSubmit}
            class:text-[var(--color-text-tertiary)]={!canSubmit}
            class:cursor-not-allowed={!canSubmit}>
            {submitting ? '⏳ Guardando...' : (mode === 'create' ? '+ Crear item' : '💾 Guardar')}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

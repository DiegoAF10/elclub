<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { CustomerProfile, TimelineEntry } from '$lib/data/comercial';
  import { Star, Loader2, ShoppingCart, Pencil, Ban, CheckCircle2, ExternalLink } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import OrderDetailModal from './OrderDetailModal.svelte';
  import ConversationThreadModal from './ConversationThreadModal.svelte';
  import ManualOrderModal from './ManualOrderModal.svelte';

  interface Props {
    customerId: number;
    onClose: () => void;
  }
  let { customerId, onClose }: Props = $props();

  let profile = $state<CustomerProfile | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);

  // Sub-modal triggers
  let openOrderRef = $state<string | null>(null);
  let openConvId = $state<string | null>(null);
  let openManualOrder = $state(false);

  // Inline editor states
  let editingTraits = $state(false);
  let traitsDraft = $state('');
  let traitsError = $state<string | null>(null);

  let editingSource = $state(false);
  let sourceDraft = $state('');

  let blockedToggling = $state(false);

  const SOURCES = ['f&f', 'ads_meta', 'organic_wa', 'organic_ig', 'messenger', 'web', 'manual', 'otro'];

  async function loadProfile() {
    loading = true;
    error = null;
    try {
      profile = await adapter.getCustomerProfile(customerId);
      if (!profile) error = `Customer ${customerId} no encontrado`;
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { void loadProfile(); });

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('es-GT', { dateStyle: 'short' });
  }

  function fmtTimelineDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }

  function selectTimelineEntry(entry: TimelineEntry) {
    if (entry.kind === 'order') openOrderRef = entry.ref;
    else if (entry.kind === 'conversation') openConvId = entry.convId;
  }

  // === Edit traits ===
  function startEditTraits() {
    if (!profile) return;
    traitsDraft = JSON.stringify(profile.traitsJson ?? {}, null, 2);
    traitsError = null;
    editingTraits = true;
  }

  async function saveTraits() {
    if (!profile) return;
    try {
      const parsed = JSON.parse(traitsDraft);
      if (typeof parsed !== 'object' || Array.isArray(parsed) || parsed === null) {
        traitsError = 'Debe ser un objeto JSON';
        return;
      }
      await adapter.updateCustomerTraits(profile.customerId, parsed);
      editingTraits = false;
      await loadProfile();
    } catch (e) {
      if (e instanceof SyntaxError) {
        traitsError = `JSON inválido: ${e.message}`;
      } else {
        traitsError = e instanceof Error ? e.message : String(e);
      }
    }
  }

  // === Edit source ===
  function startEditSource() {
    if (!profile) return;
    sourceDraft = profile.source ?? 'manual';
    editingSource = true;
  }

  async function saveSource() {
    if (!profile) return;
    try {
      await adapter.updateCustomerSource(profile.customerId, sourceDraft || null);
      editingSource = false;
      await loadProfile();
    } catch (e) {
      console.warn('[customer-profile] source update failed', e);
    }
  }

  // === Block / unblock ===
  async function toggleBlocked() {
    if (!profile || blockedToggling) return;
    blockedToggling = true;
    try {
      await adapter.setCustomerBlocked(profile.customerId, !profile.blocked);
      await loadProfile();
    } catch (e) {
      console.warn('[customer-profile] block toggle failed', e);
    } finally {
      blockedToggling = false;
    }
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if loading}
      <div class="flex items-center gap-2 text-[var(--color-text-secondary)]">
        <Loader2 size={16} class="animate-spin" /> <span class="text-[14px]">Cargando customer…</span>
      </div>
    {:else if error}
      <div class="text-[var(--color-danger)]">{error}</div>
    {:else if profile}
      <div class="flex items-center gap-3">
        <div
          class="flex h-11 w-11 items-center justify-center rounded-[6px]"
          style="background: {profile.isVip ? 'rgba(74,222,128,0.12)' : 'rgba(180,181,184,0.12)'}; border: 1px solid {profile.isVip ? 'rgba(74,222,128,0.3)' : 'rgba(180,181,184,0.3)'};"
        >
          {#if profile.isVip}
            <Star size={18} strokeWidth={1.8} fill="var(--color-accent)" style="color: var(--color-accent);" />
          {:else}
            <span class="text-display text-[12px] text-[var(--color-text-tertiary)]">{profile.name.slice(0, 2).toUpperCase()}</span>
          {/if}
        </div>
        <div>
          <div class="flex items-center gap-2 text-[18px] font-semibold">
            <span>{profile.name}</span>
            {#if profile.isVip}
              <span class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]" style="background: rgba(74,222,128,0.18); color: var(--color-accent);">★ VIP</span>
            {/if}
            {#if profile.blocked}
              <span class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]" style="background: rgba(244,63,94,0.18); color: var(--color-danger);">● BLOCKED</span>
            {/if}
          </div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            <span class="text-mono">Q{profile.totalRevenueGtq.toFixed(0)}</span> LTV ·
            {profile.totalOrders} órdenes ·
            {profile.attribution.customerSource ?? 'sin origen'} ·
            últ {fmtDate(profile.lastOrderAt)}
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if profile}
      <div class="grid grid-cols-[1fr_280px] gap-0 max-h-[500px] overflow-hidden">
        <!-- Timeline -->
        <div class="border-r border-[var(--color-border)] overflow-y-auto px-6 py-4">
          <div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">Timeline · {profile.timeline.length} entries</div>
          {#if profile.timeline.length === 0}
            <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">> sin actividad registrada</div>
          {:else}
            <div class="space-y-2">
              {#each profile.timeline as entry, i (i)}
                <button
                  type="button"
                  onclick={() => selectTimelineEntry(entry)}
                  class="w-full text-left rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 hover:border-[var(--color-accent)]"
                  style="border-left: 3px solid {entry.kind === 'order' ? 'var(--color-accent)' : 'var(--color-warning)'};"
                >
                  <div class="flex items-baseline justify-between gap-2">
                    <div class="flex items-center gap-2">
                      <span class="text-display text-[9px]" style="color: {entry.kind === 'order' ? 'var(--color-accent)' : 'var(--color-warning)'};">
                        [{entry.kind === 'order' ? 'ORDER' : 'CONV'}]
                      </span>
                      {#if entry.kind === 'order'}
                        <span class="text-mono text-[11.5px]">{entry.ref}</span>
                      {:else}
                        <span class="text-mono text-[11px] text-[var(--color-text-secondary)]">{entry.convId}</span>
                      {/if}
                    </div>
                    <span class="text-mono text-[10px] text-[var(--color-text-muted)]">
                      {entry.kind === 'order' ? fmtTimelineDate(entry.occurredAt) : fmtTimelineDate(entry.endedAt)}
                    </span>
                  </div>
                  <div class="mt-1 text-[10.5px] text-[var(--color-text-tertiary)]">
                    {#if entry.kind === 'order'}
                      Q{entry.totalGtq.toFixed(0)} · {entry.status} · {entry.itemsCount} item{entry.itemsCount === 1 ? '' : 's'}
                    {:else}
                      {entry.platform.toUpperCase()} · {entry.outcome ?? 'open'} · {entry.messagesTotal} msgs
                    {/if}
                  </div>
                </button>
              {/each}
            </div>
          {/if}
        </div>

        <!-- Meta sidebar -->
        <div class="overflow-y-auto bg-[var(--color-surface-0)] px-4 py-4">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Info</div>
          <div class="mb-4 space-y-1.5 text-[11px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Phone</span><span class="text-mono">{profile.phone ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Email</span><span class="truncate" style="max-width: 160px;">{profile.email ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">First</span><span class="text-mono">{fmtDate(profile.firstOrderAt)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Active</span><span class="text-mono">{profile.daysInactive ?? '—'}d</span></div>
          </div>

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Atribución</div>
          {#if editingSource}
            <div class="mb-4 space-y-2">
              <select
                bind:value={sourceDraft}
                class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2 py-1 text-[11px]"
              >
                {#each SOURCES as s}
                  <option value={s}>{s}</option>
                {/each}
              </select>
              <div class="flex gap-2">
                <button onclick={saveSource} class="flex-1 rounded-[3px] bg-[var(--color-accent)] px-2 py-0.5 text-[10px] font-semibold text-black">Guardar</button>
                <button onclick={() => (editingSource = false)} class="flex-1 rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">Cancelar</button>
              </div>
            </div>
          {:else}
            <div class="mb-4 space-y-1.5 text-[11px]">
              <div class="flex justify-between">
                <span class="text-[var(--color-text-tertiary)]">Source</span>
                <span>
                  {profile.attribution.customerSource ?? '—'}
                  <button onclick={startEditSource} class="ml-1 text-[10px] text-[var(--color-accent)]">[editar]</button>
                </span>
              </div>
              {#if profile.attribution.leadCampaigns.length > 0}
                <div class="text-[10px] text-[var(--color-text-tertiary)]">
                  Lead camps: <span class="text-mono">{profile.attribution.leadCampaigns.join(' · ')}</span>
                </div>
              {/if}
            </div>
          {/if}

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">
            Traits
            {#if !editingTraits}
              <button onclick={startEditTraits} class="ml-1 text-[10px] text-[var(--color-accent)]">[editar]</button>
            {/if}
          </div>
          {#if editingTraits}
            <div class="mb-4 space-y-2">
              <textarea
                bind:value={traitsDraft}
                class="text-mono w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2 text-[10px]"
                rows="6"
              ></textarea>
              {#if traitsError}<div class="text-[10px] text-[var(--color-danger)]">⚠ {traitsError}</div>{/if}
              <div class="flex gap-2">
                <button onclick={saveTraits} class="flex-1 rounded-[3px] bg-[var(--color-accent)] px-2 py-0.5 text-[10px] font-semibold text-black">Guardar</button>
                <button onclick={() => (editingTraits = false)} class="flex-1 rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px] text-[var(--color-text-secondary)]">Cancelar</button>
              </div>
            </div>
          {:else}
            <pre class="text-mono mb-4 rounded-[3px] bg-[var(--color-surface-1)] p-2 text-[10px] text-[var(--color-text-secondary)]" style="white-space: pre-wrap;">{JSON.stringify(profile.traitsJson, null, 2)}</pre>
          {/if}

          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Status</div>
          <div class="flex items-center justify-between text-[11px]">
            <span class="{profile.blocked ? 'text-[var(--color-danger)]' : 'text-[var(--color-accent)]'}">
              {profile.blocked ? '● Bloqueado' : '● Activo'}
            </span>
            <button
              onclick={toggleBlocked}
              disabled={blockedToggling}
              class="rounded-[3px] border border-[var(--color-border)] px-2 py-0.5 text-[10px] disabled:opacity-50"
            >
              {profile.blocked ? 'Desbloquear' : 'Bloquear'}
            </button>
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if profile}
      <div class="flex items-center gap-2">
        <button
          onclick={() => (openManualOrder = true)}
          class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)]"
        >
          <ShoppingCart size={12} strokeWidth={1.8} /> + Orden manual
        </button>
        <button
          onclick={onClose}
          class="ml-auto rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
        >Cerrar</button>
      </div>
    {/if}
  {/snippet}
</BaseModal>

{#if openOrderRef}
  <OrderDetailModal orderRef={openOrderRef} onClose={() => { openOrderRef = null; loadProfile(); }} />
{/if}

{#if openConvId && profile}
  {@const conv = profile.timeline.find((e) => e.kind === 'conversation' && e.convId === openConvId)}
  {#if conv && conv.kind === 'conversation'}
    <ConversationThreadModal conversations={[{
      convId: conv.convId, leadId: null, brand: 'elclub', platform: conv.platform as any,
      senderId: '', startedAt: '', endedAt: conv.endedAt, outcome: (conv.outcome as any) ?? null,
      orderId: null, messagesTotal: conv.messagesTotal, tagsJson: [], analyzed: false, syncedAt: ''
    }]} onClose={() => { openConvId = null; }} />
  {/if}
{/if}

{#if openManualOrder && profile}
  <ManualOrderModal
    customer={profile}
    onClose={() => { openManualOrder = false; loadProfile(); }}
  />
{/if}

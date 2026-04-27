<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { Lead, ConversationMeta } from '$lib/data/comercial';
  import { Users, MessageCircle } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import ConversationThreadModal from './ConversationThreadModal.svelte';

  interface Props {
    leads: Lead[];
    onClose: () => void;
  }
  let { leads, onClose }: Props = $props();

  let mode = $state<'list' | 'detail'>('list');
  let selectedLead = $state<Lead | null>(null);
  let leadConvs = $state<ConversationMeta[]>([]);
  let loadingConvs = $state(false);
  let convLoadError = $state<string | null>(null);
  let showConvModal = $state(false);

  async function selectLead(lead: Lead) {
    selectedLead = lead;
    mode = 'detail';
    loadingConvs = true;
    convLoadError = null;
    try {
      leadConvs = await adapter.listConversations({ leadId: lead.leadId });
    } catch (e) {
      convLoadError = e instanceof Error ? e.message : String(e);
      console.warn('[lead-profile] load convs failed', e);
      leadConvs = [];
    } finally {
      loadingConvs = false;
    }
  }

  function backToList() {
    mode = 'list';
    selectedLead = null;
    leadConvs = [];
  }

  function fmtPlatform(p: string) {
    return ({ wa: 'WhatsApp', ig: 'Instagram', messenger: 'Messenger', web: 'Web' } as Record<string, string>)[p] ?? p;
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if mode === 'list'}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(96,165,250,0.12); border: 1px solid rgba(96,165,250,0.3);">
          <Users size={18} strokeWidth={1.8} style="color: #60a5fa;" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">Leads · {leads.length}</div>
          <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Click un lead para ver su perfil + conversations</div>
        </div>
      </div>
    {:else if selectedLead}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(96,165,250,0.12); border: 1px solid rgba(96,165,250,0.3);">
          <Users size={18} strokeWidth={1.8} style="color: #60a5fa;" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">{selectedLead.name ?? selectedLead.handle ?? selectedLead.senderId}</div>
          <div class="text-[11.5px] text-[var(--color-text-tertiary)]">
            {fmtPlatform(selectedLead.platform)} · {selectedLead.status} · llegó {fmtDate(selectedLead.firstContactAt)}
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if mode === 'list'}
      <div class="px-6 py-4">
        {#if leads.length === 0}
          <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> 0 leads en este período</div>
        {:else}
          <div class="space-y-2">
            {#each leads as lead (lead.leadId)}
              <button
                type="button"
                onclick={() => selectLead(lead)}
                class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left hover:border-[var(--color-accent)]"
              >
                <div class="flex items-baseline justify-between">
                  <span class="text-[12.5px] font-medium">{lead.name ?? lead.handle ?? lead.senderId}</span>
                  <span class="text-mono text-[10px] text-[var(--color-text-muted)]">{fmtPlatform(lead.platform)}</span>
                </div>
                <div class="text-[10.5px] text-[var(--color-text-tertiary)]">
                  {lead.phone ?? '—'} · status: {lead.status}
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else if selectedLead}
      <div class="grid grid-cols-[1fr_280px] gap-0">
        <div class="border-r border-[var(--color-border)] px-6 py-4">
          <div class="text-display mb-3 text-[9.5px] text-[var(--color-text-tertiary)]">Conversations · {leadConvs.length}</div>
          {#if loadingConvs}
            <div class="text-[11px] text-[var(--color-text-tertiary)]">Cargando…</div>
          {:else if convLoadError}
            <div class="text-[9.5px] text-[var(--color-danger)]">⚠ {convLoadError}</div>
          {:else if leadConvs.length === 0}
            <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> sin conversations</div>
          {:else}
            {#each leadConvs as conv (conv.convId)}
              <button
                type="button"
                onclick={() => (showConvModal = true)}
                class="mb-2 w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left hover:border-[var(--color-accent)]"
              >
                <div class="text-mono text-[11px]">{conv.convId}</div>
                <div class="text-[10px] text-[var(--color-text-tertiary)]">
                  {fmtDate(conv.startedAt)} → {fmtDate(conv.endedAt)} · {conv.outcome ?? 'open'} · {conv.messagesTotal} msgs
                </div>
              </button>
            {/each}
          {/if}
        </div>
        <div class="px-4 py-4 bg-[var(--color-surface-0)]">
          <div class="text-display mb-2 text-[9.5px] text-[var(--color-text-tertiary)]">Lead</div>
          <div class="space-y-2 text-[11.5px]">
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Nombre</span><span>{selectedLead.name ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Handle</span><span>{selectedLead.handle ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Phone</span><span class="text-mono">{selectedLead.phone ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Plataforma</span><span>{fmtPlatform(selectedLead.platform)}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Status</span><span>{selectedLead.status}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Source camp.</span><span class="text-mono">{selectedLead.sourceCampaignId ?? '—'}</span></div>
            <div class="flex justify-between"><span class="text-[var(--color-text-tertiary)]">Sender ID</span><span class="text-mono text-[10px]">{selectedLead.senderId}</span></div>
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    {#if mode === 'detail'}
      <button
        type="button"
        onclick={backToList}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
      >← Volver a lista</button>
    {/if}
    <div class="ml-auto">
      <button
        type="button"
        onclick={onClose}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
      >Cerrar</button>
    </div>
  {/snippet}
</BaseModal>

{#if showConvModal && selectedLead}
  <ConversationThreadModal conversations={leadConvs} onClose={() => (showConvModal = false)} />
{/if}

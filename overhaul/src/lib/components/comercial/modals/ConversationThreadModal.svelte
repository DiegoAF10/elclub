<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ConversationMeta, ConversationMessage } from '$lib/data/comercial';
  import { MessageCircle, Loader2, ExternalLink } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';
  import { SYNC_CONSTANTS } from '$lib/data/manychatSync';

  interface Props {
    conversations: ConversationMeta[];
    onClose: () => void;
  }
  let { conversations, onClose }: Props = $props();

  let mode = $state<'list' | 'detail'>('list');
  let selectedConv = $state<ConversationMeta | null>(null);
  let messages = $state<ConversationMessage[]>([]);
  let loadingMsgs = $state(false);
  let messagesError = $state<string | null>(null);

  async function selectConv(conv: ConversationMeta) {
    selectedConv = conv;
    mode = 'detail';
    loadingMsgs = true;
    messagesError = null;
    try {
      messages = await adapter.getConversationMessages({
        convId: conv.convId,
        workerBase: SYNC_CONSTANTS.WORKER_BASE,
        dashboardKey: SYNC_CONSTANTS.DASHBOARD_KEY,
      });
    } catch (e) {
      messagesError = e instanceof Error ? e.message : String(e);
      messages = [];
    } finally {
      loadingMsgs = false;
    }
  }

  function backToList() {
    mode = 'list';
    selectedConv = null;
    messages = [];
    messagesError = null;
  }

  function handleResponderWA() {
    if (!selectedConv) return;
    // Phone may not be in conv directly — best-effort: senderId for WA, alert for others
    const phone = selectedConv.platform === 'wa' ? selectedConv.senderId.replace(/\D/g, '') : null;
    if (!phone) {
      alert('Sin teléfono — esta conversation es de IG/Messenger. Respondé desde la app.');
      return;
    }
    window.open(`https://wa.me/${phone}`, '_blank');
  }

  function fmtDate(iso: string | null): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' });
  }

  function fmtPlatform(p: string) {
    return ({ wa: 'WA', ig: 'IG', messenger: 'Messenger', web: 'Web' } as Record<string, string>)[p] ?? p;
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    {#if mode === 'list'}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.3);">
          <MessageCircle size={18} strokeWidth={1.8} style="color: var(--color-warning);" />
        </div>
        <div>
          <div class="text-[18px] font-semibold">Conversations · {conversations.length}</div>
          <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Click una conversation para ver el thread</div>
        </div>
      </div>
    {:else if selectedConv}
      <div class="flex items-center gap-3">
        <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(251,191,36,0.12); border: 1px solid rgba(251,191,36,0.3);">
          <MessageCircle size={18} strokeWidth={1.8} style="color: var(--color-warning);" />
        </div>
        <div>
          <div class="flex items-center gap-2 text-[16px] font-semibold">
            <span class="text-mono text-[14px]">{selectedConv.convId}</span>
            <span class="text-display rounded-[3px] px-2 py-0.5 text-[9.5px]" style="background: rgba(107,110,117,0.2); color: var(--color-text-secondary);">
              ● {(selectedConv.outcome ?? 'OPEN').toUpperCase()}
            </span>
          </div>
          <div class="mt-0.5 text-[11.5px] text-[var(--color-text-tertiary)]">
            {fmtPlatform(selectedConv.platform)} · {selectedConv.messagesTotal} msgs · {fmtDate(selectedConv.startedAt)} → {fmtDate(selectedConv.endedAt)}
          </div>
        </div>
      </div>
    {/if}
  {/snippet}

  {#snippet body()}
    {#if mode === 'list'}
      <div class="px-6 py-4">
        {#if conversations.length === 0}
          <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> sin conversations en este período</div>
        {:else}
          <div class="space-y-2">
            {#each conversations as conv (conv.convId)}
              <button
                type="button"
                onclick={() => selectConv(conv)}
                class="w-full rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left hover:border-[var(--color-accent)]"
              >
                <div class="flex items-baseline justify-between">
                  <span class="text-mono text-[12px]">{conv.convId}</span>
                  <span class="text-mono text-[10px] text-[var(--color-text-muted)]">{fmtPlatform(conv.platform)}</span>
                </div>
                <div class="text-[10.5px] text-[var(--color-text-tertiary)]">
                  {conv.outcome ?? 'open'} · {conv.messagesTotal} msgs · {fmtDate(conv.endedAt)}
                </div>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {:else if selectedConv}
      <div class="px-6 py-4">
        {#if loadingMsgs}
          <div class="flex items-center gap-2 text-[11.5px] text-[var(--color-text-tertiary)]">
            <Loader2 size={14} class="animate-spin" /> Cargando mensajes…
          </div>
        {:else if messagesError}
          <div class="text-[11.5px] text-[var(--color-danger)]">⚠ {messagesError}</div>
        {:else if messages.length === 0}
          <div class="text-mono text-[11.5px] text-[var(--color-text-tertiary)]">> mensajes >90d fueron purgados</div>
        {:else}
          <div class="space-y-2 max-h-[450px] overflow-y-auto">
            {#each messages as msg}
              <div class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-2.5">
                <div class="text-display mb-1 text-[9.5px]" style="color: {msg.role === 'user' ? 'var(--color-warning)' : msg.role === 'assistant' ? 'var(--color-accent)' : 'var(--color-text-tertiary)'};">
                  {msg.role.toUpperCase()}
                </div>
                <div class="text-[11.5px] whitespace-pre-wrap text-[var(--color-text-primary)]">{msg.text}</div>
                <div class="text-mono mt-1 text-[9.5px] text-[var(--color-text-muted)]">{fmtDate(msg.timestamp)}</div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  {/snippet}

  {#snippet footer()}
    <div class="flex items-center justify-between gap-2">
      {#if mode === 'detail'}
        <button
          type="button"
          onclick={backToList}
          class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
        >← Volver</button>
        <button
          type="button"
          onclick={handleResponderWA}
          class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black"
        >
          <ExternalLink size={12} strokeWidth={2.2} />
          Responder en WA
        </button>
      {/if}
      <button
        type="button"
        onclick={onClose}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)] ml-auto"
      >Cerrar</button>
    </div>
  {/snippet}
</BaseModal>

<script lang="ts">
  import { X } from 'lucide-svelte';
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    onClose: () => void;
    /** Header rico — avatar/icon + nombre + status pill + meta */
    header: Snippet;
    /** Stats strip horizontal (5 columnas usualmente) */
    stats?: Snippet;
    /** Body principal — usualmente 2 cols (timeline + factbook) */
    body: Snippet;
    /** Footer con acciones primarias + cerrar */
    footer?: Snippet;
    /** Width override; default 880px */
    maxWidth?: number;
  }

  let { open, onClose, header, stats, body, footer, maxWidth = 880 }: Props = $props();

  function handleKey(e: KeyboardEvent) {
    if (open && e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  }

  function handleBackdrop(e: MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }
</script>

<svelte:window on:keydown={handleKey} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center"
    style="background: rgba(0,0,0,0.55); backdrop-filter: blur(2px);"
    onclick={handleBackdrop}
    role="dialog"
    aria-modal="true"
  >
    <div
      class="flex flex-col overflow-hidden rounded-[8px] border border-[var(--color-border-strong)] bg-[var(--color-bg)]"
      style="
        width: 90%;
        max-width: {maxWidth}px;
        max-height: 90vh;
        box-shadow: 0 20px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(74, 222, 128, 0.08);
      "
    >
      <!-- Header -->
      <div class="flex items-start gap-4 border-b border-[var(--color-border)] px-6 py-4">
        <div class="flex-1 min-w-0">{@render header()}</div>
        <button
          type="button"
          onclick={onClose}
          aria-label="Cerrar"
          class="rounded-[3px] p-1 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-surface-1)] hover:text-[var(--color-text-primary)]"
        >
          <X size={16} strokeWidth={2} />
        </button>
      </div>

      <!-- Stats strip (opcional) -->
      {#if stats}
        <div class="border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-3">
          {@render stats()}
        </div>
      {/if}

      <!-- Body -->
      <div class="flex-1 overflow-y-auto">
        {@render body()}
      </div>

      <!-- Footer (opcional) -->
      {#if footer}
        <div class="border-t border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-3">
          {@render footer()}
        </div>
      {/if}
    </div>
  </div>
{/if}

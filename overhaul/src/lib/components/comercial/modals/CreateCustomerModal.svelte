<script lang="ts">
  import { adapter } from '$lib/adapter';
  import { UserPlus, Loader2 } from 'lucide-svelte';
  import BaseModal from '../BaseModal.svelte';

  interface Props {
    onClose: () => void;
  }
  let { onClose }: Props = $props();

  let name = $state('');
  let phone = $state('');
  let email = $state('');
  let source = $state('f&f');
  let saving = $state(false);
  let error = $state<string | null>(null);

  const SOURCES = ['f&f', 'ads_meta', 'organic_wa', 'organic_ig', 'messenger', 'web', 'manual', 'otro'];

  async function handleSubmit() {
    error = null;
    if (!name.trim()) {
      error = 'Nombre es requerido';
      return;
    }
    saving = true;
    try {
      const result = await adapter.createCustomer({
        name: name.trim(),
        phone: phone.trim() || null,
        email: email.trim() || null,
        source: source || null,
      });
      if (!result.ok) {
        error = result.error ?? 'Error desconocido';
      } else {
        onClose();
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      saving = false;
    }
  }
</script>

<BaseModal open={true} {onClose}>
  {#snippet header()}
    <div class="flex items-center gap-3">
      <div class="flex h-11 w-11 items-center justify-center rounded-[6px]" style="background: rgba(74,222,128,0.12); border: 1px solid rgba(74,222,128,0.3);">
        <UserPlus size={18} strokeWidth={1.8} style="color: var(--color-accent);" />
      </div>
      <div>
        <div class="text-[18px] font-semibold">Crear customer manual</div>
        <div class="text-[11.5px] text-[var(--color-text-tertiary)]">Registro mínimo. Después podés crear orden manual desde el profile.</div>
      </div>
    </div>
  {/snippet}

  {#snippet body()}
    <div class="space-y-3 px-6 py-4">
      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Nombre *</label>
        <input
          type="text"
          bind:value={name}
          placeholder="Pedro García"
          class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        />
      </div>

      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Phone</label>
        <input
          type="text"
          bind:value={phone}
          placeholder="+502 1234-5678"
          class="text-mono w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        />
      </div>

      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Email</label>
        <input
          type="email"
          bind:value={email}
          placeholder="pedro@gmail.com"
          class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        />
      </div>

      <div>
        <label class="text-display mb-1 block text-[9.5px] text-[var(--color-text-tertiary)]">Origen</label>
        <select
          bind:value={source}
          class="w-full rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-primary)]"
        >
          {#each SOURCES as s}
            <option value={s}>{s}</option>
          {/each}
        </select>
      </div>

      {#if error}
        <div class="rounded-[3px] border border-[var(--color-danger)] bg-[var(--color-surface-1)] p-2 text-[10.5px] text-[var(--color-danger)]">
          ⚠ {error}
        </div>
      {/if}
    </div>
  {/snippet}

  {#snippet footer()}
    <div class="flex items-center gap-2">
      <button
        type="button"
        onclick={onClose}
        disabled={saving}
        class="rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] text-[var(--color-text-secondary)]"
      >Cancelar</button>
      <button
        type="button"
        onclick={handleSubmit}
        disabled={saving || !name.trim()}
        class="ml-auto flex items-center gap-2 rounded-[4px] bg-[var(--color-accent)] px-3 py-1.5 text-[11.5px] font-semibold text-black disabled:opacity-60"
      >
        {#if saving}
          <Loader2 size={12} strokeWidth={2} class="animate-spin" /> Creando…
        {:else}
          Crear
        {/if}
      </button>
    </div>
  {/snippet}
</BaseModal>

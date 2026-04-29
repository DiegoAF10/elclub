<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ImpSetting } from '$lib/adapter/types';

  let { setting, label, hint = '', inputType = 'number', step = '0.01', onSaved } = $props<{
    setting: ImpSetting;
    label: string;
    hint?: string;
    inputType?: 'number' | 'text';
    step?: string;
    onSaved?: (s: ImpSetting) => void;
  }>();

  let draft = $state(setting.value);
  let saving = $state(false);
  let error = $state<string | null>(null);
  let savedOk = $state(false);

  let dirty = $derived(draft !== setting.value);

  async function save() {
    if (!dirty || saving) return;
    saving = true;
    error = null;
    savedOk = false;
    try {
      const updated = await adapter.updateImpSetting(setting.key, draft);
      onSaved?.(updated);
      savedOk = true;
      setTimeout(() => (savedOk = false), 2000);
    } catch (e: any) {
      error = e?.message ?? String(e);
    } finally {
      saving = false;
    }
  }
</script>

<div class="settings-field">
  <label for={`fld-${setting.key}`}>
    <span class="lbl">{label}</span>
    {#if hint}<span class="hint">{hint}</span>{/if}
  </label>
  <div class="row">
    <input
      id={`fld-${setting.key}`}
      type={inputType}
      step={inputType === 'number' ? step : undefined}
      bind:value={draft}
      disabled={saving}
    />
    <button onclick={save} disabled={!dirty || saving} class="save-btn">
      {saving ? '...' : 'Guardar'}
    </button>
    {#if savedOk}<span class="ok">✓</span>{/if}
  </div>
  {#if error}
    <div class="err">⚠️ {error}</div>
  {/if}
  {#if setting.updatedAt}
    <div class="meta">Última actualización: {setting.updatedAt}{setting.updatedBy ? ` · ${setting.updatedBy}` : ''}</div>
  {/if}
</div>

<style>
  .settings-field { margin-bottom: 14px; }
  label { display: flex; flex-direction: column; gap: 2px; margin-bottom: 4px; }
  .lbl { text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px; color: var(--text-2, #aaa); }
  .hint { font-size: 11px; color: var(--text-3, #777); }
  .row { display: flex; gap: 8px; align-items: center; }
  input {
    background: var(--surface-2, #16161b);
    border: 1px solid var(--border, #22222a);
    color: inherit;
    padding: 6px 10px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    width: 140px;
    font-variant-numeric: tabular-nums;
  }
  input:focus { outline: 1px solid var(--accent, #5b8def); border-color: var(--accent, #5b8def); }
  .save-btn {
    background: var(--accent, #5b8def);
    color: #fff;
    border: 0;
    padding: 6px 12px;
    border-radius: 3px;
    cursor: pointer;
    font-size: 12px;
  }
  .save-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .ok { color: var(--terminal, #4ade80); }
  .err { margin-top: 4px; color: var(--alert, #f43f5e); font-size: 12px; }
  .meta { margin-top: 4px; font-size: 11px; color: var(--text-3, #777); font-family: 'JetBrains Mono', monospace; }
</style>

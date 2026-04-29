<script lang="ts">
  import { adapter } from '$lib/adapter';
  import type { ImpSetting } from '$lib/adapter/types';
  import SettingsSection from '../SettingsSection.svelte';
  import SettingsField from '../SettingsField.svelte';
  import MigrationLogPanel from '../MigrationLogPanel.svelte';
  import IntegrationsStatusPanel from '../IntegrationsStatusPanel.svelte';

  let settings = $state<ImpSetting[]>([]);
  let loading = $state(true);
  let error = $state<string | null>(null);

  async function load() {
    loading = true;
    error = null;
    try {
      settings = await adapter.getImpSettings();
    } catch (e: any) {
      error = e?.message ?? String(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => { load(); });

  function settingByKey(key: string): ImpSetting | undefined {
    return settings.find((s) => s.key === key);
  }

  function onSaved(updated: ImpSetting) {
    settings = settings.map((s) => (s.key === updated.key ? updated : s));
  }
</script>

<div class="settings-tab">
  <header class="tab-head">
    <h2>Settings</h2>
    <p class="sub">Defaults, umbrales para inbox events, y status de integraciones.</p>
  </header>

  {#if loading}
    <div class="skeleton-block">
      <div class="line w-30"></div>
      <div class="line w-50"></div>
      <div class="line w-40"></div>
    </div>
  {:else if error}
    <div class="err-banner">⚠️ Error cargando settings: {error}</div>
  {:else}
    <SettingsSection title="Defaults">
      {@const fx = settingByKey('default_fx')}
      {@const ratio = settingByKey('default_free_ratio')}
      {@const target = settingByKey('default_wishlist_target')}
      {#if fx}<SettingsField setting={fx} label="FX default" hint="Tipo de cambio default (Q por USD)" {onSaved} />{/if}
      {#if ratio}<SettingsField setting={ratio} label="Free unit ratio" hint="1 free cada N paid units (R4 hardcoded en v0.4.0 · cablea en v0.5)" {onSaved} />{/if}
      {#if target}<SettingsField setting={target} label="Wishlist target" hint="Tamaño target para sugerir promote-to-batch" {onSaved} />{/if}
      <div class="ro-row">
        <span class="lbl">Lead time supplier (auto)</span>
        <span class="val">— calculado del scorecard</span>
      </div>
    </SettingsSection>

    <SettingsSection title="Umbrales (Inbox events)" defaultOpen={false}>
      {@const t1 = settingByKey('threshold_wishlist_unbatched_days')}
      {@const t2 = settingByKey('threshold_paid_unarrived_days')}
      {@const t3 = settingByKey('threshold_cost_overrun_pct')}
      {@const t4 = settingByKey('threshold_free_unit_unassigned_days')}
      {#if t1}<SettingsField setting={t1} label="Wishlist sin batch" hint="Días sin promote → inbox alert" {onSaved} />{/if}
      {#if t2}<SettingsField setting={t2} label="Batch paid sin arrived" hint="Días en pipeline → inbox alert" {onSaved} />{/if}
      {#if t3}<SettingsField setting={t3} label="Cost overrun %" hint="% sobre avg → inbox alert" {onSaved} />{/if}
      {#if t4}<SettingsField setting={t4} label="Free unit sin asignar" hint="Días unassigned → inbox alert" {onSaved} />{/if}
      <p class="muted-note">Nota: los thresholds se almacenan acá pero el módulo Comercial es responsable de consumir los valores y emitir los inbox events. Follow-up post v0.4.0.</p>
    </SettingsSection>

    <SettingsSection title="Migration log" defaultOpen={false}>
      <MigrationLogPanel />
    </SettingsSection>

    <SettingsSection title="Integrations" defaultOpen={false}>
      <IntegrationsStatusPanel />
    </SettingsSection>
  {/if}
</div>

<style>
  .settings-tab { padding: 16px; max-width: 760px; }
  .tab-head { margin-bottom: 16px; }
  .tab-head h2 { margin: 0; font-size: 14px; text-transform: uppercase; letter-spacing: 0.08em; }
  .sub { font-size: 12px; color: var(--text-3, #777); margin: 4px 0 0; }
  .skeleton-block { padding: 12px; background: var(--surface-1, #0f0f12); border-radius: 4px; border: 1px solid var(--border, #22222a); }
  .skeleton-block .line {
    height: 10px; background: linear-gradient(90deg, var(--surface-2, #16161b), var(--surface-3, #1e1e24), var(--surface-2, #16161b));
    background-size: 200% 100%; border-radius: 2px; margin-bottom: 8px;
    animation: shimmer 1.4s infinite;
  }
  .w-30 { width: 30%; } .w-40 { width: 40%; } .w-50 { width: 50%; }
  @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
  .err-banner { padding: 10px 14px; background: rgba(244,63,94,0.1); border: 1px solid var(--alert, #f43f5e); border-radius: 3px; color: var(--alert, #f43f5e); }
  .ro-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 12px; }
  .ro-row .lbl { text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-2, #aaa); font-size: 11px; }
  .ro-row .val { color: var(--text-3, #777); font-style: italic; }
  .muted-note { margin-top: 8px; font-size: 11px; color: var(--text-3, #777); font-style: italic; padding: 6px; background: var(--surface-2, #16161b); border-radius: 2px; }
</style>

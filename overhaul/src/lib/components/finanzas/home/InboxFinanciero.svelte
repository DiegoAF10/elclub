<script lang="ts">
  import type { HomeSnapshot, FinanzasInboxEvent, InboxSeverity } from '$lib/data/finanzas';
  import { formatGTQ } from '$lib/data/finanzasComputed';

  let { snapshot }: { snapshot: HomeSnapshot } = $props();

  let events = $derived<FinanzasInboxEvent[]>(deriveEvents(snapshot));

  function deriveEvents(s: HomeSnapshot): FinanzasInboxEvent[] {
    const out: FinanzasInboxEvent[] = [];
    const now = new Date().toISOString();

    if (s.cash_stale_days !== null && s.cash_stale_days > 14) {
      out.push({
        event_id: 'cash-stale-crit',
        severity: 'crit',
        title: `Cash balance ${s.cash_stale_days}d stale`,
        sub: 'syncea desde tab Cuenta business',
        detected_at: now,
      });
    } else if (s.cash_stale_days !== null && s.cash_stale_days > 7) {
      out.push({
        event_id: 'cash-stale-warn',
        severity: 'warn',
        title: `Cash balance ${s.cash_stale_days}d sin sync`,
        sub: 'considerá actualizarlo · cadencia weekly default',
        detected_at: now,
      });
    } else if (s.cash_business_gtq === null) {
      out.push({
        event_id: 'cash-never',
        severity: 'info',
        title: 'Cash balance nunca sincronizado',
        sub: 'primer sync arranca la historia · tab Cuenta business (R3)',
        detected_at: now,
      });
    }

    if (s.shareholder_loan_trend_30d > 500) {
      out.push({
        event_id: 'loan-growing',
        severity: 'warn',
        title: `Shareholder loan creció ${formatGTQ(s.shareholder_loan_trend_30d)} en 30d`,
        sub: 'considerá un movimiento business → personal cuando haya cash',
        detected_at: now,
      });
    }

    if (
      s.profit.profit_operativo > 0 &&
      s.profit.prev_period_profit !== undefined &&
      s.profit.prev_period_profit !== null &&
      s.profit.prev_period_profit < 0
    ) {
      out.push({
        event_id: 'profit-flipped',
        severity: 'strat',
        title: 'Profit positivo este período',
        sub: `vs ${formatGTQ(s.profit.prev_period_profit)} el anterior · momentum`,
        detected_at: now,
      });
    }

    if (s.profit.revenue_gtq === 0 && s.profit.opex_gtq === 0 && s.profit.cogs_gtq === 0) {
      out.push({
        event_id: 'all-clean',
        severity: 'info',
        title: 'Sin actividad financiera todavía',
        sub: '> all clean. nothing to act on.',
        detected_at: now,
      });
    }

    return out;
  }

  function severityClass(sev: InboxSeverity): string {
    switch (sev) {
      case 'crit': return 'border-l-[var(--color-danger)]';
      case 'warn': return 'border-l-[var(--color-warning)]';
      case 'info': return 'border-l-[var(--color-accent)]';
      case 'strat': return 'border-l-[var(--color-live)]';
    }
  }
</script>

<div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-4 flex flex-col min-h-0">
  <div class="text-mono text-[10px] uppercase mb-3 text-[var(--color-text-tertiary)] flex items-center justify-between" style="letter-spacing: 0.08em;">
    <span>Inbox financiero</span>
    <span class="text-[var(--color-text-secondary)]">{events.length}</span>
  </div>
  {#if events.length === 0}
    <div class="text-mono text-[11px] text-[var(--color-text-tertiary)]">&gt; all clean. nothing to act on.</div>
  {:else}
    <ul class="flex flex-col gap-2 overflow-y-auto">
      {#each events as ev (ev.event_id)}
        <li class="border-l-[3px] {severityClass(ev.severity)} pl-3 py-1">
          <div class="text-[12px] text-[var(--color-text-primary)]">{ev.title}</div>
          <div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-0.5">{ev.sub}</div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

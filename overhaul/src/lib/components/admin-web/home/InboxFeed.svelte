<!--
	InboxFeed — lista vertical de inbox events del Home.

	Carga adminWeb.list_inbox_events() on-mount + auto-refresh cada 60s.
	Sort backend (Rust): critical → important → info, recencia desc.
	Display: 5-7 eventos visibles + footer "VER TODOS (N)" si hay más.
	Dismiss optimista (remueve de lista local antes de await Tauri).
-->
<script lang="ts">
	import { ChevronRight } from 'lucide-svelte';
	import { adminWeb } from '$lib/adapter';
	import type { InboxEvent } from '$lib/adapter';
	import EventCard from './EventCard.svelte';

	const VISIBLE_LIMIT = 7;
	const REFRESH_MS = 60_000;

	let events = $state<InboxEvent[]>([]);
	let loaded = $state(false);

	async function loadEvents() {
		try {
			const next = await adminWeb.list_inbox_events({});
			events = next as InboxEvent[];
		} catch {
			events = [];
		} finally {
			loaded = true;
		}
	}

	$effect(() => {
		// On-mount: trigger detector + load. Después solo poll list (detector
		// es idempotente pero costoso para correr cada 60s — el cron del
		// scheduled_job 'detect-inbox-events' se encarga del refresh real).
		void (async () => {
			try {
				await adminWeb.detect_events_now();
			} catch {
				/* no fatal: lista igual carga lo que ya esté en DB */
			}
			void loadEvents();
		})();

		const interval = setInterval(() => {
			void loadEvents();
		}, REFRESH_MS);
		return () => clearInterval(interval);
	});

	async function handleDismiss(id: number) {
		// Optimistic remove
		events = events.filter((e) => e.id !== id);
		try {
			await adminWeb.dismiss_event({ id });
		} catch {
			// Revertir si falla — re-load real
			void loadEvents();
		}
	}

	const visible = $derived(events.slice(0, VISIBLE_LIMIT));
	const hidden = $derived(Math.max(0, events.length - VISIBLE_LIMIT));
</script>

<div
	class="flex h-full flex-col rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)]"
>
	<div
		class="flex h-10 shrink-0 items-center justify-between border-b border-[var(--color-border)] px-3"
	>
		<div class="flex items-center gap-2">
			<span
				class="text-display text-[10.5px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>
				INBOX
			</span>
			{#if loaded}
				<span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">
					{events.length}
				</span>
			{/if}
		</div>
		{#if loaded && events.length === 0}
			<span class="text-mono text-[9.5px] text-[var(--color-live)]">● ALL CLEAR</span>
		{/if}
	</div>

	<div class="flex-1 overflow-y-auto p-2">
		{#if !loaded}
			<div class="space-y-2">
				{#each Array(3) as _, i (i)}
					<div
						class="h-16 animate-pulse rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)]"
					></div>
				{/each}
			</div>
		{:else if visible.length === 0}
			<div
				class="flex h-full items-center justify-center text-[11px] text-[var(--color-text-muted)]"
			>
				No hay eventos pendientes.
			</div>
		{:else}
			<div class="space-y-2">
				{#each visible as event (event.id)}
					<EventCard {event} onDismiss={handleDismiss} />
				{/each}
			</div>
		{/if}
	</div>

	{#if hidden > 0}
		<button
			type="button"
			class="text-display flex shrink-0 items-center justify-center gap-1.5 border-t border-[var(--color-border)] py-2 text-[10px] tracking-[0.14em] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
			title="Ver todos los eventos"
		>
			VER TODOS · {events.length}
			<ChevronRight size={11} strokeWidth={1.8} />
		</button>
	{/if}
</div>

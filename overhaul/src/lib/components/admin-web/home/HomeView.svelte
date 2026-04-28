<!--
	HomeView — assembly del dashboard del Admin Web.
	Orquesta:
		- header "HOME" + datetime
		- KpisGrid (4×2)
		- AccesosTiles (5 tiles)
		- InboxFeed (lateral, en columna)

	Layout: header arriba, grid 2-col debajo (KPIs+Tiles a la izquierda
	apilados, Inbox a la derecha ocupando full height).
-->
<script lang="ts">
	import KpisGrid from './KpisGrid.svelte';
	import AccesosTiles from './AccesosTiles.svelte';
	import InboxFeed from './InboxFeed.svelte';

	// Datetime header reactivo, refresh cada 30s
	let now = $state(new Date());
	$effect(() => {
		const interval = setInterval(() => {
			now = new Date();
		}, 30_000);
		return () => clearInterval(interval);
	});

	const formattedNow = $derived.by(() => {
		// Format: '28 abr 2026 · 23:47' — corto y legible
		const months = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
		const d = now.getDate();
		const m = months[now.getMonth()];
		const y = now.getFullYear();
		const hh = String(now.getHours()).padStart(2, '0');
		const mm = String(now.getMinutes()).padStart(2, '0');
		return `${d} ${m} ${y} · ${hh}:${mm}`;
	});
</script>

<div class="flex h-full flex-col p-4">
	<!-- Header -->
	<div class="mb-4 flex shrink-0 items-baseline justify-between">
		<div>
			<div
				class="text-display text-[24px] tracking-[0.16em] text-[var(--color-text-primary)]"
			>
				HOME
			</div>
			<div class="text-mono mt-0.5 text-[10.5px] text-[var(--color-text-muted)]">
				{formattedNow}
			</div>
		</div>
	</div>

	<!-- Body: 2 columnas. Izquierda KPIs+Tiles, derecha Inbox -->
	<div class="grid min-h-0 flex-1 grid-cols-[1fr_360px] gap-4">
		<div class="flex min-h-0 flex-col gap-4 overflow-y-auto">
			<KpisGrid />
			<AccesosTiles />
		</div>
		<div class="min-h-0">
			<InboxFeed />
		</div>
	</div>
</div>

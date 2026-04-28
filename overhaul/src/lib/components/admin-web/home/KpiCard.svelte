<!--
	KpiCard — tarjeta unitaria de KPI con icon + value + label + sparkline.
	Sparkline render con SVG inline (sin chart library, ADR explícito).

	Click navega al `target` route. Hover effect: borde verde terminal.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { Activity } from 'lucide-svelte';

	interface Props {
		icon: typeof Activity; // lucide icon — typeof X estructural match
		label: string;
		value: string | number;
		suffix?: string;
		target: string;
		sparkline?: number[];
		tone?: 'default' | 'warn' | 'critical';
	}

	// `icon: Icon` rename para usar `<Icon />` directo en markup
	// (capitalizado, Svelte requiere PascalCase para components).
	let {
		icon: Icon,
		label,
		value,
		suffix,
		target,
		sparkline = [],
		tone = 'default'
	}: Props = $props();

	function go() {
		void goto(target);
	}

	// SVG sparkline: viewBox normalizado 100×30, polyline relativa al min/max
	// del array. Si todos los valores son iguales devuelve línea horizontal.
	const sparkPath = $derived.by(() => {
		if (sparkline.length < 2) return null;
		const min = Math.min(...sparkline);
		const max = Math.max(...sparkline);
		const range = max - min || 1;
		const xStep = 100 / (sparkline.length - 1);
		const points = sparkline.map((v, i) => {
			const x = i * xStep;
			const y = 30 - ((v - min) / range) * 28 - 1;
			return `${x.toFixed(1)},${y.toFixed(1)}`;
		});
		return points.join(' ');
	});

	const accentColor = $derived(
		tone === 'critical'
			? 'var(--color-danger)'
			: tone === 'warn'
				? 'var(--color-warning)'
				: 'var(--color-terminal)'
	);
</script>

<button
	type="button"
	onclick={go}
	class="group relative flex flex-col gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] p-3 text-left transition-all hover:border-[var(--color-terminal)] hover:bg-[var(--color-surface-2)]"
>
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-1.5 text-[var(--color-text-tertiary)]">
			<Icon size={12} strokeWidth={1.8} />
			<span
				class="text-display text-[9.5px] tracking-[0.14em]"
				style:color={accentColor}
				class:opacity-70={tone === 'default'}
			>
				{label}
			</span>
		</div>
		{#if sparkPath}
			<svg viewBox="0 0 100 30" class="h-5 w-12 opacity-70 group-hover:opacity-100">
				<polyline
					points={sparkPath}
					fill="none"
					stroke={accentColor}
					stroke-width="1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		{/if}
	</div>
	<div class="flex items-baseline gap-1">
		<span
			class="text-mono text-[26px] font-semibold leading-none tabular-nums text-[var(--color-text-primary)]"
		>
			{value}
		</span>
		{#if suffix}
			<span class="text-mono text-[12px] text-[var(--color-text-muted)]">{suffix}</span>
		{/if}
	</div>
</button>

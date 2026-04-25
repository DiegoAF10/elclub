<script lang="ts">
	import type { Status } from '$lib/data/types';

	interface Props {
		status: Status;
		size?: 'xs' | 'sm';
	}

	let { status, size = 'sm' }: Props = $props();

	const CONFIG: Record<Status, { label: string; color: string; dot: string; glow: boolean }> = {
		live: {
			label: 'LIVE',
			color: 'text-[var(--color-live)]',
			dot: 'bg-[var(--color-live)]',
			glow: true
		},
		ready: {
			label: 'READY',
			color: 'text-[var(--color-ready)]',
			dot: 'bg-[var(--color-ready)]',
			glow: false
		},
		pending: {
			label: 'PEND',
			color: 'text-[var(--color-text-secondary)]',
			dot: 'bg-[var(--color-text-tertiary)]',
			glow: false
		},
		rework: {
			label: 'RWRK',
			color: 'text-[var(--color-rework)]',
			dot: 'bg-[var(--color-rework)]',
			glow: false
		},
		flagged: {
			label: 'FLAG',
			color: 'text-[var(--color-flagged)]',
			dot: 'bg-[var(--color-flagged)]',
			glow: false
		},
		missing: {
			label: 'FALTA',
			color: 'text-[var(--color-missing)]',
			dot: 'bg-[var(--color-missing)]',
			glow: false
		}
	};

	let cfg = $derived(CONFIG[status]);
	let px = $derived(size === 'xs' ? 'text-[9.5px]' : 'text-[10.5px]');
	let dotSz = $derived(size === 'xs' ? 'h-1.5 w-1.5' : 'h-2 w-2');
</script>

<span
	class="text-display inline-flex items-center gap-1.5 {cfg.color} {px} tabular-nums"
	style="letter-spacing: 0.08em;"
>
	<span
		class="rounded-full {dotSz} {cfg.dot}"
		class:pulse-live={cfg.glow}
	></span>
	{cfg.label}
</span>

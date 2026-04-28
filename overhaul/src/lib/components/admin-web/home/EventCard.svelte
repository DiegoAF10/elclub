<!--
	EventCard — render unitario de un inbox_event.
	Border-left color según severity. Hover muestra X dismiss.
	Action button (si action_label) navega a action_target.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { X } from 'lucide-svelte';
	import type { InboxEvent } from '$lib/adapter';

	interface Props {
		event: InboxEvent;
		onDismiss?: (id: number) => void;
	}
	let { event, onDismiss }: Props = $props();

	const borderColor = $derived(
		event.severity === 'critical'
			? 'var(--color-danger)'
			: event.severity === 'important'
				? 'var(--color-warning)'
				: 'var(--color-text-tertiary)'
	);

	function handleAction() {
		if (event.action_target) {
			void goto(event.action_target);
		}
	}

	function handleDismiss(e: MouseEvent) {
		e.stopPropagation();
		onDismiss?.(event.id);
	}

	function formatRelative(ts: number): string {
		const now = Math.floor(Date.now() / 1000);
		const delta = now - ts;
		if (delta < 60) return 'recién';
		if (delta < 3600) return `${Math.floor(delta / 60)}m`;
		if (delta < 86400) return `${Math.floor(delta / 3600)}h`;
		return `${Math.floor(delta / 86400)}d`;
	}
</script>

<div
	class="group relative flex items-start gap-3 rounded-[3px] border border-[var(--color-border)] border-l-[3px] bg-[var(--color-surface-1)] p-3 transition-colors hover:bg-[var(--color-surface-2)]"
	style:border-left-color={borderColor}
>
	<div class="flex-1 min-w-0">
		<div class="mb-1 flex items-center justify-between gap-2">
			<div class="flex min-w-0 items-center gap-2">
				<span
					class="text-display text-[9px] tracking-[0.16em] uppercase"
					style:color={borderColor}
				>
					{event.severity}
				</span>
				<span
					class="text-mono shrink-0 text-[9.5px] uppercase tracking-wide text-[var(--color-text-muted)]"
				>
					{event.module}
				</span>
				<span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">·</span>
				<span class="text-mono text-[9.5px] text-[var(--color-text-muted)]">
					{formatRelative(event.created_at)}
				</span>
			</div>
		</div>
		<div class="text-[12.5px] font-medium leading-snug text-[var(--color-text-primary)]">
			{event.title}
		</div>
		{#if event.description}
			<div class="mt-0.5 text-[11px] leading-snug text-[var(--color-text-secondary)]">
				{event.description}
			</div>
		{/if}
		{#if event.action_label && event.action_target}
			<button
				type="button"
				onclick={handleAction}
				class="text-mono mt-2 inline-block rounded-[3px] border border-[var(--color-terminal)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-terminal)] transition-colors hover:bg-[var(--color-terminal)] hover:text-[var(--color-bg)]"
			>
				{event.action_label}
			</button>
		{/if}
	</div>

	{#if onDismiss}
		<button
			type="button"
			onclick={handleDismiss}
			class="opacity-0 transition-opacity group-hover:opacity-60 hover:!opacity-100 text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
			title="Dismiss"
		>
			<X size={14} strokeWidth={1.8} />
		</button>
	{/if}
</div>

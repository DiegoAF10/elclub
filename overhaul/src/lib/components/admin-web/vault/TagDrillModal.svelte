<!--
	TagDrillModal — modal con la lista de jerseys que tienen un tag asignado.
	Carga adminWeb.list_jerseys_by_tag({ tag_id }).
-->
<script lang="ts">
	import { adminWeb } from '$lib/adapter';
	import { X } from 'lucide-svelte';

	interface Props {
		tag: { id: number; display_name: string; icon?: string };
		onClose: () => void;
	}
	let { tag, onClose }: Props = $props();

	let jerseys = $state<Record<string, unknown>[]>([]);
	let loading = $state(true);

	async function load() {
		loading = true;
		try {
			const list = await adminWeb.list_jerseys_by_tag({ tag_id: tag.id });
			jerseys = list as unknown as Record<string, unknown>[];
		} catch {
			jerseys = [];
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void load();
	});

	function handleBackdrop(e: MouseEvent) {
		if (e.target === e.currentTarget) onClose();
	}
	function handleKey(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

<svelte:window onkeydown={handleKey} />

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
	onclick={handleBackdrop}
	role="dialog"
	aria-modal="true"
	tabindex="-1"
>
	<div
		class="flex max-h-[80vh] w-full max-w-2xl flex-col rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] shadow-2xl"
	>
		<div
			class="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3"
		>
			<div class="flex items-center gap-2">
				{#if tag.icon}
					<span class="text-[16px]">{tag.icon}</span>
				{/if}
				<div>
					<div
						class="text-display text-[12px] tracking-[0.16em] text-[var(--color-text-primary)]"
					>
						{tag.display_name.toUpperCase()}
					</div>
					<div class="text-mono mt-0.5 text-[10px] text-[var(--color-text-muted)]">
						{loading ? 'cargando…' : `${jerseys.length} jerseys`}
					</div>
				</div>
			</div>
			<button
				type="button"
				onclick={onClose}
				class="text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
			>
				<X size={16} strokeWidth={1.8} />
			</button>
		</div>

		<div class="min-h-0 flex-1 overflow-y-auto p-4">
			{#if loading}
				<div class="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
					{#each Array(10) as _, i (i)}
						<div
							class="aspect-[3/4] animate-pulse rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)]"
						></div>
					{/each}
				</div>
			{:else if jerseys.length === 0}
				<div class="p-8 text-center text-[12px] text-[var(--color-text-muted)]">
					Ningún jersey tiene este tag asignado todavía.
				</div>
			{:else}
				<div class="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-5">
					{#each jerseys as j (j.family_id)}
						{@const hero = j.hero_thumbnail as string | null | undefined}
						{@const sku = String(j.sku ?? j.family_id)}
						{@const team = String(j.team ?? '')}
						<div
							class="overflow-hidden rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-2)]"
						>
							<div class="aspect-[3/4]">
								{#if hero}
									<img src={hero} alt={team} class="h-full w-full object-cover" loading="lazy" />
								{:else}
									<div
										class="flex h-full w-full items-center justify-center text-[10px] text-[var(--color-text-muted)]"
									>
										sin foto
									</div>
								{/if}
							</div>
							<div class="text-mono truncate p-1.5 text-[10px] text-[var(--color-text-primary)]" title={sku}>
								{sku}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</div>

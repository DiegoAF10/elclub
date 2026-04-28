<script lang="ts">
	import { adapter } from '$lib/adapter';
	import type { ExpenseCategory, PaymentMethod, Currency, ExpenseInput } from '$lib/data/finanzas';
	import { CATEGORY_LABELS } from '$lib/data/finanzas';

	let {
		onSaved,
		onCancel,
	}: {
		onSaved: () => void;
		onCancel: () => void;
	} = $props();

	function todayIso(): string {
		return new Date().toISOString().slice(0, 10);
	}

	let amount = $state<string>('');
	let currency = $state<Currency>('GTQ');
	let category = $state<ExpenseCategory | null>(null);
	let paymentMethod = $state<PaymentMethod | null>(null);
	let paidAt = $state<string>(todayIso());
	let notes = $state<string>('');
	let saving = $state(false);
	let error = $state<string | null>(null);

	const FX_DEFAULT = 7.73;

	let amountNum = $derived.by(() => {
		const n = parseFloat(amount);
		return isNaN(n) ? null : n;
	});

	let canSubmit = $derived(
		amountNum !== null &&
		amountNum > 0 &&
		category !== null &&
		paymentMethod !== null &&
		paidAt !== ''
	);

	let convertedGtq = $derived(
		currency === 'USD' && amountNum !== null ? amountNum * FX_DEFAULT : null
	);

	const CATEGORIES: ExpenseCategory[] = ['variable', 'tech', 'marketing', 'operations', 'owner_draw', 'other'];

	async function handleSubmit() {
		if (!canSubmit || saving || !category || !paymentMethod || amountNum === null) return;
		saving = true;
		error = null;
		try {
			const input: ExpenseInput = {
				amount_native: amountNum,
				currency,
				category,
				payment_method: paymentMethod,
				paid_at: paidAt,
				notes: notes.trim() || undefined,
			};
			await adapter.createExpense(input);
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
			saving = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			onCancel();
		} else if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
			e.preventDefault();
			handleSubmit();
		}
	}
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-[6px] p-6 max-w-[520px] mx-auto">
	<div class="text-mono text-[12px] font-semibold text-[var(--color-text-primary)] mb-4 pb-3 border-b border-[var(--color-surface-2)]" style="letter-spacing: 0.05em;">
		+ Nuevo gasto
	</div>

	<!-- Monto + currency -->
	<div class="mb-4">
		<label class="block text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;" for="gasto-amount">
			Monto
		</label>
		<div class="flex gap-2">
			<input
				id="gasto-amount"
				type="number"
				step="0.01"
				min="0"
				bind:value={amount}
				placeholder="0.00"
				autofocus
				class="flex-1 px-3 py-2.5 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px] text-mono text-[20px] font-bold tabular-nums text-right text-[var(--color-live)] focus:outline-none focus:border-[var(--color-accent)]"
			/>
			<button
				type="button"
				class="text-mono text-[11px] px-3 rounded-[3px] border transition-colors"
				class:bg-[var(--color-surface-2)]={currency !== 'GTQ'}
				class:text-[var(--color-text-secondary)]={currency !== 'GTQ'}
				class:border-[var(--color-border)]={currency !== 'GTQ'}
				class:!bg-[rgba(91,141,239,0.16)]={currency === 'GTQ'}
				class:!text-[var(--color-accent)]={currency === 'GTQ'}
				class:!border-[rgba(91,141,239,0.4)]={currency === 'GTQ'}
				onclick={() => currency = 'GTQ'}
			>
				Q
			</button>
			<button
				type="button"
				class="text-mono text-[11px] px-3 rounded-[3px] border transition-colors"
				class:bg-[var(--color-surface-2)]={currency !== 'USD'}
				class:text-[var(--color-text-secondary)]={currency !== 'USD'}
				class:border-[var(--color-border)]={currency !== 'USD'}
				class:!bg-[rgba(91,141,239,0.16)]={currency === 'USD'}
				class:!text-[var(--color-accent)]={currency === 'USD'}
				class:!border-[rgba(91,141,239,0.4)]={currency === 'USD'}
				onclick={() => currency = 'USD'}
			>
				USD
			</button>
		</div>
		{#if convertedGtq !== null}
			<div class="text-mono text-[10px] text-[var(--color-text-tertiary)] mt-1.5">
				≈ Q{convertedGtq.toFixed(2)} (FX {FX_DEFAULT})
			</div>
		{/if}
	</div>

	<!-- Categoría -->
	<div class="mb-4">
		<div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
			Categoría · 1 click
		</div>
		<div class="grid grid-cols-3 gap-1.5">
			{#each CATEGORIES as cat (cat)}
				{@const isOwnerDraw = cat === 'owner_draw'}
				{@const isActive = category === cat}
				<button
					type="button"
					class="text-mono text-[11px] px-2.5 py-2 rounded-[3px] border transition-colors"
					class:bg-[var(--color-surface-2)]={!isActive && !isOwnerDraw}
					class:text-[var(--color-text-secondary)]={!isActive && !isOwnerDraw}
					class:border-[var(--color-border)]={!isActive}
					class:!bg-[rgba(91,141,239,0.16)]={isActive}
					class:!text-[var(--color-accent)]={isActive}
					class:!border-[rgba(91,141,239,0.4)]={isActive}
					class:opacity-40={isOwnerDraw}
					class:cursor-not-allowed={isOwnerDraw}
					disabled={isOwnerDraw}
					title={isOwnerDraw ? 'Owner draw vive en tab Inter-cuenta · no acá' : ''}
					onclick={() => { if (!isOwnerDraw) category = cat; }}
				>
					{CATEGORY_LABELS[cat]}
				</button>
			{/each}
		</div>
	</div>

	<!-- Payment method -->
	<div class="mb-4">
		<div class="text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;">
			Pagado con · 1 click
		</div>
		<div class="grid grid-cols-2 gap-2">
			<button
				type="button"
				class="px-3 py-3 rounded-[3px] border text-center transition-colors"
				class:bg-[var(--color-surface-2)]={paymentMethod !== 'tdc_personal'}
				class:border-[var(--color-border)]={paymentMethod !== 'tdc_personal'}
				class:!bg-[rgba(91,141,239,0.10)]={paymentMethod === 'tdc_personal'}
				class:!border-[rgba(91,141,239,0.4)]={paymentMethod === 'tdc_personal'}
				onclick={() => paymentMethod = 'tdc_personal'}
			>
				<div class="text-[20px]" aria-hidden="true">💳</div>
				<div class="text-mono text-[10px] mt-1 text-[var(--color-text-secondary)]" style="letter-spacing: 0.04em;">TDC PERSONAL</div>
				<div class="text-mono text-[8.5px] mt-0.5 text-[var(--color-text-tertiary)]">crece shareholder loan</div>
			</button>
			<button
				type="button"
				class="px-3 py-3 rounded-[3px] border text-center transition-colors"
				class:bg-[var(--color-surface-2)]={paymentMethod !== 'cuenta_business'}
				class:border-[var(--color-border)]={paymentMethod !== 'cuenta_business'}
				class:!bg-[rgba(91,141,239,0.10)]={paymentMethod === 'cuenta_business'}
				class:!border-[rgba(91,141,239,0.4)]={paymentMethod === 'cuenta_business'}
				onclick={() => paymentMethod = 'cuenta_business'}
			>
				<div class="text-[20px]" aria-hidden="true">🏦</div>
				<div class="text-mono text-[10px] mt-1 text-[var(--color-text-secondary)]" style="letter-spacing: 0.04em;">CUENTA BUSINESS</div>
				<div class="text-mono text-[8.5px] mt-0.5 text-[var(--color-text-tertiary)]">resta del cash business</div>
			</button>
		</div>
	</div>

	<!-- Fecha + notas -->
	<div class="grid grid-cols-2 gap-3 mb-4">
		<div>
			<label class="block text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;" for="gasto-paidat">
				Fecha · default hoy
			</label>
			<input
				id="gasto-paidat"
				type="date"
				bind:value={paidAt}
				class="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px] text-mono text-[12px] text-[var(--color-text-secondary)] focus:outline-none focus:border-[var(--color-accent)]"
			/>
		</div>
		<div>
			<label class="block text-mono text-[9.5px] uppercase mb-1.5 text-[var(--color-text-tertiary)]" style="letter-spacing: 0.08em;" for="gasto-notes">
				Notas · opcional
			</label>
			<input
				id="gasto-notes"
				type="text"
				bind:value={notes}
				placeholder="ej. Anthropic API · bot abril"
				class="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-[3px] text-mono text-[12px] text-[var(--color-text-primary)] focus:outline-none focus:border-[var(--color-accent)]"
			/>
		</div>
	</div>

	{#if error}
		<div class="text-mono text-[11px] text-[var(--color-danger)] mb-3 p-2 bg-[rgba(244,63,94,0.06)] border border-[rgba(244,63,94,0.2)] rounded-[3px]">
			⚠ {error}
		</div>
	{/if}

	<div class="flex gap-2 pt-3 border-t border-[var(--color-surface-2)]">
		<button
			type="button"
			class="flex-1 text-mono text-[11px] py-2.5 bg-transparent text-[var(--color-text-secondary)] border border-[var(--color-border)] rounded-[3px] hover:bg-[var(--color-surface-2)] transition-colors"
			onclick={onCancel}
		>
			Cancelar
		</button>
		<button
			type="button"
			class="flex-1 text-mono text-[12px] font-bold py-2.5 bg-[var(--color-live)] text-[var(--color-bg)] rounded-[3px] disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
			disabled={!canSubmit || saving}
			onclick={handleSubmit}
		>
			{saving ? 'Guardando…' : 'Guardar gasto'}
		</button>
	</div>

	<div class="text-mono text-[9px] text-[var(--color-text-tertiary)] mt-3 text-right" style="letter-spacing: 0.05em;">
		Esc cancela · ⌘/Ctrl+Enter guarda
	</div>
</div>

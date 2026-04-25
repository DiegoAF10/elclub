<script lang="ts">
	import type { Family, Modelo, Photo } from '$lib/data/types';
	import {
		Check,
		X,
		Flag,
		SkipForward,
		Shuffle,
		DoorOpen,
		Trash2,
		ExternalLink,
		Sparkles,
		Paintbrush,
		Brush,
		Crown,
		Command,
		Upload,
		Star,
		Eye,
		EyeOff,
		Archive,
		PackageX,
		Copy,
		FileJson,
		Files,
		History,
		ChevronRight,
		GripVertical,
		Loader2,
		AlertTriangle,
		ChevronLeft,
		Maximize2
	} from 'lucide-svelte';
	import StatusBadge from './StatusBadge.svelte';
	import MoveModeloModal from './MoveModeloModal.svelte';
	import EditModeloPanel from './EditModeloPanel.svelte';
	import { dndzone } from 'svelte-dnd-action';
	import { adapter, NotAvailableInBrowser } from '$lib/adapter';
	import { validateForPublish } from '$lib/data/publishValidation';

	interface Props {
		family: Family | null;
		modelo: Modelo | null;
		families?: Family[];
		onSelectSku?: (sku: string) => void;
		onFlash?: (msg: string) => void;
		onRefresh?: () => void;
	}

	let {
		family,
		modelo,
		families = [],
		onSelectSku = () => {},
		onFlash = () => {},
		onRefresh = () => {}
	}: Props = $props();

	// Move modal state
	let moveModalOpen = $state(false);

	// Edit modelo type/sleeve panel state — inline en el header, reemplaza
	// los 3 window.prompt encadenados que existían pre-v0.1.22.
	let editPanelOpen = $state(false);

	// Cerrar el panel cuando cambia de modelo (evita estado inconsistente
	// si Diego clickea otro SKU mientras el panel está abierto).
	$effect(() => {
		// Track modelo.sku — cuando cambia, colapsamos
		void modelo?.sku;
		editPanelOpen = false;
	});

	// Photo op state: photo.id → 'busy' | 'error' | null
	let photoOps = $state<Record<string, 'busy' | 'error' | null>>({});

	async function runWatermark(photoIdx: number, mode: 'auto' | 'force' | 'gemini') {
		if (!family || !modelo) return;
		const photo = modelo.fotos[photoIdx];
		if (!photo) return;
		if (photoOps[photo.id] === 'busy') return;

		photoOps = { ...photoOps, [photo.id]: 'busy' };
		const modeLabel = mode === 'gemini' ? 'Gemini' : mode === 'force' ? 'Force' : 'Auto';
		onFlash(`${modeLabel} · foto ${photoIdx + 1} · procesando…`);

		try {
			// Resolver modelo_idx dentro de family.modelos
			const modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
			if (modeloIdx < 0) throw new Error('modelo no encontrado en family');

			const result = await adapter.invokeWatermark({
				family_id: family.id,
				modelo_idx: modeloIdx,
				photo_idx: photoIdx,
				mode
			});

			if (result.ok && result.new_url) {
				photoOps = { ...photoOps, [photo.id]: null };
				onFlash(`✓ ${modeLabel} · foto ${photoIdx + 1} limpia`);
				// Python ya escribió catalog.json — refresh para que la UI lea los nuevos URLs
				onRefresh();
			} else {
				photoOps = { ...photoOps, [photo.id]: 'error' };
				onFlash(`✗ ${modeLabel} falló: ${result.error ?? 'error desconocido'}`);
				setTimeout(() => {
					photoOps = { ...photoOps, [photo.id]: null };
				}, 3000);
			}
		} catch (err) {
			photoOps = { ...photoOps, [photo.id]: 'error' };
			if (err instanceof NotAvailableInBrowser) {
				onFlash(`${modeLabel}: requiere el .exe (subprocess Python)`);
			} else {
				onFlash(`${modeLabel} falló: ${err instanceof Error ? err.message : err}`);
			}
			setTimeout(() => {
				photoOps = { ...photoOps, [photo.id]: null };
			}, 3000);
		}
	}

	const MODELO_LABEL: Record<string, string> = {
		fan_adult: 'Fan adulto',
		player_adult: 'Player adulto',
		retro_adult: 'Retro',
		woman: 'Mujer',
		kid: 'Niño',
		baby: 'Bebé',
		goalkeeper: 'Goalkeeper'
	};

	const SLEEVE_LABEL: Record<string, string> = { short: 'Manga corta', long: 'Manga larga' };

	// Override state para drag-to-reorder (visible durante drag activo).
	// Se declara ANTES del $derived para que lo pueda leer.
	let photosOverride = $state<Photo[] | null>(null);

	// Fotos de la galería — derived de modelo.fotos (source of truth),
	// con override temporal durante drag.
	let localPhotos = $derived<Photo[]>(
		photosOverride !== null ? photosOverride : modelo?.fotos ? [...modelo.fotos] : []
	);
	let currentSku = $state<string | null>(null);
	// Signature legacy (kept para compat con lightbox $effect)
	let currentPhotoSig = $state<string>('');

	// Lightbox — foto ampliada fullscreen
	let lightboxIdx = $state<number | null>(null);

	// Multi-select — ctrl/shift+click selecciona fotos para batch actions
	let selectedPhotoIdxs = $state<Set<number>>(new Set());
	let lastSelectedIdx = $state<number | null>(null);

	function togglePhotoSelection(idx: number, event: MouseEvent) {
		const isModifier = event.ctrlKey || event.metaKey;
		const isShift = event.shiftKey;
		const next = new Set(selectedPhotoIdxs);

		if (isShift && lastSelectedIdx !== null) {
			// Range select from lastSelected to idx
			const [start, end] =
				lastSelectedIdx < idx ? [lastSelectedIdx, idx] : [idx, lastSelectedIdx];
			for (let i = start; i <= end; i++) next.add(i);
		} else if (isModifier) {
			if (next.has(idx)) next.delete(idx);
			else next.add(idx);
		} else {
			// Plain click without modifiers: NO es multi-select → abrir lightbox
			// (caller decide; acá solo manejamos multi-select path)
			return false;
		}
		selectedPhotoIdxs = next;
		lastSelectedIdx = idx;
		return true; // consumió el click
	}

	function clearPhotoSelection() {
		selectedPhotoIdxs = new Set();
		lastSelectedIdx = null;
	}

	// Reset selection cuando cambia el modelo
	$effect(() => {
		if (currentSku) {
			selectedPhotoIdxs = new Set();
			lastSelectedIdx = null;
		}
	});

	async function deleteSelectedPhotos() {
		if (!family || !modelo || selectedPhotoIdxs.size === 0) return;
		const count = selectedPhotoIdxs.size;

		// Dialog con 2 opciones:
		//   OK      → borrar del catalog + R2 (libera espacio)
		//   Cancel  → no hacer nada
		// Hold Shift mientras confirmás → keep R2 (fallback opción antigua)
		const alsoDeleteR2 = window.confirm(
			`Borrar ${count} foto${count !== 1 ? 's' : ''} del modelo ${modelo.sku}?\n\n` +
				`✓ Se removerán del gallery en catalog.json.\n` +
				`✓ También se borrarán de R2 (libera espacio).\n\n` +
				`Clickeá CANCELAR si preferís mantener los archivos R2 (solo desasociar).`
		);

		// Si cancelan, ofrecemos opción "solo catalog" (no R2)
		let doCatalogOnly = false;
		if (!alsoDeleteR2) {
			doCatalogOnly = window.confirm(
				`¿Querés borrar solo del catalog (sin tocar R2)?\n\n` +
					`Los archivos R2 quedarían como orphan (ocupan espacio pero no se ven en el vault).`
			);
			if (!doCatalogOnly) return; // totalmente cancelado
		}

		const modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
		if (modeloIdx < 0) return;

		try {
			const result = await adapter.removeModeloPhotos(
				family.id,
				modeloIdx,
				[...selectedPhotoIdxs].sort((a, b) => a - b),
				alsoDeleteR2
			);
			const parts = [`${result.removed_from_catalog} del catalog`];
			if (result.deleted_from_r2 > 0) parts.push(`${result.deleted_from_r2} de R2`);
			if (result.r2_failed > 0) parts.push(`${result.r2_failed} R2 fallaron`);
			onFlash(`✓ Borrado: ${parts.join(' · ')}`);
			if (result.r2_errors.length > 0) console.warn('[r2-delete] errors:', result.r2_errors);
			clearPhotoSelection();
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Borrar fotos: requiere el .exe');
			} else {
				onFlash(`Borrar falló: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	async function cleanSelectedWithGemini() {
		if (!family || !modelo || selectedPhotoIdxs.size === 0) return;
		const count = selectedPhotoIdxs.size;
		const confirmed = window.confirm(
			`Limpiar ${count} foto${count !== 1 ? 's' : ''} con Gemini 2.5?\n\n` +
				`Tarda ~10s por foto. Backup automático.`
		);
		if (!confirmed) return;

		const modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
		if (modeloIdx < 0) return;

		const sortedIdxs = [...selectedPhotoIdxs].sort((a, b) => a - b);
		let cleaned = 0;
		let failed = 0;
		for (const idx of sortedIdxs) {
			const photo = modelo.fotos[idx];
			if (!photo) continue;
			photoOps = { ...photoOps, [photo.id]: 'busy' };
			onFlash(`🪄 Gemini ${idx + 1}/${sortedIdxs.length}…`);
			try {
				const result = await adapter.invokeWatermark({
					family_id: family.id,
					modelo_idx: modeloIdx,
					photo_idx: idx,
					mode: 'gemini'
				});
				if (result.ok) {
					cleaned++;
				} else {
					failed++;
				}
			} catch {
				failed++;
			} finally {
				photoOps = { ...photoOps, [photo.id]: null };
			}
		}
		onFlash(`✓ Gemini batch: ${cleaned} limpias, ${failed} fallaron`);
		clearPhotoSelection();
		onRefresh();
	}

	function openLightbox(idx: number) {
		lightboxIdx = idx;
	}
	function closeLightbox() {
		lightboxIdx = null;
	}
	function lightboxPrev() {
		if (lightboxIdx === null || localPhotos.length === 0) return;
		lightboxIdx = (lightboxIdx - 1 + localPhotos.length) % localPhotos.length;
	}
	function lightboxNext() {
		if (lightboxIdx === null || localPhotos.length === 0) return;
		lightboxIdx = (lightboxIdx + 1) % localPhotos.length;
	}

	function handleLightboxKey(e: KeyboardEvent) {
		if (lightboxIdx === null) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			closeLightbox();
		} else if (e.key === 'ArrowLeft') {
			e.preventDefault();
			lightboxPrev();
		} else if (e.key === 'ArrowRight') {
			e.preventDefault();
			lightboxNext();
		}
	}

	// Cuando cambia el modelo, cerrar el lightbox (evita estado stale)
	$effect(() => {
		if (currentSku !== null) {
			lightboxIdx = null;
		}
	});

	// Track currentSku for selection reset effects (resolves to modelo.sku via derived)
	$effect(() => {
		if (modelo) {
			currentSku = modelo.sku;
			currentPhotoSig = modelo.fotos.map((p) => p.url).join('|');
		}
	});

	// ─── Gallery reorder (drag within same modelo) ────────────────────
	// `photosOverride` se declara arriba (junto a localPhotos). Al terminar
	// drag: commit al catalog via updateGalleryOrder; override se resetea y
	// el $derived vuelve a leer de modelo.fotos post-refresh.

	function handleDndConsider(e: CustomEvent<{ items: Photo[] }>) {
		photosOverride = e.detail.items;
	}

	async function handleDndFinalize(e: CustomEvent<{ items: Photo[] }>) {
		photosOverride = e.detail.items;
		if (!family || !modelo) return;
		const modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
		if (modeloIdx < 0) return;
		// Derivar el nuevo orden de URLs para persistir al catalog
		const newUrlOrder = e.detail.items.map((p) => p.url);
		try {
			await adapter.updateGalleryOrder(family.id, modeloIdx, newUrlOrder);
			onFlash('✓ Orden actualizado · hero = foto #1');
			photosOverride = null; // dejar que $derived reconstruya desde modelo
			onRefresh();
		} catch (err) {
			photosOverride = null; // revert visual
			if (err instanceof NotAvailableInBrowser) onFlash('Reorder: requiere .exe');
			else onFlash(`Reorder falló: ${err instanceof Error ? err.message : err}`);
		}
	}

	// Keep the old handleDnd alias for Svelte onconsider/onfinalize compat
	function handleDnd(e: CustomEvent<{ items: Photo[] }>) {
		handleDndConsider(e);
	}

	// ─── Publicar family (flow completo) ────────────────────────────────
	// Precios default por tipo — duplicado de transform.DEFAULT_PRICE_BY_TYPE
	// para backfill al momento del publish. Si modelo tiene price null/0 en
	// catalog, lo seteamos antes de push para que el vault live no muestre NaN.
	const DEFAULT_PRICE_BY_TYPE_UI: Record<string, number> = {
		fan_adult: 435,
		player_adult: 435,
		retro_adult: 435,
		woman: 435,
		goalkeeper: 435,
		adult: 435,
		kid: 275,
		baby: 250,
		polo: 435,
		vest: 435,
		training: 435,
		sweatshirt: 435,
		jacket: 435,
		shorts: 435
	};

	let publishState = $state<'idle' | 'busy'>('idle');
	async function handlePublishFamily() {
		if (!family || publishState === 'busy') return;
		publishState = 'busy';
		onFlash(`📦 Publicando ${family.id}…`);
		try {
			// 0. Backfill precios: para cualquier modelo con price null/0, persistir
			//    el default según tipo. Esto fixea el "QNaN" del vault live.
			const modelosNeedingPrice: Array<{ idx: number; sku: string; price: number }> = [];
			family.modelos.forEach((m, idx) => {
				const current = m.price;
				if (!current || current <= 0) {
					const def = DEFAULT_PRICE_BY_TYPE_UI[m.modeloType] ?? 435;
					modelosNeedingPrice.push({ idx, sku: m.sku, price: def });
				}
			});
			for (const { idx, price } of modelosNeedingPrice) {
				await adapter.setModeloField(family.id, idx, 'price', price);
			}
			if (modelosNeedingPrice.length > 0) {
				onFlash(`💰 Backfill ${modelosNeedingPrice.length} precios → Publicando…`);
			}

			// 1. Marcar todos los modelos como final_verified=1
			for (const m of family.modelos) {
				await adapter.setFinalVerified(m.sku, true);
			}
			// 2. published=true en catalog
			await adapter.setFamilyPublished(family.id, true);
			// 3. Commit + push
			const msg = `Publish: ${family.team} ${family.season} ${family.variantLabel}`;
			const result = await adapter.commitAndPush(msg);
			if (result.ok && result.pushed) {
				onFlash(`✓ ${family.id} publicado → vault live en ~30s · ${result.commit_sha ?? ''}`);
			} else if (result.nothing_to_commit) {
				onFlash(`✓ ${family.id} publicado (nothing new to commit)`);
			} else if (!result.pushed) {
				onFlash(`⚠ Commit ${result.commit_sha ?? ''} local ok, push falló: ${result.error ?? ''}`);
			}
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) onFlash('Publicar: requiere .exe');
			else onFlash(`Publicar falló: ${err instanceof Error ? err.message : err}`);
		} finally {
			publishState = 'idle';
		}
	}

	// ─── Decisiones (Verify/Flag/Skip clicks) ──────────────────────────
	type UIDecision = 'verified' | 'flagged' | 'skipped';
	async function triggerDecision(status: UIDecision, label: string) {
		if (!modelo) {
			onFlash(`${label}: seleccioná un SKU primero`);
			return;
		}
		const sku = modelo.sku;
		try {
			await adapter.setDecisionStatus(sku, status);
			onFlash(`${label} · ${sku}`);
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash(`${label}: requiere el .exe — browser es read-only`);
			} else {
				onFlash(`${label} falló: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	// Validación pre-publish (L1) — block/warn/info
	// Reemplaza el `checks` legacy. Se computa contra la family + primary modelo
	// (el visible en el card del vault). Si no hay primary explícito, usa el
	// modelo seleccionado actualmente.
	let validation = $derived.by(() => {
		if (!family || !modelo) return null;
		const primaryIdx = family.primaryModeloIdx ?? 0;
		const primary = family.modelos[primaryIdx] ?? modelo;
		return validateForPublish(family, primary);
	});

	let familyReady = $derived.by(() => {
		if (!family) return { ready: false, total: 0, verified: 0 };
		const total = family.modelos.length;
		const verified = family.modelos.filter(
			(m) => m.status === 'live' || m.status === 'ready'
		).length;
		return { ready: total > 0 && verified === total, total, verified };
	});

	async function copyToClipboard(text: string) {
		try {
			await navigator.clipboard.writeText(text);
		} catch (e) {
			console.error('clipboard fail', e);
		}
	}

	// ─── Specs editing: variant / price / sizes ────────────────────────
	const VARIANT_OPTIONS = [
		{ value: 'home', label: 'Local' },
		{ value: 'away', label: 'Visita' },
		{ value: 'third', label: 'Tercera' },
		{ value: 'goalkeeper', label: 'Portero' },
		{ value: 'special', label: 'Especial' },
		{ value: 'training', label: 'Entrenamiento' },
		{ value: 'fourth', label: 'Cuarta' },
		{ value: 'anniversary', label: 'Aniversario' },
		{ value: 'windbreaker', label: 'Windbreaker' },
		{ value: 'retro', label: 'Retro' },
		{ value: 'originals', label: 'Originals' },
		{ value: 'concept', label: 'Concept' },
		{ value: 'limited', label: 'Limitada' }
	];

	const SIZES_PRESETS = [
		'S-M',
		'S-L',
		'S-XL',
		'S-XXL',
		'S-3XL',
		'S-4XL',
		'S-5XL',
		'16-28',
		'XS-S',
		'M-L',
		'L-XL'
	];

	async function changeFamilyVariant(newVariant: string) {
		if (!family || newVariant === family.variant) return;
		const label = VARIANT_OPTIONS.find((v) => v.value === newVariant)?.label;
		try {
			const result = await adapter.setFamilyVariant(family.id, newVariant, label);
			if (result.ok) {
				const migCount = result.migrated
					? result.migrated.audit_decisions + result.migrated.audit_photo_actions
					: 0;
				onFlash(
					`✓ Variant → ${label || newVariant}${migCount ? ` · ${migCount} rows migradas` : ''}`
				);
				onRefresh();
			} else {
				onFlash(`✗ Variant falló: ${result.error ?? 'unknown'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) onFlash('Variant: requiere .exe');
			else onFlash(`Variant falló: ${err instanceof Error ? err.message : err}`);
		}
	}

	async function changeModeloField(field: 'price' | 'sizes' | 'notes', value: string | number) {
		if (!family || !modelo) return;
		const modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
		if (modeloIdx < 0) return;

		const current = modelo[field as keyof typeof modelo];
		if (String(current ?? '') === String(value ?? '')) return; // sin cambios

		const normalizedValue =
			field === 'price' ? (typeof value === 'number' ? value : parseInt(String(value), 10) || 0) : value;

		try {
			await adapter.setModeloField(family.id, modeloIdx, field, normalizedValue);
			onFlash(`✓ ${field} actualizado`);
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) onFlash(`${field}: requiere .exe`);
			else onFlash(`${field} falló: ${err instanceof Error ? err.message : err}`);
		}
	}

	type FamilyFlag = 'published' | 'featured' | 'archived';
	async function toggleFamilyFlag(flag: FamilyFlag) {
		if (!family) return;
		const current = flag === 'published' ? family.published : flag === 'featured' ? !!family.featured : !!family.archived;
		const next = !current;
		const label = flag === 'published' ? 'Publicado' : flag === 'featured' ? 'Featured' : 'Archivado';
		try {
			if (flag === 'published') await adapter.setFamilyPublished(family.id, next);
			else if (flag === 'featured') await adapter.setFamilyFeatured(family.id, next);
			else await adapter.setFamilyArchived(family.id, next);
			onFlash(`✓ ${label} · ${next ? 'ON' : 'OFF'}`);
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash(`${label}: requiere el .exe`);
			} else {
				onFlash(`${label} falló: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	async function handleDelete() {
		if (!family || !modelo) return;
		const motivo = window.prompt(
			`Borrar SKU ${modelo.sku}?\n\n` +
				`Esto hace soft-delete: marca status='deleted' en audit_decisions, ` +
				`remueve el modelo del catalog.json, y si estaba publicado, hace commit+push ` +
				`para bajarlo del vault.\n\n` +
				`Explicá por qué (motivo):`
		);
		if (!motivo || !motivo.trim()) return;

		onFlash(`🗑 Borrando ${modelo.sku}…`);
		try {
			const result = await adapter.deleteSku(modelo.sku, motivo.trim());
			if (result.ok) {
				const extra = result.family_deleted ? ' + family entero eliminado' : '';
				const committed = result.committed ? ' · pushed al vault' : '';
				onFlash(`✓ ${modelo.sku} borrado${extra}${committed}`);
				onRefresh();
			} else {
				onFlash(`✗ Delete falló: ${result.error ?? 'error desconocido'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Delete: requiere el .exe');
			} else {
				onFlash(`Delete falló: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	function handleMover() {
		moveModalOpen = true;
	}

	function handleHuerfano() {
		// Huérfano = "mover a family nueva" preselected con team/season del source
		// → solo abre el modal en tab "nueva"
		moveModalOpen = true;
	}

	// Edit modelo type/sleeve: lógica vive en EditModeloPanel.svelte (inline UI).
	// Trigger del chip togglea editPanelOpen — declarado arriba.

	// Auto-fix backfill: corre backfill_catalog_meta.py vía bridge para llenar
	// meta_country, meta_confederation, wc2026_eligible cuando faltan.
	// Resuelve los 3 issues "fixable" del L1 validator sin terminal.
	const BACKFILL_FIXABLE_KINDS = new Set([
		'meta-country-missing',
		'meta-confederation-missing',
		'wc2026-not-eligible'
	]);
	let backfillState = $state<'idle' | 'busy'>('idle');

	async function handleBackfillMeta() {
		if (backfillState === 'busy') return;
		backfillState = 'busy';
		onFlash('Backfill meta corriendo…');
		try {
			const result = await adapter.backfillMeta();
			if (result.ok) {
				const stats = result.stats || {};
				const filled =
					(stats.meta_country_set ?? 0) +
					(stats.meta_confederation_set ?? 0) +
					(stats.wc2026_eligible_set ?? 0);
				if (filled > 0) {
					onFlash(`✓ Backfill: ${filled} campos llenos`);
				} else {
					onFlash('Backfill: nada que llenar (data ya OK)');
				}
				onRefresh();
			} else {
				onFlash(`✗ Backfill falló: ${result.error ?? 'error desconocido'}`);
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Backfill: requiere el .exe');
			} else {
				onFlash(`Backfill falló: ${err instanceof Error ? err.message : err}`);
			}
		} finally {
			backfillState = 'idle';
		}
	}

	// Batch clean — scope: modelo (solo actual) o family (todos los modelos)
	let batchCleanState = $state<'idle' | 'busy'>('idle');
	// Progress streaming desde Python bridge → Tauri event 'bridge-progress'
	let batchProgress = $state<{
		current: number;
		total: number;
		modelo_idx?: number;
		photo_idx?: number;
	} | null>(null);

	$effect(() => {
		let unlisten: (() => void) | null = null;
		(async () => {
			try {
				const { listen } = await import('@tauri-apps/api/event');
				unlisten = await listen<{
					op?: string;
					stage?: string;
					current?: number;
					total?: number;
					modelo_idx?: number;
					photo_idx?: number;
				}>('bridge-progress', (event) => {
					const p = event.payload;
					if (p.op === 'batch_clean') {
						if (p.stage === 'start') {
							batchProgress = { current: 0, total: p.total ?? 0 };
						} else if (p.stage === 'processing') {
							batchProgress = {
								current: p.current ?? 0,
								total: p.total ?? 0,
								modelo_idx: p.modelo_idx,
								photo_idx: p.photo_idx
							};
						} else if (p.stage === 'done') {
							batchProgress = null;
						}
					}
				});
			} catch {
				// browser mode — no Tauri event API
			}
		})();
		return () => unlisten?.();
	});

	async function handleBatchClean(scope: 'modelo' | 'family') {
		if (!family || batchCleanState === 'busy') return;

		let dirtyCount = 0;
		let modeloIdx: number | undefined;
		if (scope === 'modelo') {
			if (!modelo) return;
			modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
			if (modeloIdx < 0) return;
			dirtyCount = modelo.fotos.filter((f) => f.isDirty).length;
		} else {
			dirtyCount = family.modelos.reduce(
				(sum, m) => sum + m.fotos.filter((f) => f.isDirty).length,
				0
			);
		}

		if (dirtyCount === 0) {
			onFlash(scope === 'modelo' ? 'Sin fotos DIRTY en este modelo' : 'Sin fotos DIRTY en el family');
			return;
		}

		const label = scope === 'modelo' ? `modelo ${modelo?.sku}` : `family ${family.id}`;
		const confirmed = window.confirm(
			`Limpiar ${dirtyCount} fotos DIRTY del ${label} con LaMa auto-detect?\n\n` +
				`Tarda ~3-5s por foto. Backup automático.`
		);
		if (!confirmed) return;

		batchCleanState = 'busy';
		onFlash(`🧹 Limpiando ${dirtyCount} del ${label}…`);
		try {
			const result = await adapter.batchCleanFamily(family.id, modeloIdx);
			if (result.ok) {
				const parts = [`${result.cleaned} limpias`];
				if (result.skipped > 0) parts.push(`${result.skipped} skipped`);
				if (result.failed > 0) parts.push(`${result.failed} fallaron`);
				onFlash(`✓ Batch clean: ${parts.join(' · ')}`);
				if (result.errors.length > 0) console.warn('[batch-clean] errors:', result.errors);
				onRefresh();
			} else {
				onFlash('✗ Batch clean falló');
			}
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Batch clean: requiere el .exe');
			} else {
				onFlash(`Batch clean falló: ${err instanceof Error ? err.message : err}`);
			}
		} finally {
			batchCleanState = 'idle';
		}
	}

	async function toggleSoldOut() {
		if (!family || !modelo) return;
		const modeloIdx = family.modelos.findIndex((m) => m.sku === modelo.sku);
		if (modeloIdx < 0) return;
		const next = !modelo.soldOut;
		try {
			await adapter.setModeloSoldOut(family.id, modeloIdx, next);
			onFlash(`✓ Sold out · ${next ? 'YES' : 'NO'}`);
			onRefresh();
		} catch (err) {
			if (err instanceof NotAvailableInBrowser) {
				onFlash('Sold out: requiere el .exe');
			} else {
				onFlash(`Sold out falló: ${err instanceof Error ? err.message : err}`);
			}
		}
	}
</script>

<section class="flex h-full flex-1 flex-col bg-[var(--color-bg)]">
	{#if !family || !modelo}
		<div
			class="flex h-full flex-col items-center justify-center gap-4 text-[var(--color-text-tertiary)]"
		>
			<Command size={32} strokeWidth={1.2} class="opacity-30" />
			<div class="text-[12px]">Seleccioná un SKU del panel izquierdo</div>
			<div class="flex items-center gap-1.5 text-[11px]">
				o apretá <kbd>⌘K</kbd> para buscar
			</div>
		</div>
	{:else}
		<!-- Header con bandera grande -->
		<header
			class="ui-chrome flex h-16 shrink-0 items-center justify-between border-b border-[var(--color-border)] px-6"
		>
			<div class="flex items-center gap-3">
				{#if family.flagIso}
					<img
						src="/flags/{family.flagIso}.svg"
						alt=""
						class="h-8 w-11 rounded-[3px] shadow-[0_0_0_1px_rgba(255,255,255,0.08)]"
					/>
				{/if}
				<div class="flex flex-col gap-0.5">
					<div class="flex items-center gap-2.5">
						<span class="text-[14.5px] font-semibold text-[var(--color-text-primary)]">
							{family.team}
							<span class="text-[var(--color-text-tertiary)]">·</span>
							{family.season}
							<span class="text-[var(--color-text-tertiary)]">·</span>
							{family.variantLabel}
						</span>
						<StatusBadge status={modelo.status} />
						{#if family.featured}
							<span
								class="text-display flex items-center gap-1 rounded-[3px] bg-[var(--color-warning)]/15 px-1.5 py-0.5 text-[9.5px] text-[var(--color-warning)]"
							>
								<Star size={9} strokeWidth={2.2} fill="currentColor" />
								TOP
							</span>
						{/if}
					</div>
					<div class="flex items-center gap-2 text-[10.5px] text-[var(--color-text-tertiary)]">
						<span class="text-mono font-semibold text-[var(--color-text-secondary)]"
							>{modelo.sku}</span
						>
						<span class="text-[var(--color-text-muted)]">·</span>
						<button
							type="button"
							onclick={() => (editPanelOpen = !editPanelOpen)}
							title="Editar type / sleeve (regenera SKU)"
							class="flex items-center gap-1.5 rounded-[3px] border border-dashed px-1 py-0.5 transition-colors {editPanelOpen
								? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
								: 'border-transparent hover:border-[var(--color-border)] hover:bg-[var(--color-surface-1)] hover:text-[var(--color-text-primary)]'}"
						>
							<span>{MODELO_LABEL[modelo.modeloType] || modelo.modeloType}</span>
							{#if modelo.sleeve}
								<span class="text-[var(--color-text-muted)]">·</span>
								<span>{SLEEVE_LABEL[modelo.sleeve] || modelo.sleeve}</span>
							{/if}
						</button>
						<span class="text-[var(--color-text-muted)]">·</span>
						<span class="text-mono opacity-60">family {family.id}</span>
					</div>
				</div>
			</div>
			<div class="flex items-center gap-1.5">
				<button
					type="button"
					onclick={() => copyToClipboard(modelo.sku)}
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					title="Copiar SKU"
				>
					<Copy size={12} strokeWidth={1.8} />
					SKU
				</button>
				<button
					type="button"
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)]"
				>
					<ExternalLink size={12} strokeWidth={1.8} />
					PDP live
				</button>
			</div>
		</header>

		{#if editPanelOpen && family && modelo}
			<div class="border-b border-[var(--color-border)] bg-[var(--color-surface-0)] px-6 py-3">
				<EditModeloPanel
					{family}
					{modelo}
					onClose={() => (editPanelOpen = false)}
					{onFlash}
					{onRefresh}
					{onSelectSku}
				/>
			</div>
		{/if}

		<!-- Scroll body -->
		<div class="flex-1 overflow-y-auto">
			<!-- Actions bar — con COLORES distintos por acción -->
			<div class="border-b border-[var(--color-border)] px-6 py-3">
				<div
					class="text-display mb-2 flex items-center gap-2 text-[9.5px] text-[var(--color-text-tertiary)]"
				>
					Actions
					<span class="text-[9px] font-normal normal-case text-[var(--color-text-muted)]"
						>keyboard · V · F · S</span
					>
				</div>
				<div class="flex items-center gap-1.5">
					<!-- Verify: verde terminal, el primario -->
					<button
						type="button"
						onclick={() => triggerDecision('verified', '✓ Verify')}
						class="flex items-center gap-1.5 rounded-[4px] bg-[var(--color-terminal)] px-3 py-1.5 text-[11.5px] font-semibold text-black transition-all hover:brightness-110"
						style="box-shadow: 0 0 0 1px rgba(74, 222, 128, 0.4), 0 0 12px rgba(74, 222, 128, 0.15);"
					>
						<Check size={14} strokeWidth={2.5} />
						Verify
						<kbd class="!border-black/20 !bg-black/10 !text-black/70">V</kbd>
					</button>
					<!-- Flag: ámbar warning -->
					<button
						type="button"
						onclick={() => triggerDecision('flagged', '⚑ Flag')}
						class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-warning)]/30 bg-[var(--color-warning)]/10 px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-warning)] transition-colors hover:border-[var(--color-warning)]/60 hover:bg-[var(--color-warning)]/20"
					>
						<Flag size={13} strokeWidth={2} />
						Flag
						<kbd>F</kbd>
					</button>
					<!-- Skip: gris neutro -->
					<button
						type="button"
						onclick={() => triggerDecision('skipped', '⏭ Skip')}
						class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						<SkipForward size={13} strokeWidth={1.8} />
						Skip
						<kbd>S</kbd>
					</button>
					<div class="mx-2 h-5 w-px bg-[var(--color-border)]"></div>
					<!-- Mover: cyan -->
					<button
						type="button"
						onclick={handleMover}
						class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-info)]/30 bg-[var(--color-info)]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-info)] transition-colors hover:border-[var(--color-info)]/60 hover:bg-[var(--color-info)]/20"
					>
						<Shuffle size={13} strokeWidth={1.8} />
						Mover
					</button>
					<!-- Huérfano: púrpura -->
					<button
						type="button"
						onclick={handleHuerfano}
						class="flex items-center gap-1.5 rounded-[4px] border border-[#a78bfa]/30 bg-[#a78bfa]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[#a78bfa] transition-colors hover:border-[#a78bfa]/60 hover:bg-[#a78bfa]/20"
					>
						<DoorOpen size={13} strokeWidth={1.8} />
						Huérfano
					</button>
					<!-- Delete: rojo -->
					<button
						type="button"
						onclick={handleDelete}
						class="ml-auto flex items-center gap-1.5 rounded-[4px] border border-[var(--color-flagged)]/30 bg-[var(--color-flagged)]/10 px-2.5 py-1.5 text-[11.5px] font-medium text-[var(--color-flagged)] transition-colors hover:border-[var(--color-flagged)]/60 hover:bg-[var(--color-flagged)]/20"
					>
						<Trash2 size={13} strokeWidth={1.8} />
						Delete
					</button>
				</div>
			</div>

			<!-- Visibility & Display toggles — NEW -->
			<div class="border-b border-[var(--color-border)] px-6 py-3">
				<div
					class="text-display mb-2 flex items-center gap-2 text-[9.5px] text-[var(--color-text-tertiary)]"
				>
					Visibility & Display
					<span class="text-[9px] font-normal normal-case text-[var(--color-text-muted)]"
						>afecta el vault live</span
					>
				</div>
				<div class="grid grid-cols-2 gap-1.5">
					<!-- Published toggle -->
					<button
						type="button"
						onclick={() => toggleFamilyFlag('published')}
						class="flex items-center justify-between rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] transition-all hover:border-[var(--color-border-strong)]"
					>
						<span class="flex items-center gap-1.5">
							{#if family.published}
								<Eye size={12} strokeWidth={1.8} style="color: var(--color-live)" />
								<span class="font-medium" style="color: var(--color-text-primary)">Publicado</span>
							{:else}
								<EyeOff size={12} strokeWidth={1.8} style="color: var(--color-text-tertiary)" />
								<span style="color: var(--color-text-secondary)">Oculto</span>
							{/if}
						</span>
						<span
							class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]"
							style="background: {family.published
								? 'rgba(74, 222, 128, 0.18)'
								: 'rgba(66, 66, 74, 0.3)'}; color: {family.published
								? 'var(--color-live)'
								: 'var(--color-text-tertiary)'};"
						>
							{family.published ? 'LIVE' : 'OFF'}
						</span>
					</button>
					<!-- Featured toggle -->
					<button
						type="button"
						onclick={() => toggleFamilyFlag('featured')}
						class="flex items-center justify-between rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] transition-all hover:border-[var(--color-border-strong)]"
					>
						<span class="flex items-center gap-1.5">
							<Star
								size={12}
								strokeWidth={1.8}
								style="color: {family.featured ? 'var(--color-warning)' : 'var(--color-text-tertiary)'}"
								fill={family.featured ? 'currentColor' : 'none'}
							/>
							<span
								style="color: {family.featured
									? 'var(--color-text-primary)'
									: 'var(--color-text-secondary)'}; font-weight: {family.featured
									? '500'
									: '400'};"
							>
								Featured TOP
							</span>
						</span>
						<span
							class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]"
							style="background: {family.featured
								? 'rgba(245, 165, 36, 0.18)'
								: 'rgba(66, 66, 74, 0.3)'}; color: {family.featured
								? 'var(--color-warning)'
								: 'var(--color-text-tertiary)'};"
						>
							{family.featured ? 'ON' : 'OFF'}
						</span>
					</button>
					<!-- Sold out toggle -->
					<button
						type="button"
						onclick={toggleSoldOut}
						class="flex items-center justify-between rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] transition-all hover:border-[var(--color-border-strong)]"
					>
						<span class="flex items-center gap-1.5">
							<PackageX
								size={12}
								strokeWidth={1.8}
								style="color: {modelo.soldOut ? 'var(--color-flagged)' : 'var(--color-text-tertiary)'}"
							/>
							<span
								style="color: {modelo.soldOut
									? 'var(--color-text-primary)'
									: 'var(--color-text-secondary)'}; font-weight: {modelo.soldOut
									? '500'
									: '400'};"
							>
								Sold out
							</span>
						</span>
						<span
							class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]"
							style="background: {modelo.soldOut
								? 'rgba(244, 63, 94, 0.18)'
								: 'rgba(66, 66, 74, 0.3)'}; color: {modelo.soldOut
								? 'var(--color-flagged)'
								: 'var(--color-text-tertiary)'};"
						>
							{modelo.soldOut ? 'YES' : 'NO'}
						</span>
					</button>
					<!-- Archived toggle -->
					<button
						type="button"
						onclick={() => toggleFamilyFlag('archived')}
						class="flex items-center justify-between rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] transition-all hover:border-[var(--color-border-strong)]"
					>
						<span class="flex items-center gap-1.5">
							<Archive
								size={12}
								strokeWidth={1.8}
								style="color: {family.archived ? 'var(--color-rework)' : 'var(--color-text-tertiary)'}"
							/>
							<span
								style="color: {family.archived
									? 'var(--color-text-primary)'
									: 'var(--color-text-secondary)'}; font-weight: {family.archived
									? '500'
									: '400'};"
							>
								Archivado
							</span>
						</span>
						<span
							class="text-display rounded-[3px] px-1.5 py-0.5 text-[9px]"
							style="background: {family.archived
								? 'rgba(245, 165, 36, 0.18)'
								: 'rgba(66, 66, 74, 0.3)'}; color: {family.archived
								? 'var(--color-rework)'
								: 'var(--color-text-tertiary)'};"
						>
							{family.archived ? 'ON' : 'OFF'}
						</span>
					</button>
				</div>
			</div>

			<!-- Gallery CON drag-and-drop -->
			<div class="border-b border-[var(--color-border)] px-6 py-4">
				<div class="mb-3 flex items-center justify-between">
					<div
						class="text-display flex items-center gap-2 text-[9.5px] text-[var(--color-text-tertiary)]"
					>
						Gallery
						<span class="text-[9px] font-normal normal-case text-[var(--color-text-muted)]">
							{localPhotos.length} fotos · drag to reorder
						</span>
					</div>
					<div class="flex items-center gap-2">
						{#if selectedPhotoIdxs.size > 0}
							<!-- Selection toolbar — aparece cuando hay fotos seleccionadas -->
							<span
								class="text-mono rounded-[3px] bg-[var(--color-accent)]/20 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--color-accent)] tabular-nums"
							>
								{selectedPhotoIdxs.size} sel
							</span>
							<button
								type="button"
								onclick={cleanSelectedWithGemini}
								class="flex items-center gap-1 rounded-[4px] border border-[var(--color-terminal)]/40 bg-[var(--color-terminal-soft)] px-2 py-1 text-[10.5px] font-medium text-[var(--color-terminal)] transition-colors hover:opacity-90"
							>
								<Sparkles size={11} strokeWidth={1.8} />
								Limpiar con Gemini
							</button>
							<button
								type="button"
								onclick={deleteSelectedPhotos}
								class="flex items-center gap-1 rounded-[4px] border border-[var(--color-flagged)]/40 bg-[var(--color-flagged)]/10 px-2 py-1 text-[10.5px] font-medium text-[var(--color-flagged)] transition-colors hover:bg-[var(--color-flagged)]/20"
							>
								<Trash2 size={11} strokeWidth={1.8} />
								Borrar
							</button>
							<button
								type="button"
								onclick={clearPhotoSelection}
								class="text-[10px] text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]"
							>
								Cancelar
							</button>
						{:else if batchCleanState === 'busy'}
							<span
								class="flex items-center gap-2 rounded-[4px] border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-2 py-1 text-[10.5px] font-medium text-[var(--color-warning)]"
							>
								<Loader2 size={11} strokeWidth={1.8} class="animate-spin" />
								{#if batchProgress}
									<span class="text-mono tabular-nums">
										{batchProgress.current}/{batchProgress.total}
									</span>
									<span
										class="inline-block h-1 w-16 rounded-full bg-[var(--color-warning)]/20"
									>
										<span
											class="block h-full rounded-full bg-[var(--color-warning)] transition-all"
											style="width: {batchProgress.total > 0
												? Math.round((batchProgress.current / batchProgress.total) * 100)
												: 0}%"
										></span>
									</span>
								{:else}
									Limpiando…
								{/if}
							</span>
						{:else}
							<button
								type="button"
								onclick={() => handleBatchClean('modelo')}
								title="Limpiar fotos DIRTY del MODELO actual"
								class="flex items-center gap-1 rounded-[4px] border border-[var(--color-warning)]/40 bg-[var(--color-warning)]/10 px-2 py-1 text-[10.5px] font-medium text-[var(--color-warning)] transition-colors hover:border-[var(--color-warning)]/60 hover:bg-[var(--color-warning)]/20"
							>
								<Brush size={11} strokeWidth={1.8} />
								Limpiar modelo
							</button>
							<button
								type="button"
								onclick={() => handleBatchClean('family')}
								title="Limpiar fotos DIRTY de TODOS los modelos del family"
								class="flex items-center gap-1 rounded-[4px] border border-[var(--color-warning)]/30 bg-transparent px-2 py-1 text-[10.5px] font-medium text-[var(--color-warning)]/80 transition-colors hover:border-[var(--color-warning)]/50 hover:bg-[var(--color-warning)]/10"
							>
								<Brush size={11} strokeWidth={1.8} />
								family
							</button>
							<span class="text-[9.5px] text-[var(--color-text-muted)]">ctrl+click selecciona</span>
						{/if}
					</div>
				</div>
				{#if localPhotos.length === 0}
					<div
						class="flex h-48 items-center justify-center rounded-[4px] border border-dashed border-[var(--color-border)] text-[12px] text-[var(--color-text-tertiary)]"
					>
						Sin fotos
					</div>
				{:else}
					<div
						class="grid grid-cols-4 gap-2"
						use:dndzone={{
							items: localPhotos.map((p) => ({ ...p, id: p.id })),
							flipDurationMs: 180,
							dropTargetStyle: {
								outline: '2px dashed var(--color-accent)',
								outlineOffset: '-2px',
								borderRadius: '4px'
							}
						}}
						onconsider={handleDndConsider}
						onfinalize={handleDndFinalize}
					>
						{#each localPhotos as foto, i (foto.id)}
							{@const opState = photoOps[foto.id] ?? null}
							<div
								class="group relative aspect-square cursor-grab overflow-hidden rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] transition-all hover:border-[var(--color-accent)]/50 active:cursor-grabbing"
							>
								<img
									src={foto.url}
									alt=""
									loading="lazy"
									fetchpriority="low"
									class="h-full w-full object-cover"
									draggable="false"
									onclick={(e) => {
										e.stopPropagation();
										// Ctrl/Shift+click toggles selection. Click plano abre lightbox.
										if (!togglePhotoSelection(i, e)) {
											openLightbox(i);
										}
									}}
								/>

								<!-- Selection overlay — accent border si esta foto está selected -->
								{#if selectedPhotoIdxs.has(i)}
									<div
										class="pointer-events-none absolute inset-0 rounded-[4px] ring-2 ring-[var(--color-accent)] ring-offset-0"
									></div>
									<span
										class="text-mono absolute bottom-1 left-1 rounded-[3px] bg-[var(--color-accent)] px-1.5 py-0.5 text-[9px] font-semibold text-white backdrop-blur-sm"
									>
										✓
									</span>
								{/if}

								<!-- Zoom hint (arriba izquierda, solo hover) -->
								<button
									type="button"
									onclick={(e) => {
										e.stopPropagation();
										openLightbox(i);
									}}
									title="Ampliar (click o doble-click) · Ctrl+click para seleccionar · Shift+click rango"
									class="absolute top-1 right-1 flex h-6 w-6 items-center justify-center rounded-[3px] bg-black/70 text-white/80 opacity-0 backdrop-blur-sm transition-opacity hover:bg-black/90 hover:text-white group-hover:opacity-100"
								>
									<Maximize2 size={11} strokeWidth={2} />
								</button>

								{#if opState === 'busy'}
									<!-- Busy overlay — cubre todo, spinner al centro -->
									<div
										class="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm"
									>
										<Loader2 size={24} strokeWidth={1.8} class="animate-spin text-white" />
									</div>
								{:else if opState === 'error'}
									<div
										class="absolute inset-0 flex items-center justify-center bg-[var(--color-flagged)]/40 backdrop-blur-sm"
									>
										<AlertTriangle size={24} strokeWidth={1.8} class="text-white" />
									</div>
								{/if}

								<!-- Drag handle sutil top-center -->
								<div
									class="pointer-events-none absolute top-1 left-1/2 -translate-x-1/2 rounded-[3px] bg-black/60 px-1 py-0.5 opacity-0 backdrop-blur-sm transition-opacity group-hover:opacity-100"
								>
									<GripVertical size={10} strokeWidth={2} class="text-white/70" />
								</div>
								<div
									class="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between p-1.5"
								>
									<span
										class="text-mono rounded-[3px] bg-black/70 px-1.5 py-0.5 text-[9px] font-semibold text-white backdrop-blur-sm tabular-nums"
									>
										{i + 1}
									</span>
									<div class="flex gap-1">
										{#if foto.isHero}
											<span
												title="Hero"
												class="flex h-5 w-5 items-center justify-center rounded-[3px] bg-[var(--color-accent)]/95 text-white backdrop-blur-sm"
											>
												<Crown size={11} strokeWidth={2} />
											</span>
										{/if}
										{#if foto.isDirty}
											<span
												title="DIRTY"
												class="text-display rounded-[3px] bg-[var(--color-warning)] px-1 py-0.5 text-[8.5px] text-black"
											>
												DIRTY
											</span>
										{/if}
									</div>
								</div>

								<!-- Watermark actions: hover reveals 3 icon buttons bottom -->
								{#if opState !== 'busy'}
									<div
										class="absolute inset-x-0 bottom-0 flex items-center justify-center gap-1 bg-gradient-to-t from-black/80 to-transparent p-2 opacity-0 transition-opacity group-hover:opacity-100"
									>
										<button
											type="button"
											onclick={(e) => {
												e.stopPropagation();
												void runWatermark(i, 'auto');
											}}
											title="Auto (LaMa + OCR detect watermark)"
											class="flex h-7 w-7 items-center justify-center rounded-[4px] border border-white/20 bg-black/80 text-white transition-colors hover:border-white/40 hover:bg-[var(--color-surface-2)]"
										>
											<Brush size={12} strokeWidth={1.8} />
										</button>
										<button
											type="button"
											onclick={(e) => {
												e.stopPropagation();
												void runWatermark(i, 'force');
											}}
											title="Force (LaMa + mask hardcoded centro)"
											class="flex h-7 w-7 items-center justify-center rounded-[4px] border border-[#a78bfa]/40 bg-[#a78bfa]/20 text-[#c4b5fd] transition-colors hover:bg-[#a78bfa]/40"
										>
											<Paintbrush size={12} strokeWidth={1.8} />
										</button>
										<button
											type="button"
											onclick={(e) => {
												e.stopPropagation();
												void runWatermark(i, 'gemini');
											}}
											title="Gemini 2.5 (preserva logos/texturas)"
											class="flex h-7 w-7 items-center justify-center rounded-[4px] border border-[var(--color-terminal)]/40 bg-[var(--color-terminal-soft)] text-[var(--color-terminal)] transition-colors hover:bg-[var(--color-terminal-soft)] hover:opacity-90"
										>
											<Sparkles size={12} strokeWidth={1.8} />
										</button>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- Specs inline editables -->
			<div class="border-b border-[var(--color-border)] px-6 py-4">
				<div
					class="text-display mb-3 flex items-center gap-2 text-[9.5px] text-[var(--color-text-tertiary)]"
				>
					Specs
					<span class="text-[9px] font-normal normal-case text-[var(--color-text-muted)]"
						>auto-save on blur</span
					>
				</div>
				<div class="grid grid-cols-[120px_1fr] gap-x-4 gap-y-1 text-[12px]">
					<div class="py-1 text-[var(--color-text-tertiary)]">Team</div>
					<input
						type="text"
						value={family.team}
						class="rounded-[3px] border border-transparent bg-transparent px-1.5 py-1 text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-border)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface-1)] focus:outline-none"
					/>

					<div class="py-1 text-[var(--color-text-tertiary)]">Season</div>
					<input
						type="text"
						value={family.season}
						class="rounded-[3px] border border-transparent bg-transparent px-1.5 py-1 text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-border)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface-1)] focus:outline-none"
					/>

					<div class="py-1 text-[var(--color-text-tertiary)]">Variant</div>
					<select
						value={family.variant}
						onchange={(e) => changeFamilyVariant(e.currentTarget.value)}
						class="rounded-[3px] border border-transparent bg-transparent px-1.5 py-1 text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-border)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface-1)] focus:outline-none"
					>
						{#each VARIANT_OPTIONS as opt (opt.value)}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>

					<div class="py-1 text-[var(--color-text-tertiary)]">Precio</div>
					<div class="flex items-center gap-1">
						<span class="text-[var(--color-text-tertiary)] text-[11px]">Q</span>
						<input
							type="number"
							value={modelo.price ?? 0}
							onblur={(e) => changeModeloField('price', parseInt(e.currentTarget.value, 10) || 0)}
							onkeydown={(e) => {
								if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur();
							}}
							class="text-mono flex-1 rounded-[3px] border border-transparent bg-transparent px-1.5 py-1 text-[var(--color-text-primary)] transition-colors hover:border-[var(--color-border)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface-1)] focus:outline-none"
						/>
					</div>

					<div class="py-1 text-[var(--color-text-tertiary)]">Sizes</div>
					<div class="flex items-center gap-1">
						<input
							type="text"
							list="sizes-presets"
							value={modelo.sizes ?? ''}
							onblur={(e) => changeModeloField('sizes', e.currentTarget.value.trim())}
							onkeydown={(e) => {
								if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur();
							}}
							placeholder="S-XXL"
							class="flex-1 rounded-[3px] border border-transparent bg-transparent px-1.5 py-1 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface-1)] focus:outline-none"
						/>
						<datalist id="sizes-presets">
							{#each SIZES_PRESETS as s}
								<option value={s}></option>
							{/each}
						</datalist>
					</div>

					<div class="py-1 text-[var(--color-text-tertiary)]">Priority</div>
					<input
						type="number"
						value={family.priority ?? 0}
						placeholder="orden manual en vault"
						class="text-mono rounded-[3px] border border-transparent bg-transparent px-1.5 py-1 text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] transition-colors hover:border-[var(--color-border)] focus:border-[var(--color-accent)] focus:bg-[var(--color-surface-1)] focus:outline-none"
					/>
				</div>
			</div>

			<!-- Checks pre-publish (L1 validation: block/warn/info) -->
			<div class="border-b border-[var(--color-border)] px-6 py-4">
				<div class="text-display mb-2.5 flex items-center justify-between text-[9.5px] text-[var(--color-text-tertiary)]">
					<span>Checks pre-publish</span>
					{#if validation && validation.isClean}
						<span class="flex items-center gap-1 text-[var(--color-success)]">
							<Check size={10} strokeWidth={2.5} />
							Todo OK
						</span>
					{:else if validation && !validation.canPublish}
						<span class="flex items-center gap-1 text-[var(--color-danger)]">
							<AlertTriangle size={10} strokeWidth={2.5} />
							{validation.issues.filter((i) => i.severity === 'block').length} bloquea
						</span>
					{:else if validation && validation.issues.length > 0}
						<span class="flex items-center gap-1 text-[var(--color-warning)]">
							<AlertTriangle size={10} strokeWidth={2.5} />
							{validation.issues.length} aviso{validation.issues.length === 1 ? '' : 's'}
						</span>
					{/if}
				</div>
				<div class="flex flex-col gap-1.5">
					{#if validation && validation.isClean}
						<div class="flex items-center gap-2 text-[12px] text-[var(--color-success)]">
							<span
								class="flex h-4 w-4 items-center justify-center rounded-full"
								style="background: rgba(74, 222, 128, 0.12);"
							>
								<Check size={11} strokeWidth={2.5} />
							</span>
							<span>Lista para publicar</span>
						</div>
					{:else if validation}
						{#each validation.issues as issue (issue.kind)}
							{@const tone =
								issue.severity === 'block'
									? { bg: 'rgba(244, 63, 94, 0.12)', fg: 'var(--color-danger)' }
									: issue.severity === 'warn'
										? { bg: 'rgba(251, 191, 36, 0.14)', fg: 'var(--color-warning)' }
										: { bg: 'rgba(96, 165, 250, 0.14)', fg: 'var(--color-info, #60a5fa)' }}
							<div
								class="flex items-start gap-2 rounded-[4px] px-2 py-1.5 text-[11.5px]"
								style="background: {tone.bg};"
							>
								<span class="mt-0.5 flex-shrink-0" style="color: {tone.fg};">
									{#if issue.severity === 'block'}
										<X size={11} strokeWidth={2.5} />
									{:else if issue.severity === 'warn'}
										<AlertTriangle size={11} strokeWidth={2.2} />
									{:else}
										<Check size={11} strokeWidth={2} />
									{/if}
								</span>
								<div class="min-w-0 flex-1">
									<div style="color: {tone.fg};">{issue.message}</div>
									{#if issue.suggestion}
										<div class="mt-0.5 text-[10.5px] text-[var(--color-text-tertiary)]">
											{issue.suggestion}
										</div>
									{/if}
								</div>
								{#if BACKFILL_FIXABLE_KINDS.has(issue.kind)}
									<button
										type="button"
										onclick={handleBackfillMeta}
										disabled={backfillState === 'busy'}
										title="Corre backfill_catalog_meta.py — llena meta_country, conf, wc26 si faltan"
										class="flex flex-shrink-0 items-center gap-1 self-center rounded-[3px] border border-[var(--color-accent)]/40 bg-[var(--color-accent-soft)] px-2 py-1 text-[10.5px] font-semibold text-[var(--color-accent)] transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 disabled:cursor-not-allowed disabled:opacity-50"
									>
										{#if backfillState === 'busy'}
											<Loader2 size={10} class="animate-spin" />
											Fixing…
										{:else}
											⚡ Auto-fix
										{/if}
									</button>
								{/if}
							</div>
						{/each}
					{/if}
				</div>
			</div>

			<!-- Family siblings — clickables -->
			{#if family.modelos.length > 1}
				<div class="border-b border-[var(--color-border)] px-6 py-4">
					<div class="text-display mb-2.5 text-[9.5px] text-[var(--color-text-tertiary)]">
						Hermanos · {family.modelos.length - 1}
					</div>
					<div class="flex flex-col gap-0.5">
						{#each family.modelos as m (m.sku)}
							{#if m.sku !== modelo.sku}
								<button
									type="button"
									onclick={() => onSelectSku(m.sku)}
									class="group flex w-full items-center gap-2 rounded-[3px] px-2 py-1.5 text-left transition-colors hover:bg-[var(--color-surface-2)]"
								>
									<span
										class="text-mono text-[10px] text-[var(--color-text-tertiary)] group-hover:text-[var(--color-accent)] tabular-nums"
									>
										{m.sku}
									</span>
									<span
										class="flex-1 text-[12px] text-[var(--color-text-secondary)] group-hover:text-[var(--color-text-primary)]"
									>
										{MODELO_LABEL[m.modeloType] || m.modeloType}
									</span>
									<StatusBadge status={m.status} size="xs" />
									<ChevronRight
										size={12}
										strokeWidth={1.8}
										class="text-[var(--color-text-muted)] opacity-0 transition-opacity group-hover:opacity-100"
									/>
								</button>
							{/if}
						{/each}
					</div>
				</div>
			{/if}

			<!-- Quick actions — NEW section -->
			<div class="border-b border-[var(--color-border)] px-6 py-4">
				<div class="text-display mb-2.5 text-[9.5px] text-[var(--color-text-tertiary)]">
					Quick actions
				</div>
				<div class="grid grid-cols-2 gap-1.5">
					<button
						type="button"
						onclick={() => copyToClipboard(family.id)}
						class="flex items-center gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						<Copy size={12} strokeWidth={1.8} />
						Copy family_id
					</button>
					<button
						type="button"
						class="flex items-center gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						<FileJson size={12} strokeWidth={1.8} />
						Export JSON
					</button>
					<button
						type="button"
						class="flex items-center gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						<Files size={12} strokeWidth={1.8} />
						Duplicar como template
					</button>
					<button
						type="button"
						class="flex items-center gap-2 rounded-[3px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-2.5 py-1.5 text-[11px] text-[var(--color-text-secondary)] transition-colors hover:border-[var(--color-border-strong)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)]"
					>
						<History size={12} strokeWidth={1.8} />
						Ver audit history
					</button>
				</div>
			</div>

			<!-- Publish block -->
			<div class="px-6 py-5">
				<div class="text-display mb-2.5 text-[9.5px] text-[var(--color-text-tertiary)]">
					Publish
				</div>
				{#if familyReady.ready && validation && validation.canPublish}
					<button
						type="button"
						onclick={handlePublishFamily}
						disabled={publishState === 'busy'}
						class="flex w-full items-center justify-center gap-2 rounded-[4px] bg-[var(--color-terminal)] px-4 py-2.5 text-[12.5px] font-semibold text-black transition-all hover:brightness-110 disabled:opacity-60"
						style="box-shadow: 0 0 0 1px rgba(74, 222, 128, 0.5), 0 0 20px rgba(74, 222, 128, 0.2);"
					>
						{#if publishState === 'busy'}
							<Loader2 size={14} strokeWidth={2.5} class="animate-spin" />
							Publicando…
						{:else}
							<Upload size={14} strokeWidth={2.5} />
							Publicar family + Commit + Push · {familyReady.total} modelos
						{/if}
					</button>
					{#if validation.issues.length > 0}
						<div class="mt-2 text-[10.5px] text-[var(--color-text-tertiary)]">
							{validation.issues.length} aviso{validation.issues.length === 1 ? '' : 's'}
							no-bloqueante{validation.issues.length === 1 ? '' : 's'} — revisá arriba.
						</div>
					{/if}
				{:else if !familyReady.ready}
					<div class="mb-2 text-[11.5px] text-[var(--color-text-secondary)]">
						<span class="text-mono font-semibold tabular-nums text-[var(--color-text-primary)]"
							>{familyReady.verified}/{familyReady.total}</span
						>
						modelos verified · faltan
						<span class="text-mono font-semibold tabular-nums text-[var(--color-rework)]"
							>{familyReady.total - familyReady.verified}</span
						>
					</div>
					<button
						type="button"
						disabled
						class="flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-surface-1)] px-4 py-2.5 text-[12.5px] font-semibold text-[var(--color-text-tertiary)]"
					>
						<Upload size={14} strokeWidth={1.8} />
						Publicar family · disabled
					</button>
				{:else}
					<!-- familyReady.ready=true PERO validation.canPublish=false → hay block issues -->
					<div class="mb-2 text-[11.5px] text-[var(--color-danger)]">
						{validation?.issues.filter((i) => i.severity === 'block').length} regla{validation &&
						validation.issues.filter((i) => i.severity === 'block').length === 1
							? ''
							: 's'} bloquea{validation &&
						validation.issues.filter((i) => i.severity === 'block').length === 1
							? ''
							: 'n'} la publicación · revisá arriba.
					</div>
					<button
						type="button"
						disabled
						class="flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-[4px] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 px-4 py-2.5 text-[12.5px] font-semibold text-[var(--color-danger)]"
					>
						<Upload size={14} strokeWidth={1.8} />
						Publicar family · bloqueado
					</button>
				{/if}
			</div>
		</div>
	{/if}
</section>

<!-- Keyboard listener para el lightbox -->
<svelte:window onkeydown={handleLightboxKey} />

<!-- Move modal -->
<MoveModeloModal
	open={moveModalOpen}
	sourceFamily={family}
	sourceModelo={modelo}
	{families}
	onClose={() => (moveModalOpen = false)}
	{onFlash}
	{onSelectSku}
/>

<!-- Lightbox overlay — foto ampliada fullscreen con navegación -->
{#if lightboxIdx !== null && localPhotos[lightboxIdx]}
	{@const photo = localPhotos[lightboxIdx]}
	{@const opState = photoOps[photo.id] ?? null}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md"
		onclick={closeLightbox}
		onkeydown={(e) => e.key === 'Escape' && closeLightbox()}
		role="dialog"
		tabindex="-1"
		aria-label="Vista ampliada de foto"
	>
		<!-- Close button top-right -->
		<button
			type="button"
			onclick={(e) => {
				e.stopPropagation();
				closeLightbox();
			}}
			title="Cerrar (ESC)"
			class="absolute top-4 right-4 flex h-10 w-10 items-center justify-center rounded-[6px] border border-white/10 bg-black/60 text-white/80 backdrop-blur-sm transition-colors hover:border-white/30 hover:bg-black/80 hover:text-white"
		>
			<X size={20} strokeWidth={1.8} />
		</button>

		<!-- Nav prev -->
		{#if localPhotos.length > 1}
			<button
				type="button"
				onclick={(e) => {
					e.stopPropagation();
					lightboxPrev();
				}}
				title="Foto anterior (←)"
				class="absolute left-4 flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-black/60 text-white/80 backdrop-blur-sm transition-colors hover:border-white/30 hover:bg-black/80 hover:text-white"
			>
				<ChevronLeft size={22} strokeWidth={1.8} />
			</button>
		{/if}

		<!-- Image + info wrapper — stopPropagation para que click-on-image no cierre -->
		<div
			class="flex max-h-[92vh] max-w-[90vw] flex-col items-center gap-4"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="presentation"
		>
			<!-- Foto + busy overlay -->
			<div class="relative overflow-hidden rounded-[8px] border border-white/10 shadow-2xl">
				<img
					src={photo.url}
					alt=""
					class="block max-h-[78vh] max-w-full object-contain"
					draggable="false"
				/>
				{#if opState === 'busy'}
					<div
						class="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm"
					>
						<Loader2 size={48} strokeWidth={1.8} class="animate-spin text-white" />
					</div>
				{/if}
				<!-- Badges top-left -->
				<div class="pointer-events-none absolute top-3 left-3 flex items-center gap-2">
					<span
						class="text-mono rounded-[4px] bg-black/80 px-2 py-1 text-[11px] font-semibold text-white backdrop-blur-sm tabular-nums"
					>
						{lightboxIdx + 1} / {localPhotos.length}
					</span>
					{#if photo.isHero}
						<span
							class="flex items-center gap-1 rounded-[4px] bg-[var(--color-accent)]/95 px-2 py-1 text-[10px] font-semibold text-white backdrop-blur-sm"
						>
							<Crown size={12} strokeWidth={2} />
							HERO
						</span>
					{/if}
					{#if photo.isDirty}
						<span
							class="text-display rounded-[4px] bg-[var(--color-warning)] px-2 py-1 text-[10px] text-black"
						>
							DIRTY
						</span>
					{/if}
				</div>
			</div>

			<!-- Watermark actions bar -->
			<div
				class="flex items-center gap-2 rounded-[8px] border border-white/10 bg-black/60 p-2 backdrop-blur-sm"
			>
				<button
					type="button"
					onclick={() => lightboxIdx !== null && void runWatermark(lightboxIdx, 'auto')}
					disabled={opState === 'busy'}
					title="Auto (LaMa + OCR detect)"
					class="flex items-center gap-1.5 rounded-[4px] border border-white/20 bg-black/70 px-3 py-1.5 text-[11.5px] font-medium text-white transition-colors hover:border-white/40 hover:bg-black/90 disabled:opacity-50"
				>
					<Brush size={13} strokeWidth={1.8} />
					Auto
				</button>
				<button
					type="button"
					onclick={() => lightboxIdx !== null && void runWatermark(lightboxIdx, 'force')}
					disabled={opState === 'busy'}
					title="Force (mask centro)"
					class="flex items-center gap-1.5 rounded-[4px] border border-[#a78bfa]/40 bg-[#a78bfa]/20 px-3 py-1.5 text-[11.5px] font-medium text-[#c4b5fd] transition-colors hover:bg-[#a78bfa]/40 disabled:opacity-50"
				>
					<Paintbrush size={13} strokeWidth={1.8} />
					Force
				</button>
				<button
					type="button"
					onclick={() => lightboxIdx !== null && void runWatermark(lightboxIdx, 'gemini')}
					disabled={opState === 'busy'}
					title="Gemini 2.5 Flash Image"
					class="flex items-center gap-1.5 rounded-[4px] border border-[var(--color-terminal)]/40 bg-[var(--color-terminal-soft)] px-3 py-1.5 text-[11.5px] font-medium text-[var(--color-terminal)] transition-colors hover:opacity-90 disabled:opacity-50"
				>
					<Sparkles size={13} strokeWidth={1.8} />
					Gemini
				</button>
				<div class="mx-1 h-6 w-px bg-white/10"></div>
				<a
					href={photo.url}
					target="_blank"
					rel="noopener"
					onclick={(e) => e.stopPropagation()}
					title="Abrir original en nueva pestaña"
					class="flex items-center gap-1.5 rounded-[4px] border border-white/10 bg-black/50 px-3 py-1.5 text-[11.5px] font-medium text-white/80 transition-colors hover:border-white/30 hover:bg-black/70 hover:text-white"
				>
					<ExternalLink size={13} strokeWidth={1.8} />
					Abrir
				</a>
			</div>

			<!-- Keyboard hints -->
			<div class="flex items-center gap-3 text-[10px] text-white/50">
				<span class="flex items-center gap-1">
					<kbd class="rounded border border-white/20 px-1.5 py-0.5 text-[9px]">←</kbd>
					<kbd class="rounded border border-white/20 px-1.5 py-0.5 text-[9px]">→</kbd>
					navegar
				</span>
				<span class="flex items-center gap-1">
					<kbd class="rounded border border-white/20 px-1.5 py-0.5 text-[9px]">ESC</kbd>
					cerrar
				</span>
			</div>
		</div>

		<!-- Nav next -->
		{#if localPhotos.length > 1}
			<button
				type="button"
				onclick={(e) => {
					e.stopPropagation();
					lightboxNext();
				}}
				title="Foto siguiente (→)"
				class="absolute right-4 flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-black/60 text-white/80 backdrop-blur-sm transition-colors hover:border-white/30 hover:bg-black/80 hover:text-white"
			>
				<ChevronRight size={22} strokeWidth={1.8} />
			</button>
		{/if}
	</div>
{/if}

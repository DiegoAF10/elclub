/**
 * Pre-publish validation para families del catalog.
 *
 * Por qué existe: la sesión 2026-04-24 reveló que Czech Republic 2026 home
 * se publicó sin meta_confederation (no estaba en wc2026-classified.json) →
 * no apareció en /mundial cards y quedó sin bandera. Validation pre-publish
 * detecta estos casos antes del commit + push.
 *
 * Por qué client-side: el ERP es local, single-user. La fuente de truth
 * (catalog.json) vive en disk. No hay backend que pueda validar de manera
 * más autoritativa. Frontend validation es suficiente.
 *
 * Por qué TS puro (no Svelte): para que sea testeable y reusable. Si
 * agregamos pre-publish gate al "Publicar Family" button + un panel de
 * preview en el sidebar, ambos consumen la misma function.
 */

import type { Family, Modelo } from './types';

export type ValidationSeverity = 'block' | 'warn' | 'info';

export interface ValidationIssue {
	severity: ValidationSeverity;
	/** Identificador estable para el issue (testing, telemetry, etc.). */
	kind: string;
	/** Mensaje user-facing. Se muestra en el banner + tooltip. */
	message: string;
	/** Acción sugerida si aplica (ej. "Correr backfill", "Agregar alias"). */
	suggestion?: string;
}

export interface ValidationResult {
	issues: ValidationIssue[];
	/** True si NO hay issues con severity='block'. UI deshabilita botón si false. */
	canPublish: boolean;
	/** True si todos los issues son severity='info' o no hay issues. */
	isClean: boolean;
}

/**
 * Valida si una family + modelo seleccionado están listos para publicar.
 *
 * Llamada desde:
 * - DetailPane "Publicar family" button (gate / banner)
 * - Sidebar widget de readiness (preview)
 *
 * TODO (Diego, ~5-10 LOC):
 *
 * Reglas a implementar — vos decidís qué severity tiene cada una:
 *
 *   1. **meta_country falta** — afecta el render del card en vault (sin
 *      country chip). Severidad sugerida: ?
 *
 *   2. **meta_confederation falta** — afecta /mundial confederation cards
 *      (no aparece en counters). Severidad sugerida: ?
 *
 *   3. **wc2026_eligible falta** y season incluye 2026 — afecta /mundial
 *      flags row + country pages. Si NO es 2026, no aplica. Severidad: ?
 *
 *   4. **price del primary modelo es 0 o null** — produce QNaN en cards.
 *      Severidad sugerida: ? (probablemente 'block' — fix obvio).
 *
 *   5. **gallery del primary < 3 fotos** — playbook §1 paso 7 mínimo. ?
 *
 *   6. **hero_thumbnail desincronizado** (family.hero != primary.gallery[0]).
 *      Workaround manual existe (sync). ?
 *
 *   7. **supplier_gap=true** publicándose — caso ambiguo. Anfitriones
 *      Mundial sin supplier (Paraguay/Australia/etc) podrían aún ser
 *      "publicables" como placeholders. ?
 *
 *   8. **L16 priority violation** — primary_modelo_idx apunta a kid/baby/
 *      woman cuando hay fan_adult disponible (caso brazil-2026-home reciente). ?
 *
 * Trade-offs a considerar:
 *
 * - **Strict (todo block) vs Permissive (todo warn)**: strict previene
 *   bugs pero frustra cuando vos sabés que la regla no aplica (ej. supplier_gap
 *   case 7). Permissive te deja ship con un click extra de confirmación.
 *
 * - **Auto-fix vs manual**: para meta_* faltantes, podríamos correr backfill
 *   automático antes de bloquear. Eso es J1 del backlog, no L1 — por ahora,
 *   solo flagear y que Diego decida.
 *
 * - **Granularidad**: si validás per-modelo (todos los modelos de la family
 *   deben pasar) vs per-family (solo el primary), cambia el comportamiento
 *   de families con muchas variantes. Hoy "Publicar family" hace
 *   final_verified=1 en TODOS los modelos — sugiero validar todos.
 *
 * Si necesitás más context: ver SESSION-HANDOFF.md L1 + el playbook §3
 * (schema canonical) + L16 (primary priority).
 */
export function validateForPublish(family: Family, primaryModelo: Modelo): ValidationResult {
	const issues: ValidationIssue[] = [];
	const seasonHas2026 = (family.season || '').includes('2026');

	// ─── Meta del catalog (L1 — bug Czech Republic 2026-04-24) ────────────

	if (!family.metaCountry) {
		issues.push({
			severity: 'block',
			kind: 'meta-country-missing',
			message: 'Falta meta_country — sin esto el vault no muestra chip de país',
			suggestion: 'Agregá el alias del fid a wc2026-classified.json + corré backfill'
		});
	}

	// meta_confederation aplica solo a selecciones nacionales. Los clubes
	// (Boca, Real Madrid, etc.) tienen meta_league pero NO confederación.
	// Por eso es warn, no block — para no trabar el workflow de clubes.
	if (!family.metaConfederation) {
		issues.push({
			severity: 'warn',
			kind: 'meta-confederation-missing',
			message: 'Sin confederación — OK si es club, problema si es selección',
			suggestion: 'Selecciones: agregar a wc2026-classified.json. Clubes: ignorar.'
		});
	}

	// wc2026_eligible solo aplica si la team es selección Y compite Mundial 2026.
	// Clubes con season 2026 (Real Madrid 2025-26) NO son elegibles. Warn, no block.
	if (seasonHas2026 && family.wc2026Eligible !== true) {
		issues.push({
			severity: 'warn',
			kind: 'wc2026-not-eligible',
			message: 'Season 2026 pero wc2026_eligible no está marcado',
			suggestion: 'Selecciones Mundial: corregir backfill. Clubes con season 25-26: ignorar.'
		});
	}

	// ─── Price del primary (bug QNaN 2026-04-24) ──────────────────────────

	if (!primaryModelo.price || primaryModelo.price <= 0) {
		issues.push({
			severity: 'block',
			kind: 'price-missing',
			message: `Primary modelo ${primaryModelo.sku} sin precio — genera QNaN en cards`,
			suggestion: 'Editá el precio en SPECS o corré backfill (asigna defaults Q435/Q275/Q250)'
		});
	}

	// ─── Gallery coverage ─────────────────────────────────────────────────
	// Diego pidió umbral 2 (no 3). Con 2+ fotos, el card del vault tiene
	// algo que mostrar y el carousel funciona. 1 foto es el límite.

	const galleryCount = primaryModelo.fotos.length;
	if (galleryCount < 2) {
		issues.push({
			severity: 'warn',
			kind: 'gallery-low-coverage',
			message: `Primary modelo solo tiene ${galleryCount} foto${galleryCount === 1 ? '' : 's'}`,
			suggestion: 'Refetch desde álbum Yupoo o agregá manual'
		});
	}

	// Regla DIRTY removida (2026-04-24): la detección de fotos sin watermark
	// no es 100% confiable (false positives), entonces bloquear o advertir
	// genera ruido. Diego revisa visualmente las fotos en el ERP.

	// ─── L16 primary priority — informativo, no block ─────────────────────
	// Si hay fan_adult pero el primary es kid/baby/woman, el card del vault
	// muestra la variante "secundaria" como hero. Funcional pero sub-óptimo.

	const hasAdultFan = family.modelos.some(
		(m) => m.modeloType === 'fan_adult' && m.sleeve === 'short'
	);
	const primaryIsSecondary = ['kid', 'baby', 'woman'].includes(primaryModelo.modeloType);
	if (hasAdultFan && primaryIsSecondary) {
		issues.push({
			severity: 'warn',
			kind: 'primary-priority-violation',
			message: `Primary es ${primaryModelo.modeloType} pero hay fan_adult/short — viola L16 priority`,
			suggestion: 'Click la corona en el modelo fan_adult para hacerlo primary'
		});
	}

	// ─── supplier_gap — informativo (anfitrión honorary) ──────────────────
	// Casos: Paraguay, Australia, Iraq, NZ, Uzbekistán (no en H&B). Si Diego
	// publica de todos modos, asume placeholder hasta supplier secundario.

	if (family.supplierGap) {
		issues.push({
			severity: 'info',
			kind: 'supplier-gap',
			message: 'Marcado supplier_gap=true — team no existe en H&B',
			suggestion: 'OK publicar como placeholder, o esperar supplier secundario'
		});
	}

	const blockCount = issues.filter((i) => i.severity === 'block').length;
	const totalCount = issues.length;

	return {
		issues,
		canPublish: blockCount === 0,
		isClean: totalCount === 0
	};
}

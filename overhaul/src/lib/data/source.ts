// Helpers de derivación sobre un array de Family.
// Ya no hay una export FAMILIES global — families se cargan via `$lib/adapter` en
// SvelteKit load functions (src/routes/+page.ts) y se pasan por props.
//
// Esto desacopla el data source del shape del consumer: dev (browser adapter),
// Tauri (native adapter), tests (mock data) — todos producen Family[] que estos
// helpers consumen indistintamente.

import type { Family, Modelo, Status } from './types';

// ─── Constantes compartidas ───────────────────────────────────────────

const GROUP_ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L'];

// ─── Agrupamiento ─────────────────────────────────────────────────────

export function familiesByGroup(families: Family[]): Map<string, Family[]> {
	const map = new Map<string, Family[]>();

	for (const fam of families) {
		const g = fam.group || '—';
		if (!map.has(g)) map.set(g, []);
		map.get(g)!.push(fam);
	}

	// Sort: Mundial groups A-L primero, luego resto alfabético, '—' al final.
	const sorted = new Map<string, Family[]>();
	for (const g of GROUP_ORDER) {
		if (map.has(g)) sorted.set(g, map.get(g)!);
	}
	const nonMundial = [...map.keys()]
		.filter((g) => !GROUP_ORDER.includes(g) && g !== '—')
		.sort();
	for (const g of nonMundial) sorted.set(g, map.get(g)!);
	if (map.has('—')) sorted.set('—', map.get('—')!);
	return sorted;
}

// ─── Flat list de SKUs (navegación J/K + command palette) ──────────────

export interface SkuEntry {
	sku: string;
	family: Family;
	modelo: Modelo;
	modeloIdx: number;
}

// Orden debe matchear exactamente el render del ListPane para que J/K y
// command palette naveguen en orden visual.
const VARIANT_ORDER = ['home', 'away', 'third', 'goalkeeper', 'special', 'training'];
const TYPE_ORDER = [
	'fan_adult',
	'player_adult',
	'retro_adult',
	'woman',
	'kid',
	'baby',
	'goalkeeper',
	'training',
	'polo',
	'sweatshirt',
	'jacket',
	'vest',
	'shorts',
	'adult'
];

function groupRank(group: string): number {
	const idx = GROUP_ORDER.indexOf(group);
	if (idx >= 0) return idx;
	if (group === '—') return 999;
	return 500; // otros groups van entre Mundial y '—'
}

function variantRank(variant: string): number {
	const idx = VARIANT_ORDER.indexOf(variant);
	return idx < 0 ? 999 : idx;
}

function typeRank(type: string): number {
	const idx = TYPE_ORDER.indexOf(type);
	return idx < 0 ? 999 : idx;
}

export function allSkus(families: Family[]): SkuEntry[] {
	// Ordenar families: group → team alfab → variant order
	const sortedFamilies = [...families].sort((a, b) => {
		const gr = groupRank(a.group || '—') - groupRank(b.group || '—');
		if (gr !== 0) return gr;
		const t = a.team.localeCompare(b.team);
		if (t !== 0) return t;
		return variantRank(a.variant) - variantRank(b.variant);
	});

	const list: SkuEntry[] = [];
	for (const fam of sortedFamilies) {
		// Dentro de la family: modelos por TYPE_ORDER, sleeve short antes de long
		const modelosWithIdx = fam.modelos.map((m, i) => ({ modelo: m, modeloIdx: i }));
		modelosWithIdx.sort((a, b) => {
			const tr = typeRank(a.modelo.modeloType) - typeRank(b.modelo.modeloType);
			if (tr !== 0) return tr;
			const sleeveA = a.modelo.sleeve === 'long' ? 1 : 0;
			const sleeveB = b.modelo.sleeve === 'long' ? 1 : 0;
			return sleeveA - sleeveB;
		});
		for (const { modelo, modeloIdx } of modelosWithIdx) {
			list.push({ sku: modelo.sku, family: fam, modelo, modeloIdx });
		}
	}
	return list;
}

// ─── Stats ─────────────────────────────────────────────────────────────

export interface CatalogStats {
	totalFamilies: number;
	totalModelos: number;
	live: number;
	ready: number;
	pending: number;
	rework: number;
	flagged: number;
	missing: number;
}

export function stats(families: Family[]): CatalogStats {
	const counts: Record<Status, number> = {
		live: 0,
		ready: 0,
		pending: 0,
		rework: 0,
		flagged: 0,
		missing: 0
	};
	let totalModelos = 0;
	for (const fam of families) {
		for (const m of fam.modelos) {
			totalModelos++;
			counts[m.status]++;
		}
	}
	return {
		totalFamilies: families.length,
		totalModelos,
		...counts
	};
}

// ─── Lookup helper ─────────────────────────────────────────────────────

export function findFamilyBySku(
	families: Family[],
	sku: string
): { family: Family; modeloIdx: number } | null {
	for (const fam of families) {
		const idx = fam.modelos.findIndex((m) => m.sku === sku);
		if (idx >= 0) return { family: fam, modeloIdx: idx };
	}
	return null;
}

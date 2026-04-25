// Mock data del Mundial 2026 — 12 families representativas con distintos estados
// para que Diego sienta el flow real. Post-MVP esto se reemplaza por un adapter
// que lee catalog.json (o la nueva base clean del Mundial).

import type { Family } from './types';

// Helper: placeholder image URL (gris con ícono SVG inline)
function placeholderPhoto(label: string, color = '#2a2a32'): string {
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400"><rect width="400" height="400" fill="${color}"/><text x="200" y="210" text-anchor="middle" fill="#6b6b74" font-family="Inter" font-size="24" font-weight="500">${label}</text></svg>`;
	return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

// ─── Mock families ────────────────────────────────────────
// Cubrimos los 12 grupos con al menos 1 team c/u + mix de status
// para demostrar visualmente los 6 estados.

export const MOCK_FAMILIES: Family[] = [
	// ══ Grupo C — Brazil (showcase: family completa con variety de status) ══
	{
		id: 'brazil-2026-home',
		team: 'Brazil',
		teamAliasEs: 'Brasil',
		flagIso: 'br',
		group: 'C',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: false,
		featured: true,
		modelos: [
			{
				sku: 'BRA-2026-L-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'live',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('BRA FS 1', '#f9b034'), isHero: true, isDirty: false },
					{ id: 'p2', url: placeholderPhoto('BRA FS 2', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p3', url: placeholderPhoto('BRA FS 3', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p4', url: placeholderPhoto('BRA FS 4', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p5', url: placeholderPhoto('BRA FS 5', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p6', url: placeholderPhoto('BRA FS 6', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p7', url: placeholderPhoto('BRA FS 7', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p8', url: placeholderPhoto('BRA FS 8', '#f9b034'), isHero: false, isDirty: false }
				]
			},
			{
				sku: 'BRA-2026-L-FL',
				modeloType: 'fan_adult',
				sleeve: 'long',
				status: 'ready',
				price: 475,
				sizes: 'S-3XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('BRA FL 1', '#f9b034'), isHero: true, isDirty: false },
					{ id: 'p2', url: placeholderPhoto('BRA FL 2', '#f9b034'), isHero: false, isDirty: false },
					{ id: 'p3', url: placeholderPhoto('BRA FL 3', '#f9b034'), isHero: false, isDirty: true },
					{ id: 'p4', url: placeholderPhoto('BRA FL 4', '#f9b034'), isHero: false, isDirty: false }
				]
			},
			{
				sku: 'BRA-2026-L-PS',
				modeloType: 'player_adult',
				sleeve: 'short',
				status: 'pending',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('BRA PS 1', '#f9b034'), isHero: true, isDirty: true },
					{ id: 'p2', url: placeholderPhoto('BRA PS 2', '#f9b034'), isHero: false, isDirty: true },
					{ id: 'p3', url: placeholderPhoto('BRA PS 3', '#f9b034'), isHero: false, isDirty: true },
					{ id: 'p4', url: placeholderPhoto('BRA PS 4', '#f9b034'), isHero: false, isDirty: true }
				]
			},
			{
				sku: 'BRA-2026-L-K',
				modeloType: 'kid',
				sleeve: null,
				status: 'rework',
				price: 275,
				sizes: '16-28',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('BRA K 1', '#f9b034'), isHero: true, isDirty: true },
					{ id: 'p2', url: placeholderPhoto('BRA K 2', '#f9b034'), isHero: false, isDirty: true }
				]
			}
		]
	},
	{
		id: 'brazil-2026-away',
		team: 'Brazil',
		teamAliasEs: 'Brasil',
		flagIso: 'br',
		group: 'C',
		season: '2026',
		variant: 'away',
		variantLabel: 'Visita',
		published: false,
		modelos: [
			{
				sku: 'BRA-2026-V-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'pending',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('BRA V FS 1', '#2563eb'), isHero: true, isDirty: true },
					{ id: 'p2', url: placeholderPhoto('BRA V FS 2', '#2563eb'), isHero: false, isDirty: true }
				]
			}
		]
	},

	// ══ Grupo J — Argentina (all verified + mostly live) ══
	{
		id: 'argentina-2026-home',
		team: 'Argentina',
		flagIso: 'ar',
		group: 'J',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: true,
		featured: true,
		modelos: [
			{
				sku: 'ARG-2026-L-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'live',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('ARG L FS 1', '#79bfef'), isHero: true, isDirty: false },
					{ id: 'p2', url: placeholderPhoto('ARG L FS 2', '#79bfef'), isHero: false, isDirty: false },
					{ id: 'p3', url: placeholderPhoto('ARG L FS 3', '#79bfef'), isHero: false, isDirty: false }
				]
			},
			{
				sku: 'ARG-2026-L-FL',
				modeloType: 'fan_adult',
				sleeve: 'long',
				status: 'ready',
				price: 475,
				sizes: 'S-3XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('ARG L FL 1', '#79bfef'), isHero: true, isDirty: false },
					{ id: 'p2', url: placeholderPhoto('ARG L FL 2', '#79bfef'), isHero: false, isDirty: false }
				]
			}
		]
	},
	{
		id: 'argentina-2026-away',
		team: 'Argentina',
		flagIso: 'ar',
		group: 'J',
		season: '2026',
		variant: 'away',
		variantLabel: 'Visita',
		published: true,
		modelos: [
			{
				sku: 'ARG-2026-V-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'live',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('ARG V 1', '#1e1b4b'), isHero: true, isDirty: false }
				]
			}
		]
	},

	// ══ Grupo L — England ══
	{
		id: 'england-2026-home',
		team: 'England',
		teamAliasEs: 'Inglaterra',
		flagIso: 'gb-eng',
		group: 'L',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: false,
		modelos: [
			{
				sku: 'ENG-2026-L-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'flagged',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('ENG L 1', '#f5f5f5'), isHero: true, isDirty: false }
				]
			}
		]
	},

	// ══ Grupo A — Mexico ══
	{
		id: 'mexico-2026-home',
		team: 'Mexico',
		teamAliasEs: 'México',
		flagIso: 'mx',
		group: 'A',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: false,
		modelos: [
			{
				sku: 'MEX-2026-L-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'ready',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('MEX L 1', '#059669'), isHero: true, isDirty: false },
					{ id: 'p2', url: placeholderPhoto('MEX L 2', '#059669'), isHero: false, isDirty: false }
				]
			}
		]
	},

	// ══ Grupo H — Spain ══
	{
		id: 'spain-2026-home',
		team: 'Spain',
		teamAliasEs: 'España',
		flagIso: 'es',
		group: 'H',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: false,
		modelos: [
			{
				sku: 'SPA-2026-L-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'pending',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('SPA 1', '#dc2626'), isHero: true, isDirty: true },
					{ id: 'p2', url: placeholderPhoto('SPA 2', '#dc2626'), isHero: false, isDirty: true }
				]
			}
		]
	},

	// ══ Grupo F — Netherlands ══
	{
		id: 'netherlands-2026-home',
		team: 'Netherlands',
		teamAliasEs: 'Países Bajos',
		flagIso: 'nl',
		group: 'F',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: false,
		modelos: []
	},

	// ══ Grupo I — France ══
	{
		id: 'france-2026-home',
		team: 'France',
		teamAliasEs: 'Francia',
		flagIso: 'fr',
		group: 'I',
		season: '2026',
		variant: 'home',
		variantLabel: 'Local',
		published: false,
		modelos: [
			{
				sku: 'FRA-2026-L-FS',
				modeloType: 'fan_adult',
				sleeve: 'short',
				status: 'pending',
				price: 435,
				sizes: 'S-4XL',
				fotos: [
					{ id: 'p1', url: placeholderPhoto('FRA 1', '#1e40af'), isHero: true, isDirty: false }
				]
			}
		]
	}
];

// Agrupa por team para el list pane
export function familiesByGroup(): Map<string, Family[]> {
	const map = new Map<string, Family[]>();
	const GROUP_ORDER = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L'];

	for (const fam of MOCK_FAMILIES) {
		if (!map.has(fam.group)) map.set(fam.group, []);
		map.get(fam.group)!.push(fam);
	}

	// Sort by group order
	const sorted = new Map<string, Family[]>();
	for (const g of GROUP_ORDER) {
		if (map.has(g)) sorted.set(g, map.get(g)!);
	}
	return sorted;
}

// Todos los SKUs flat para navigation
export function allSkus(): Array<{ sku: string; family: Family; modeloIdx: number }> {
	const list: Array<{ sku: string; family: Family; modeloIdx: number }> = [];
	for (const fam of MOCK_FAMILIES) {
		fam.modelos.forEach((m, i) => {
			list.push({ sku: m.sku, family: fam, modeloIdx: i });
		});
	}
	return list;
}

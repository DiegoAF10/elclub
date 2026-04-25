// Catalog row → Family transform.
// Port de scripts/migrate-published.mjs a runtime TS.
// Mantener sync con ese script — single source of truth de la logic debería vivir acá.

import type { Family, Modelo, Photo, Status, ModeloType, Sleeve, Variant } from '../data/types';
import type { AuditDecision, AuditStatus, CatalogRow, CatalogModeloRow } from './types';

// ─── Team → ISO 3166 code ─────────────────────────────────────────────
// Lista canónica para rendering de banderas. Ampliar cuando aparezcan teams nuevos.
export const TEAM_TO_ISO: Record<string, string> = {
	Mexico: 'mx',
	'South Africa': 'za',
	'South Korea': 'kr',
	'Czech Republic': 'cz',
	Canada: 'ca',
	'Bosnia and Herzegovina': 'ba',
	'Bosnia & Herzegovina': 'ba',
	Qatar: 'qa',
	Switzerland: 'ch',
	Brazil: 'br',
	Morocco: 'ma',
	Haiti: 'ht',
	Scotland: 'gb-sct',
	'United States': 'us',
	USA: 'us',
	Paraguay: 'py',
	Australia: 'au',
	Turkey: 'tr',
	Germany: 'de',
	Curacao: 'cw',
	'Ivory Coast': 'ci',
	Ecuador: 'ec',
	Netherlands: 'nl',
	Japan: 'jp',
	Sweden: 'se',
	Tunisia: 'tn',
	Belgium: 'be',
	Egypt: 'eg',
	Iran: 'ir',
	'New Zealand': 'nz',
	Spain: 'es',
	'Cape Verde': 'cv',
	'Saudi Arabia': 'sa',
	Uruguay: 'uy',
	France: 'fr',
	Senegal: 'sn',
	Iraq: 'iq',
	Norway: 'no',
	Argentina: 'ar',
	Algeria: 'dz',
	Austria: 'at',
	Jordan: 'jo',
	Portugal: 'pt',
	'DR Congo': 'cd',
	Uzbekistan: 'uz',
	Colombia: 'co',
	England: 'gb-eng',
	Croatia: 'hr',
	Ghana: 'gh',
	Panama: 'pa',
	Albania: 'al',
	Italy: 'it',
	Poland: 'pl',
	Serbia: 'rs',
	Denmark: 'dk',
	Venezuela: 've',
	Peru: 'pe',
	Chile: 'cl',
	Bolivia: 'bo',
	Nigeria: 'ng',
	Cameroon: 'cm',
	Ukraine: 'ua',
	Russia: 'ru',
	Greece: 'gr',
	Hungary: 'hu',
	Ireland: 'ie',
	Wales: 'gb-wls',
	'Northern Ireland': 'gb-nir',
	UAE: 'ae',
	'United Arab Emirates': 'ae'
};

// ─── Team → grupo Mundial A-L ─────────────────────────────────────────
export const TEAM_TO_GROUP: Record<string, string> = {
	Mexico: 'A',
	'South Africa': 'A',
	'South Korea': 'A',
	'Czech Republic': 'A',
	Canada: 'B',
	'Bosnia and Herzegovina': 'B',
	'Bosnia & Herzegovina': 'B',
	Qatar: 'B',
	Switzerland: 'B',
	Brazil: 'C',
	Morocco: 'C',
	Haiti: 'C',
	Scotland: 'C',
	'United States': 'D',
	USA: 'D',
	Paraguay: 'D',
	Australia: 'D',
	Turkey: 'D',
	Germany: 'E',
	Curacao: 'E',
	'Ivory Coast': 'E',
	Ecuador: 'E',
	Netherlands: 'F',
	Japan: 'F',
	Sweden: 'F',
	Tunisia: 'F',
	Belgium: 'G',
	Egypt: 'G',
	Iran: 'G',
	'New Zealand': 'G',
	Spain: 'H',
	'Cape Verde': 'H',
	'Saudi Arabia': 'H',
	Uruguay: 'H',
	France: 'I',
	Senegal: 'I',
	Iraq: 'I',
	Norway: 'I',
	Argentina: 'J',
	Algeria: 'J',
	Austria: 'J',
	Jordan: 'J',
	Portugal: 'K',
	'DR Congo': 'K',
	Uzbekistan: 'K',
	Colombia: 'K',
	England: 'L',
	Croatia: 'L',
	Ghana: 'L',
	Panama: 'L'
};

// ─── Variant label map ─────────────────────────────────────────────────
const VARIANT_LABELS: Record<string, string> = {
	home: 'Local',
	away: 'Visita',
	third: 'Tercera',
	goalkeeper: 'Portero',
	special: 'Especial',
	training: 'Entrenamiento'
};

// ─── Helpers ──────────────────────────────────────────────────────────
export function normalizeTeam(raw: string | null | undefined): string | null {
	if (!raw) return null;
	let t = raw.trim();
	t = t.replace(/\s+Jerseys?$/i, '');
	t = t.replace(/\s+-+$/, '');
	t = t.trim();
	return t || null;
}

export function getIso(team: string | null | undefined): string | undefined {
	const normalized = normalizeTeam(team);
	if (!normalized) return undefined;
	return TEAM_TO_ISO[normalized];
}

export function getGroup(team: string | null | undefined): string {
	const normalized = normalizeTeam(team);
	if (!normalized) return '—';
	return TEAM_TO_GROUP[normalized] ?? '—';
}

// ─── Status derivation ─────────────────────────────────────────────────
// Combina `published` del catalog + AuditDecision para derivar el Status
// visual del modelo. Decision mappings:
//   final_verified=1 + published=true  → 'live'
//   final_verified=1 + published=false → 'ready'
//   status='pending'                   → 'pending'
//   status='needs_rework'              → 'rework'
//   status='flagged'                   → 'flagged'
//   status='skipped'|'deleted'         → 'missing' (visualmente)
//   sin decision                       → 'pending' (default queue)
export function deriveStatus(
	published: boolean,
	decision: AuditDecision | null | undefined
): Status {
	if (decision?.final_verified) {
		return published ? 'live' : 'ready';
	}
	if (!decision) {
		return published ? 'live' : 'pending';
	}
	switch (decision.status) {
		case 'verified':
			return 'ready';
		case 'needs_rework':
			return 'rework';
		case 'flagged':
			return 'flagged';
		case 'skipped':
		case 'deleted':
			return 'missing';
		case 'pending':
		default:
			return 'pending';
	}
}

// ─── Default prices por modelo_type (Q GTQ) ───────────────────────────
// Precios reales documentados en elclub-catalogo-priv/docs/AUDIT-SYSTEM.md §5.2
// y DESIGN-BRIEF.md (decisión GENESIS de Diego: adulto flat).
//   Adulto flat (fan/player/retro/women/long-sleeve/goalkeeper) = Q435
//   Kid                                                         = Q275
//   Baby                                                        = Q250
// Si el catalog tiene un price específico (scraper o edit manual), ese prevalece.
export const DEFAULT_PRICE_BY_TYPE: Record<string, number> = {
	fan_adult: 435,
	player_adult: 435,
	retro_adult: 435,
	woman: 435,
	goalkeeper: 435,
	adult: 435,
	kid: 275,
	baby: 250,
	// Categorías extra sin precio canónico todavía — Diego ajusta manualmente.
	// Default Q435 para que nunca queden en 0 (anchor adult).
	polo: 435,
	vest: 435,
	training: 435,
	sweatshirt: 435,
	jacket: 435,
	shorts: 435
};

// ─── Modelo transform ──────────────────────────────────────────────────
function transformModelo(
	m: CatalogModeloRow,
	fam: CatalogRow,
	decisionBySku: Map<string, AuditDecision>,
	skuFallback: string
): Modelo {
	const gallery = Array.isArray(m.gallery) ? m.gallery : [];
	const sku = m.sku || skuFallback;

	// Hero = SIEMPRE la primera foto (index 0). Simplicidad visual + matches
	// la semántica del vault (R2 path `m{idx}.jpg` = primer asset del modelo).
	// Si Diego reordena, foto[0] cambia y automatically es el nuevo hero.
	const fotos: Photo[] = gallery.map((url, i) => ({
		id: `${sku}-p${i}`,
		url,
		isHero: i === 0,
		isDirty: !url.includes('?v=')
	}));

	const decision = decisionBySku.get(sku) || null;
	const status = deriveStatus(!!fam.published, decision);

	// Auto-fill price si no está en catalog. Default por modelo_type.
	const modeloType = (m.type as ModeloType) || 'fan_adult';
	const effectivePrice =
		typeof m.price === 'number' && m.price > 0
			? m.price
			: DEFAULT_PRICE_BY_TYPE[modeloType] ?? 450;

	return {
		sku,
		modeloType,
		sleeve: (m.sleeve as Sleeve) || null,
		status,
		fotos,
		price: effectivePrice,
		sizes: m.sizes,
		soldOut: false,
		notes: undefined
	};
}

// ─── Family transform ──────────────────────────────────────────────────
export function transformFamily(
	fam: CatalogRow,
	decisionBySku: Map<string, AuditDecision> = new Map()
): Family {
	const normalizedTeam = normalizeTeam(fam.team);
	const iso = getIso(fam.team);
	const group = getGroup(fam.team);

	const variantLower = (fam.variant || 'home').toLowerCase();
	const variantLabel =
		fam.variant_label || VARIANT_LABELS[variantLower] || fam.variant || '';

	let modelos: Modelo[];
	if (Array.isArray(fam.modelos) && fam.modelos.length > 0) {
		modelos = fam.modelos.map((m, idx) =>
			transformModelo(m, fam, decisionBySku, m.sku || `${fam.family_id}-m${idx}`)
		);
	} else if (Array.isArray(fam.gallery) && fam.gallery.length > 0) {
		// Legacy family sin modelos[] — construir 1 modelo sintético
		modelos = [
			transformModelo(
				{
					sku: fam.sku || fam.family_id,
					type: fam.category || 'fan_adult',
					sleeve: 'short',
					gallery: fam.gallery,
					hero_thumbnail: fam.hero_thumbnail
				},
				fam,
				decisionBySku,
				fam.sku || fam.family_id
			)
		];
	} else {
		modelos = [];
	}

	// primary_modelo_idx: index del modelo que es hero del card del grid
	let primaryModeloIdx: number | undefined;
	if (typeof fam.primary_modelo_idx === 'number') {
		primaryModeloIdx = fam.primary_modelo_idx;
	}

	return {
		id: fam.family_id,
		team: normalizedTeam || fam.team || 'Unknown',
		teamAliasEs: undefined,
		flagIso: iso,
		group,
		season: fam.season || '',
		variant: variantLower as Variant,
		variantLabel,
		published: !!fam.published,
		featured: !!fam.featured,
		archived: !!fam.archived,
		priority: fam._priority || 0,
		primaryModeloIdx,
		modelos,
		// Meta fields para pre-publish validation (L1)
		metaCountry: fam.meta_country ?? null,
		metaLeague: fam.meta_league ?? null,
		metaConfederation: fam.meta_confederation ?? null,
		wc2026Eligible: fam.wc2026_eligible ?? null,
		supplierGap: fam.supplier_gap ?? null
	};
}

// ─── Status mapping inverso (Family Status → AuditStatus hints) ───────
// Útil para writes que quieren inferir el AuditStatus desde una UI action.
export function auditStatusFromUIAction(
	action: 'verify' | 'flag' | 'skip' | 'rework'
): AuditStatus {
	switch (action) {
		case 'verify':
			return 'verified';
		case 'flag':
			return 'flagged';
		case 'skip':
			return 'skipped';
		case 'rework':
			return 'needs_rework';
	}
}

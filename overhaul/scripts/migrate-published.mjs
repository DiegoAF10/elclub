// Script de migración — lee catalog.json legacy, filtra published=true,
// transforma al schema del overhaul y escribe src/lib/data/published.ts.
//
// Uso:
//   cd overhaul && node scripts/migrate-published.mjs
//
// Reusable — correr de nuevo cuando haya más families publicadas.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CATALOG_PATH = 'C:/Users/Diego/elclub-catalogo-priv/data/catalog.json';
const WC_CLASSIFIED = 'C:/Users/Diego/elclub-catalogo-priv/data/wc2026-classified.json';
const FLAG_PACKAGE_DIR = path.join(__dirname, '..', 'node_modules/flag-icons/flags/4x3');
const FLAG_OUT_DIR = path.join(__dirname, '..', 'static/flags');
const OUT_FILE = path.join(__dirname, '..', 'src/lib/data/published.ts');

// ─── Mapping team canonical (EN) → ISO 3166 code ─────────────────────
const TEAM_TO_ISO = {
	Mexico: 'mx', 'South Africa': 'za', 'South Korea': 'kr', 'Czech Republic': 'cz',
	Canada: 'ca', 'Bosnia and Herzegovina': 'ba', 'Bosnia & Herzegovina': 'ba',
	Qatar: 'qa', Switzerland: 'ch', Brazil: 'br', Morocco: 'ma', Haiti: 'ht',
	Scotland: 'gb-sct', 'United States': 'us', USA: 'us', Paraguay: 'py',
	Australia: 'au', Turkey: 'tr', Germany: 'de', Curacao: 'cw', 'Ivory Coast': 'ci',
	Ecuador: 'ec', Netherlands: 'nl', Japan: 'jp', Sweden: 'se', Tunisia: 'tn',
	Belgium: 'be', Egypt: 'eg', Iran: 'ir', 'New Zealand': 'nz', Spain: 'es',
	'Cape Verde': 'cv', 'Saudi Arabia': 'sa', Uruguay: 'uy', France: 'fr',
	Senegal: 'sn', Iraq: 'iq', Norway: 'no', Argentina: 'ar', Algeria: 'dz',
	Austria: 'at', Jordan: 'jo', Portugal: 'pt', 'DR Congo': 'cd',
	Uzbekistan: 'uz', Colombia: 'co', England: 'gb-eng', Croatia: 'hr',
	Ghana: 'gh', Panama: 'pa',
	// Extras (no-Mundial pero en catalog)
	Albania: 'al', Italy: 'it', Poland: 'pl', Serbia: 'rs', Denmark: 'dk',
	Venezuela: 've', Peru: 'pe', Chile: 'cl', Bolivia: 'bo', Nigeria: 'ng',
	Cameroon: 'cm', Ukraine: 'ua', Russia: 'ru', Greece: 'gr', Hungary: 'hu',
	Ireland: 'ie', Wales: 'gb-wls', 'Northern Ireland': 'gb-nir',
	'UAE': 'ae', 'United Arab Emirates': 'ae'
};

// ─── Mapping team → grupo Mundial A-L ───────────────────────────────
const TEAM_TO_GROUP = {
	Mexico: 'A', 'South Africa': 'A', 'South Korea': 'A', 'Czech Republic': 'A',
	Canada: 'B', 'Bosnia and Herzegovina': 'B', 'Bosnia & Herzegovina': 'B',
	Qatar: 'B', Switzerland: 'B',
	Brazil: 'C', Morocco: 'C', Haiti: 'C', Scotland: 'C',
	'United States': 'D', USA: 'D', Paraguay: 'D', Australia: 'D', Turkey: 'D',
	Germany: 'E', Curacao: 'E', 'Ivory Coast': 'E', Ecuador: 'E',
	Netherlands: 'F', Japan: 'F', Sweden: 'F', Tunisia: 'F',
	Belgium: 'G', Egypt: 'G', Iran: 'G', 'New Zealand': 'G',
	Spain: 'H', 'Cape Verde': 'H', 'Saudi Arabia': 'H', Uruguay: 'H',
	France: 'I', Senegal: 'I', Iraq: 'I', Norway: 'I',
	Argentina: 'J', Algeria: 'J', Austria: 'J', Jordan: 'J',
	Portugal: 'K', 'DR Congo': 'K', Uzbekistan: 'K', Colombia: 'K',
	England: 'L', Croatia: 'L', Ghana: 'L', Panama: 'L'
};

// ─── Helpers ───────────────────────────────────────────────────────
function normalizeTeam(raw) {
	// Limpiar sufijos como "Algeria -" o "Algeria Jerseys"
	if (!raw) return null;
	let t = raw.trim();
	t = t.replace(/\s+Jerseys?$/i, '');
	t = t.replace(/\s+-+$/, '');
	t = t.trim();
	return t;
}

function getIso(team) {
	const normalized = normalizeTeam(team);
	return TEAM_TO_ISO[normalized] || null;
}

function getGroup(team) {
	const normalized = normalizeTeam(team);
	return TEAM_TO_GROUP[normalized] || '—';
}

function ensureFlag(iso) {
	if (!iso) return;
	const src = path.join(FLAG_PACKAGE_DIR, `${iso}.svg`);
	const dst = path.join(FLAG_OUT_DIR, `${iso}.svg`);
	if (fs.existsSync(dst)) return;
	if (!fs.existsSync(src)) {
		console.warn(`  ⚠️  Flag missing in package: ${iso}`);
		return;
	}
	fs.copyFileSync(src, dst);
	console.log(`  + Flag copied: ${iso}`);
}

// ─── Transform legacy family → overhaul Family ──────────────────────
function transformFamily(fam) {
	const normalizedTeam = normalizeTeam(fam.team);
	const iso = getIso(fam.team);
	const group = getGroup(fam.team);

	// Modelos: preservar si existen, sino construir sintético desde top-level
	let modelos;
	if (Array.isArray(fam.modelos) && fam.modelos.length > 0) {
		modelos = fam.modelos.map((m) => transformModelo(m, fam));
	} else if (Array.isArray(fam.gallery) && fam.gallery.length > 0) {
		modelos = [
			transformModelo(
				{
					sku: fam.sku || fam.family_id,
					type: fam.category || 'fan_adult',
					sleeve: 'short',
					gallery: fam.gallery,
					hero_thumbnail: fam.hero_thumbnail,
					price: fam.price,
					sizes: fam.sizes
				},
				fam
			)
		];
	} else {
		modelos = [];
	}

	return {
		id: fam.family_id,
		team: normalizedTeam || fam.team || 'Unknown',
		teamAliasEs: undefined,
		flagIso: iso,
		group,
		season: fam.season || '',
		variant: (fam.variant || 'home').toLowerCase(),
		variantLabel: fam.variant_label || fam.variant || '',
		published: !!fam.published,
		featured: !!fam.featured,
		archived: false,
		priority: fam._priority || 0,
		modelos
	};
}

function transformModelo(m, fam) {
	const hero = m.hero_thumbnail || fam.hero_thumbnail;
	const gallery = Array.isArray(m.gallery) ? m.gallery : [];
	const fotos = gallery.map((url, i) => ({
		id: `${m.sku || fam.family_id}-p${i}`,
		url,
		isHero: url === hero || i === 0,
		isDirty: !url.includes('?v=')
	}));

	return {
		sku: m.sku || fam.family_id,
		modeloType: m.type || 'fan_adult',
		sleeve: m.sleeve || null,
		status: 'live', // todos los published son live
		fotos,
		price: m.price,
		sizes: m.sizes,
		soldOut: false,
		notes: undefined
	};
}

// ─── Main ──────────────────────────────────────────────────────────
function main() {
	console.log('📦 Leyendo catalog.json legacy…');
	const catalog = JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf-8'));
	const published = catalog.filter((f) => f.published === true);
	console.log(`   ${catalog.length} families totales · ${published.length} publicadas`);

	console.log('\n🏳️  Copiando banderas necesarias…');
	const teams = [...new Set(published.map((f) => normalizeTeam(f.team)))].filter(Boolean);
	const isosToEnsure = teams.map(getIso).filter(Boolean);
	console.log(`   ${isosToEnsure.length} banderas únicas a preparar`);
	for (const iso of [...new Set(isosToEnsure)]) {
		ensureFlag(iso);
	}

	console.log('\n🔄 Transformando al schema overhaul…');
	const transformed = published.map(transformFamily);
	console.log(`   ${transformed.length} families migradas`);

	// Warnings sobre coverage
	const withFlag = transformed.filter((f) => f.flagIso).length;
	const withGroup = transformed.filter((f) => f.group !== '—').length;
	console.log(`   ${withFlag}/${transformed.length} con flag ISO`);
	console.log(`   ${withGroup}/${transformed.length} con grupo Mundial`);

	const missingFlag = transformed.filter((f) => !f.flagIso);
	if (missingFlag.length > 0) {
		console.log('\n   ⚠️  Teams sin flag ISO (agregar a TEAM_TO_ISO del script):');
		for (const f of missingFlag) {
			console.log(`      - "${f.team}" (family ${f.id})`);
		}
	}

	console.log('\n✍️  Escribiendo src/lib/data/published.ts…');
	const header = `// AUTO-GENERADO por scripts/migrate-published.mjs
// Re-correr con: node scripts/migrate-published.mjs
// Fuente: elclub-catalogo-priv/data/catalog.json (families con published=true)
// Generado: ${new Date().toISOString()}
// Total: ${transformed.length} families publicadas

import type { Family } from './types';

export const PUBLISHED_FAMILIES: Family[] = ${JSON.stringify(transformed, null, 2)};
`;
	fs.writeFileSync(OUT_FILE, header, 'utf-8');
	console.log(`   ✓ ${OUT_FILE}`);

	console.log('\n✅ Migración completa.');
	console.log(`\nResumen:\n  - ${transformed.length} families publicadas\n  - ${withFlag} con bandera\n  - ${withGroup} teams en grupo Mundial`);
}

main();

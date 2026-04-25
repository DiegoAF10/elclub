// Types para el prototipo. Post-MVP esto sale de un adapter sobre catalog.json.
// Banderas: usamos códigos ISO 3166-1 alpha-2 (+ subdivisions UK).
// Ver docs/flags.md para la tabla de mapping Mundial → ISO.

export type Status =
	| 'live' // published=true + verified
	| 'ready' // verified + pending publish
	| 'pending' // audit pending
	| 'rework' // needs_rework
	| 'flagged' // rejected
	| 'missing';

export type Variant = 'home' | 'away' | 'third' | 'goalkeeper' | 'special' | 'training';

export type ModeloType =
	| 'fan_adult'
	| 'player_adult'
	| 'retro_adult'
	| 'woman'
	| 'kid'
	| 'baby'
	| 'goalkeeper'
	// Categorías extendidas del catálogo (families legacy sin modelos[] donde
	// category pasa a ser el modelo type). Mantener sincronizado con
	// adapter/transform.ts y con erp/audit_db.py categorías aceptadas.
	| 'polo'
	| 'vest'
	| 'training'
	| 'sweatshirt'
	| 'jacket'
	| 'shorts'
	| 'adult';

export type Sleeve = 'short' | 'long' | null;

export interface Photo {
	id: string;
	url: string;
	isHero: boolean;
	isDirty: boolean;
}

export interface Modelo {
	sku: string;
	modeloType: ModeloType;
	sleeve: Sleeve;
	status: Status;
	fotos: Photo[];
	price?: number;
	sizes?: string;
	soldOut?: boolean;
	notes?: string;
}

export interface Family {
	id: string;
	team: string;
	teamAliasEs?: string;
	flagIso?: string; // ISO 3166-1 alpha-2 (ej. "ar", "br", "gb-sct")
	group: string; // A-L
	season: string;
	variant: Variant;
	variantLabel: string;
	published: boolean;
	featured?: boolean; // TOP badge
	archived?: boolean; // soft delete
	priority?: number; // orden manual vault
	/** Índice del modelo que se muestra como card principal en el vault grid */
	primaryModeloIdx?: number;
	modelos: Modelo[];
}

export interface MundialProgress {
	total: number;
	live: number;
	ready: number;
	pending: number;
	rework: number;
	flagged: number;
	missing: number;
}

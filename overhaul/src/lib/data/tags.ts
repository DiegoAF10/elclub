// Admin Web R7 (T1.3) — Tags system (many-to-many con cardinalidad).
// Spec: overhaul/docs/superpowers/specs/admin-web/types.ts (sección TAGS SYSTEM).
// Schema: tag_types, tags, jersey_tags (admin_web schema migration T1.1).

export type TagCardinality = 'one' | 'many';

export type TagTypeSlug =
	| 'competicion'
	| 'geografia_region'
	| 'pais'
	| 'liga'
	| 'era'
	| 'tipo_equipo'
	| 'variant_edicion'
	| 'comercial'
	| 'paleta_principal'
	| 'narrativa_cultural'
	| 'marca_tecnica';

export interface ConditionalRule {
	// Una de las tres puede aplicar (mutuamente excluyentes en el JSON):
	applies_when?: { tag_type: TagTypeSlug; tag_slug: string };
	forbidden_when?: { tag_type: TagTypeSlug; tag_slug: string };
	required_when?: { tag_type: TagTypeSlug; tag_slug: string };
}

export interface TagType {
	id: number;
	slug: TagTypeSlug;
	display_name: string;
	icon: string;
	cardinality: TagCardinality;
	display_order: number;
	conditional_rule?: ConditionalRule;
	description?: string;
	created_at: number;
	updated_at: number;
}

export interface Tag {
	id: number;
	type_id: number;
	type_slug: TagTypeSlug; // denormalized para queries rápidas
	slug: string;
	display_name: string;
	icon?: string;
	color?: string;
	is_auto_derived: boolean;
	derivation_rule?: AutoDerivationRule;
	is_deleted: boolean;
	display_order: number;
	count?: number; // cuántas jerseys tienen este tag (computed)
	created_at: number;
	updated_at: number;
}

export interface AutoDerivationRule {
	type: 'top_n_by_metric' | 'recent_n_days' | 'matches_filter' | 'custom_sql';
	config: Record<string, unknown>;
	refresh_interval: 'hourly' | 'daily' | 'weekly';
}

export interface JerseyTag {
	family_id: string;
	tag_id: number;
	assigned_at: number;
	assigned_by: 'manual' | string; // 'auto:rule_id' | 'bulk:user'
}

/**
 * Resultado de validación al asignar un tag.
 * Si valid=false, el reason indica el motivo y conflicting_tags
 * (si aplica) lista los tags que están en conflicto.
 */
export interface TagAssignmentValidation {
	valid: boolean;
	reason?: 'cardinality_violation' | 'forbidden_by_conditional' | 'tag_deleted' | 'jersey_not_found';
	conflicting_tags?: Tag[];
	message?: string;
}

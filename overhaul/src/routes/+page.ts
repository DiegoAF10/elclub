// /  — Page data loader · post sidebar reorg (Iteración Continuous · 2026-04-28).
//
// Antes cargaba families para el Audit interface (que vivía en este +page.svelte).
// Audit se mudó a /admin-web/audit · su propio +page.ts carga families ahí.
//
// Este page raíz ahora es un dispatcher de shells (Dashboard/Comercial/IMP/FIN).
// No requiere data del adapter — los shells de cada módulo cargan su propia
// data on-mount via adapter calls. Devolvemos solo metadata mínima por compat
// con el sistema de SvelteKit (al menos el load function existe para SSR=false).

import type { PageLoad } from './$types';
import { adapter } from '$lib/adapter';

export interface PageData {
	adapterPlatform: 'browser' | 'tauri';
}

export const load: PageLoad = async (): Promise<PageData> => {
	return {
		adapterPlatform: adapter.capabilities.platform
	};
};

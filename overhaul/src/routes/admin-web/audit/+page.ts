// /admin-web/audit — load families desde adapter (idéntico al loader del / raíz
// pre-reorg). Audit interface raíz se mudó a esta ruta cuando ADM-Sidebar-Reorg
// (Iteración Continuous · 2026-04-28) eliminó el item Audit del sidebar global.
//
// El +page.svelte de esta ruta wrappea ListPane + DetailPane + FamilyPdpPane —
// los mismos componentes que vivían en /+page.svelte raíz.

import type { PageLoad } from './$types';
import { adapter } from '$lib/adapter';
import type { Family } from '$lib/data/types';

export interface PageData {
	families: Family[];
	loadError?: string;
	adapterPlatform: 'browser' | 'tauri';
}

export const load: PageLoad = async (): Promise<PageData> => {
	try {
		const families = await adapter.listFamilies();
		return {
			families,
			adapterPlatform: adapter.capabilities.platform
		};
	} catch (err) {
		return {
			families: [],
			loadError: err instanceof Error ? err.message : String(err),
			adapterPlatform: adapter.capabilities.platform
		};
	}
};

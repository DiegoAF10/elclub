// /admin-web/mundial — load families para MundialCoverageModal embedded.
// Mismo loader que /admin-web/audit (ambos consumen el catálogo completo).

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

// Page data loader — corre en el cliente (ssr=false en +layout.ts).
// Llama al adapter para traer las families y las hace disponibles via `data` prop.

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
		// Cargamos TODAS las families del catálogo — el ListPane agrupa por grupo
		// Mundial A-L primero (lo relevante pre-scrape/audit), y el resto queda en
		// "—" para cuando empiece a llenarse el catálogo entero.
		const families = await adapter.listFamilies();
		return {
			families,
			adapterPlatform: adapter.capabilities.platform
		};
	} catch (err) {
		// Non-fatal: devolvemos error + families=[] para que la UI muestre un state legible
		// en vez de romperse con un 500 page blank.
		return {
			families: [],
			loadError: err instanceof Error ? err.message : String(err),
			adapterPlatform: adapter.capabilities.platform
		};
	}
};

// Adapter facade — environment detection + single export.
//
// Usage:
//   import { adapter } from '$lib/adapter';
//   const families = await adapter.listFamilies({ published: true });
//
// En `npm run dev`              → browserAdapter (reads via vite plugin)
// En `npx tauri dev` o .msi     → tauriAdapter (reads via Rust commands)

import type { Adapter } from './types';
import { browserAdapter } from './browser';
import { tauriAdapter, isTauri } from './tauri';

export * from './types';
export { isTauri };

function pickAdapter(): Adapter {
	if (isTauri()) {
		if (import.meta.env.DEV) {
			// eslint-disable-next-line no-console
			console.info('[erp-adapter] Using tauri adapter (native runtime detected)');
		}
		return tauriAdapter;
	}
	if (import.meta.env.DEV) {
		// eslint-disable-next-line no-console
		console.info('[erp-adapter] Using browser adapter (no Tauri runtime)');
	}
	return browserAdapter;
}

// Lazy init — se evalúa la primera vez que se accede, no a import time.
// Esto permite que SSR no explote al tocar `window`.
let _instance: Adapter | null = null;

export const adapter: Adapter = new Proxy({} as Adapter, {
	get(_target, prop: keyof Adapter) {
		if (!_instance) _instance = pickAdapter();
		return _instance[prop];
	}
});

// Helper para tests / invalidación manual
export function _resetAdapter() {
	_instance = null;
}

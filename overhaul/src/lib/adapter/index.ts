// Adapter facade — environment detection + single export.
//
// Usage:
//   import { adapter } from '$lib/adapter';
//   const families = await adapter.listFamilies({ published: true });
//
// En `npm run dev`              → browserAdapter (reads via vite plugin)
// En `npx tauri dev` o .msi     → tauriAdapter (reads via Rust commands)

import type { Adapter, AdminWebTauriCommands } from './types';
import { browserAdapter, adminWebBrowser } from './browser';
import { tauriAdapter, adminWebTauri, isTauri } from './tauri';

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

// ─── Admin Web R7 (T1.4) — facade separado ─────────────────────────────
// adminWebTauri / adminWebBrowser implementan AdminWebTauriCommands en
// lugar de extender Adapter (60+ commands de un dominio nuevo). Mismo
// patrón Proxy + lazy init para detección de runtime.
function pickAdminWebAdapter(): AdminWebTauriCommands {
	return isTauri() ? adminWebTauri : adminWebBrowser;
}

let _adminWebInstance: AdminWebTauriCommands | null = null;

export const adminWeb: AdminWebTauriCommands = new Proxy({} as AdminWebTauriCommands, {
	get(_target, prop: keyof AdminWebTauriCommands) {
		if (!_adminWebInstance) _adminWebInstance = pickAdminWebAdapter();
		return _adminWebInstance[prop];
	}
});

// Helper para tests / invalidación manual
export function _resetAdapter() {
	_instance = null;
	_adminWebInstance = null;
}

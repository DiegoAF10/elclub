// Simple Svelte 5 reactive counter that SalesTab listens to.
// SettingsTab + any other component can call `bumpSalesSync()` to trigger SalesTab reload.

import { writable } from 'svelte/store';

export const salesSyncBumper = writable(0);

export function bumpSalesSync() {
  salesSyncBumper.update(n => n + 1);
}

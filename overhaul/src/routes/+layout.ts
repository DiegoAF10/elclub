// SPA mode — renderizado 100% en cliente.
// Requerido porque:
//   1. El adapter browser usa `fetch('/__erp/catalog')` que solo existe en dev server runtime.
//   2. Fase 2 (Tauri) requiere adapter-static con fallback SPA.
//
// Sin SSR nos ahorramos el "adaptar el data source para server-side" y alineamos
// dev + prod en un solo flow (client fetches → adapter → data).

export const ssr = false;
export const prerender = false;

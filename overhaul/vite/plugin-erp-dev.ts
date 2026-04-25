// Vite dev plugin — sirve endpoints /__erp/* que leen archivos del repo hermano.
// Solo activo en dev (`vite dev`). En build para Tauri se omite.
//
// Endpoints:
//   GET /__erp/catalog          → catalog.json de elclub-catalogo-priv/data/
//   GET /__erp/decisions        → 501 (stub — Fase 2 lee SQLite via Tauri)
//   GET /__erp/photo-actions    → 501 (idem)
//
// Resolución de paths: el plugin asume que el workspace está organizado como:
//   C:\Users\Diego\el-club\overhaul\           (este proyecto)
//   C:\Users\Diego\elclub-catalogo-priv\       (repo hermano)
// y toma el path relativo `../../elclub-catalogo-priv/data/catalog.json`.
//
// Override opcional via env var ERP_CATALOG_PATH si Diego mueve los repos.

import fs from 'node:fs';
import path from 'node:path';
import type { Plugin, ViteDevServer, Connect } from 'vite';

interface PluginOptions {
	/** Absolute path al catalog.json. Default: ../../elclub-catalogo-priv/data/catalog.json */
	catalogPath?: string;
	/** Absolute path a elclub.db. Default: ../erp/elclub.db */
	dbPath?: string;
}

function resolveDefault(relative: string): string {
	// __dirname en este archivo TS lo resuelve vite al compilar el config.
	// Como fallback, usamos process.cwd() (que es overhaul/ al correr `npm run dev`).
	return path.resolve(process.cwd(), relative);
}

function sendJson(res: Parameters<Connect.NextHandleFunction>[1], data: unknown, status = 200) {
	res.statusCode = status;
	res.setHeader('Content-Type', 'application/json; charset=utf-8');
	res.setHeader('Cache-Control', 'no-cache');
	res.end(JSON.stringify(data));
}

function sendText(res: Parameters<Connect.NextHandleFunction>[1], text: string, status: number) {
	res.statusCode = status;
	res.setHeader('Content-Type', 'text/plain; charset=utf-8');
	res.end(text);
}

export function erpDevPlugin(opts: PluginOptions = {}): Plugin {
	// cwd al correr `npm run dev` es `overhaul/`. Repo hermano está 2 niveles arriba:
	//   overhaul/                    → cwd
	//   overhaul/../                 → el-club/
	//   overhaul/../../              → Diego/ (donde viven ambos repos)
	const catalogPath =
		opts.catalogPath ||
		process.env.ERP_CATALOG_PATH ||
		resolveDefault('../../elclub-catalogo-priv/data/catalog.json');

	const dbPath = opts.dbPath || process.env.ERP_DB_PATH || resolveDefault('../erp/elclub.db');

	return {
		name: 'erp-dev-plugin',
		apply: 'serve', // solo en dev, no en build
		configureServer(server: ViteDevServer) {
			server.middlewares.use('/__erp/catalog', (_req, res, next) => {
				try {
					if (!fs.existsSync(catalogPath)) {
						return sendJson(
							res,
							{
								error: 'catalog.json not found',
								searchedAt: catalogPath,
								hint: 'Set ERP_CATALOG_PATH env var or pass catalogPath to erpDevPlugin()'
							},
							404
						);
					}
					// Stream-friendly: sendFile-like pero manual porque es JSON con headers específicos
					const data = fs.readFileSync(catalogPath, 'utf-8');
					res.statusCode = 200;
					res.setHeader('Content-Type', 'application/json; charset=utf-8');
					res.setHeader('Cache-Control', 'no-cache');
					res.setHeader('X-ERP-Source', 'catalog.json');
					res.end(data);
				} catch (err) {
					sendJson(res, { error: String(err) }, 500);
					next();
				}
			});

			// Stub endpoints — Fase 2 los cablea via Tauri Rust commands.
			// En Fase 1 el browser adapter maneja 501/404 gracefully (empty decisions).
			server.middlewares.use('/__erp/decisions', (_req, res) => {
				sendJson(
					res,
					{
						error: 'not_implemented_in_browser',
						hint:
							'audit_decisions read requires the Tauri build (Phase 2). ' +
							'Browser mode falls back to status derived from `published` flag.',
						dbPath
					},
					501
				);
			});

			server.middlewares.use('/__erp/photo-actions', (_req, res) => {
				sendJson(res, [], 200); // empty array is graceful — UI ignora
			});

			// Debug endpoint — útil para sanity check
			server.middlewares.use('/__erp/status', (_req, res) => {
				sendJson(res, {
					ok: true,
					plugin: 'erp-dev-plugin',
					catalogPath,
					catalogExists: fs.existsSync(catalogPath),
					dbPath,
					dbExists: fs.existsSync(dbPath),
					catalogSizeBytes: fs.existsSync(catalogPath) ? fs.statSync(catalogPath).size : null,
					note: 'Phase 1 — catalog reads only. Writes require Tauri build.'
				});
			});

			// Log al arrancar el dev server para que Diego sepa qué pasa.
			const hasCatalog = fs.existsSync(catalogPath);
			const sizeKb = hasCatalog ? Math.round(fs.statSync(catalogPath).size / 1024) : 0;
			console.log(
				`\n  \x1b[36m[erp-dev-plugin]\x1b[0m ` +
					(hasCatalog
						? `serving catalog.json (${sizeKb} KB) from ${catalogPath}`
						: `\x1b[33m⚠ catalog.json not found\x1b[0m at ${catalogPath}`)
			);
			console.log(`  \x1b[36m[erp-dev-plugin]\x1b[0m endpoints: /__erp/catalog /__erp/status\n`);
		}
	};
}

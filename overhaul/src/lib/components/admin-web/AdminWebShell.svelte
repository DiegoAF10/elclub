<!--
	AdminWebShell — Container que orquesta sidebar interno + breadcrumb + body.

	Layout:
		┌────────────────────────────────────────────────────────────────────┐
		│ AdminWebSidebar (200px) │ BreadcrumbBar                            │
		│ home, vault, stock,      ├──────────────────────────────────────────┤
		│ mystery, site, sistema   │ {@render children}  ← sub-route content  │
		└────────────────────────────────────────────────────────────────────┘

	Section/tab derivado del URL ($page.url.pathname). Para
	'/admin-web/vault/queue' → section='vault', tab='queue'.

	LocalStorage:
		- admin-web:lastSection      → último top-level visitado ('vault'|'stock'|...)
		- admin-web:lastTab:{section} → último tab visitado dentro de cada section

	Cuando el user entra a `/admin-web/[section]` sin tab, el redirect del
	+page.svelte de cada section va al default. Si quisiéramos restorear el
	último tab, podríamos leer localStorage en esos +page redirects (T2.5+).
-->
<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import AdminWebSidebar from './AdminWebSidebar.svelte';
	import BreadcrumbBar from './BreadcrumbBar.svelte';
	import AdminWebCommandPalette from './AdminWebCommandPalette.svelte';

	let { children } = $props();

	// ─── Command palette + atajos vim-style ───────────────────────────
	let paletteOpen = $state(false);
	let lastG = 0; // timestamp del último 'g' presionado, para chord 'g X'
	const G_WINDOW_MS = 800;

	function isTypingTarget(t: EventTarget | null): boolean {
		if (!(t instanceof HTMLElement)) return false;
		const tag = t.tagName.toLowerCase();
		return tag === 'input' || tag === 'textarea' || t.isContentEditable;
	}

	const G_BINDINGS: Record<string, string> = {
		h: '/admin-web/home',
		v: '/admin-web/vault',
		s: '/admin-web/stock',
		m: '/admin-web/mystery',
		w: '/admin-web/site',
		c: '/admin-web/sistema'
	};

	function handleGlobalKey(e: KeyboardEvent) {
		// Ignorar mientras se tipea en input/textarea
		if (isTypingTarget(e.target)) return;

		// ⌘K / Ctrl+K toggle palette
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
			e.preventDefault();
			paletteOpen = !paletteOpen;
			return;
		}

		if (paletteOpen) return; // los atajos no funcionan con palette abierto (palette maneja Esc/arrows)

		const now = Date.now();

		// Chord 'g X'
		if (e.key.toLowerCase() === 'g' && !e.metaKey && !e.ctrlKey && !e.altKey) {
			lastG = now;
			return;
		}
		if (lastG && now - lastG < G_WINDOW_MS) {
			const target = G_BINDINGS[e.key.toLowerCase()];
			if (target) {
				e.preventDefault();
				lastG = 0;
				void goto(target);
				return;
			}
			lastG = 0;
		}
	}

	// Derivar section + tab del pathname. Pathname formato esperado:
	//   /admin-web                    → section='home', tab=undefined
	//   /admin-web/home               → section='home'
	//   /admin-web/vault              → section='vault', tab=undefined (redirect)
	//   /admin-web/vault/queue        → section='vault', tab='queue'
	const currentSection = $derived.by((): string => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		// parts[0] = 'admin-web', parts[1] = section
		return parts[1] ?? 'home';
	});

	const currentTab = $derived.by((): string | undefined => {
		const parts = $page.url.pathname.split('/').filter(Boolean);
		return parts[2];
	});

	// LocalStorage tracking — se ejecuta cuando section/tab cambian.
	// Solo persistimos cuando la URL tiene un tab válido (no en redirects).
	$effect(() => {
		if (typeof localStorage === 'undefined') return;
		try {
			localStorage.setItem('admin-web:lastSection', currentSection);
			if (currentTab) {
				localStorage.setItem(`admin-web:lastTab:${currentSection}`, currentTab);
			}
		} catch {
			// localStorage puede fallar en SSR o por quota — no es crítico
		}
	});
</script>

<svelte:window onkeydown={handleGlobalKey} />

<div class="flex h-full min-h-0">
	<AdminWebSidebar section={currentSection} />
	<div class="flex min-w-0 flex-1 flex-col">
		<BreadcrumbBar section={currentSection} tab={currentTab} />
		<main class="min-h-0 flex-1 overflow-auto">
			{@render children?.()}
		</main>
	</div>
</div>

<AdminWebCommandPalette open={paletteOpen} onClose={() => (paletteOpen = false)} />

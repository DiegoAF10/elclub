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
	import AdminWebSidebar from './AdminWebSidebar.svelte';
	import BreadcrumbBar from './BreadcrumbBar.svelte';

	let { children } = $props();

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

<div class="flex h-full min-h-0">
	<AdminWebSidebar section={currentSection} />
	<div class="flex min-w-0 flex-1 flex-col">
		<BreadcrumbBar section={currentSection} tab={currentTab} />
		<main class="min-h-0 flex-1 overflow-auto">
			{@render children?.()}
		</main>
	</div>
</div>

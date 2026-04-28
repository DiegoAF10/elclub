<!--
	Layout de Admin Web — monta AdminWebShell que orquesta sidebar interno +
	breadcrumb + body slot. Todo descendant route recibe el chrome del módulo.

	El root layout (routes/+layout.svelte) renderiza solo {children} sin chrome
	global, así que Admin Web NO compite con la chrome del +page.svelte raíz
	(que tiene su propio Sidebar global). Dos URL spaces disjuntos.
-->
<script lang="ts">
	import AdminWebShell from '$lib/components/admin-web/AdminWebShell.svelte';

	let { children } = $props();
</script>

<div class="h-screen w-screen bg-[var(--color-bg)] text-[var(--color-text-primary)]">
	<AdminWebShell>
		{@render children?.()}
	</AdminWebShell>
</div>

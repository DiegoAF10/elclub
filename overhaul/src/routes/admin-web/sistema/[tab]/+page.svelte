<!-- TODO: T2.7 — SistemaShell cascarón con tab del URL -->
<script lang="ts">
	import { page } from '$app/stores';
	import SistemaShell from '$lib/components/admin-web/sistema/SistemaShell.svelte';
	let tab = $derived($page.params.tab);
</script>

<SistemaShell {tab} />

<!-- TODO: T2.7 — StockShell cascarón con tab del URL -->
<script lang="ts">
	import { page } from '$app/stores';
	import StockShell from '$lib/components/admin-web/stock/StockShell.svelte';
	let tab = $derived($page.params.tab);
</script>

<StockShell {tab} />

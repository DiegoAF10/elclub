<!-- TODO: T2.7 — SiteShell cascarón con tab del URL -->
<script lang="ts">
	import { page } from '$app/stores';
	import SiteShell from '$lib/components/admin-web/site/SiteShell.svelte';
	let tab = $derived($page.params.tab);
</script>

<SiteShell {tab} />

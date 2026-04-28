<!-- TODO: T2.7 — MysteryShell cascarón con tab del URL -->
<script lang="ts">
	import { page } from '$app/stores';
	import MysteryShell from '$lib/components/admin-web/mystery/MysteryShell.svelte';
	let tab = $derived($page.params.tab);
</script>

<MysteryShell {tab} />

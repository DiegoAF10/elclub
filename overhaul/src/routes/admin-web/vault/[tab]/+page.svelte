<!-- TODO: T2.5/T4.1 — VaultShell con tab desde URL param -->
<script lang="ts">
	import { page } from '$app/stores';
	import VaultShell from '$lib/components/admin-web/vault/VaultShell.svelte';
	let tab = $derived($page.params.tab);
</script>

<VaultShell {tab} />

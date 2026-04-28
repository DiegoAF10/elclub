<!-- TODO: T2.5 — redirect a /admin-web/vault/queue (default tab) -->
<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => {
		void goto('/admin-web/vault/queue', { replaceState: true });
	});
</script>

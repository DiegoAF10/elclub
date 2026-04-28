<!-- TODO: T2.5 — redirect a /admin-web/stock/drops -->
<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => {
		void goto('/admin-web/stock/drops', { replaceState: true });
	});
</script>

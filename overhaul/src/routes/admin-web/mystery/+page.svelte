<!-- TODO: T2.5 — redirect a /admin-web/mystery/pool -->
<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => {
		void goto('/admin-web/mystery/pool', { replaceState: true });
	});
</script>

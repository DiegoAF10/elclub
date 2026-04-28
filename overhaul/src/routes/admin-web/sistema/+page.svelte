<!-- TODO: T2.5 — redirect a /admin-web/sistema/status -->
<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => {
		void goto('/admin-web/sistema/status', { replaceState: true });
	});
</script>

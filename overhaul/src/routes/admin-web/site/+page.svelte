<!-- TODO: T2.5 — redirect a /admin-web/site/paginas -->
<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => {
		void goto('/admin-web/site/paginas', { replaceState: true });
	});
</script>

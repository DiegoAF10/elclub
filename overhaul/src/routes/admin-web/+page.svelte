<!-- TODO: T2.5 — redirect a /admin-web/home -->
<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => {
		void goto('/admin-web/home', { replaceState: true });
	});
</script>

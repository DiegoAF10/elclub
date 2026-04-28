<!-- /admin-web/stock → redirect a last-tab o default 'drops'. -->
<script lang="ts">
	import { goto } from '$app/navigation';

	$effect(() => {
		let target = 'drops';
		if (typeof localStorage !== 'undefined') {
			try {
				const last = localStorage.getItem('admin-web:lastTab:stock');
				if (last) target = last;
			} catch {
				/* fallback */
			}
		}
		void goto(`/admin-web/stock/${target}`, { replaceState: true });
	});
</script>

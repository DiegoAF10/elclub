<!-- /admin-web/site → redirect a last-tab o default 'paginas'. -->
<script lang="ts">
	import { goto } from '$app/navigation';

	$effect(() => {
		let target = 'paginas';
		if (typeof localStorage !== 'undefined') {
			try {
				const last = localStorage.getItem('admin-web:lastTab:site');
				if (last) target = last;
			} catch {
				/* fallback */
			}
		}
		void goto(`/admin-web/site/${target}`, { replaceState: true });
	});
</script>

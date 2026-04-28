<!-- /admin-web/mystery → redirect a last-tab o default 'pool'. -->
<script lang="ts">
	import { goto } from '$app/navigation';

	$effect(() => {
		let target = 'pool';
		if (typeof localStorage !== 'undefined') {
			try {
				const last = localStorage.getItem('admin-web:lastTab:mystery');
				if (last) target = last;
			} catch {
				/* fallback */
			}
		}
		void goto(`/admin-web/mystery/${target}`, { replaceState: true });
	});
</script>

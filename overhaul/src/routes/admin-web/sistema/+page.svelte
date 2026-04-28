<!-- /admin-web/sistema → redirect a last-tab o default 'status'. -->
<script lang="ts">
	import { goto } from '$app/navigation';

	$effect(() => {
		let target = 'status';
		if (typeof localStorage !== 'undefined') {
			try {
				const last = localStorage.getItem('admin-web:lastTab:sistema');
				if (last) target = last;
			} catch {
				/* fallback */
			}
		}
		void goto(`/admin-web/sistema/${target}`, { replaceState: true });
	});
</script>

<!--
	/admin-web/vault → redirect al tab apropiado.
	Lee localStorage 'admin-web:lastTab:vault' (set por AdminWebShell). Si no
	existe, usa el default 'queue'. Permite que recargar /admin-web/vault
	te lleve donde estabas, no al default.
-->
<script lang="ts">
	import { goto } from '$app/navigation';

	$effect(() => {
		let target = 'queue';
		if (typeof localStorage !== 'undefined') {
			try {
				const last = localStorage.getItem('admin-web:lastTab:vault');
				if (last) target = last;
			} catch {
				// fallback al default
			}
		}
		void goto(`/admin-web/vault/${target}`, { replaceState: true });
	});
</script>

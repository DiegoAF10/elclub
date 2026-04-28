<!--
	/admin-web/inventario — cascarón inicial. Reemplaza el ex-`/admin-web/stock/`
	por decisión D1=c (Diego, 2026-04-28): Inventario absorbe el rol de Stock.

	Funcionalidad por definir — pendiente brainstorm dedicado INV-Rx que defina:
		- Stock real (jerseys físicos en almacén Diego)
		- Sync con Comercial sales (decrementar al ship)
		- Alertas low-stock
		- Trigger a Importaciones para repedido
		- Si absorbe el dominio "jerseys garantizadas Q475 con drops" del ex-Stock R7.1

	Mientras tanto, este cascarón aparece en el sidebar Admin Web > Inventario
	para que Diego sepa que el slot existe y reservado para próxima iteración.
-->
<script lang="ts">
	import PlaceholderPanel from '$lib/components/admin-web/shared/PlaceholderPanel.svelte';
</script>

<PlaceholderPanel
	title="INVENTARIO"
	future="próxima iteración (INV-Rx · brainstorm pendiente)"
	description="Control de unidades físicas · sync con Comercial sales · alertas low-stock · trigger a Importaciones para repedido. Absorbe el ex-Stock (jerseys garantizadas Q475 con drops) según decisión D1=c."
/>

# Banderas — referencia rápida

Usamos [`flag-icons` by lipis](https://github.com/lipis/flag-icons) — paquete oficial, ISO 3166-1
alpha-2 codes, maintained, 271 banderas.

## Cómo agregar más banderas

El paquete completo está en `node_modules/flag-icons/flags/4x3/*.svg`. Solo copiamos
las que usamos activamente a `static/flags/` para reducir bundle.

```bash
# Ejemplo: copiar AR, BR y otros nuevos
cd overhaul
for code in ar br cl pe; do
  cp "node_modules/flag-icons/flags/4x3/${code}.svg" "static/flags/${code}.svg"
done
```

Para copiar TODAS de una (bundle grande, pero simple):

```bash
cp -r node_modules/flag-icons/flags/4x3/* static/flags/
```

## Mapping Mundial 2026 → ISO code

| Team (canonical EN)       | ISO code  |
| -------------------------- | --------- |
| Mexico                     | `mx`      |
| South Africa               | `za`      |
| South Korea                | `kr`      |
| Czech Republic             | `cz`      |
| Canada                     | `ca`      |
| Bosnia and Herzegovina     | `ba`      |
| Qatar                      | `qa`      |
| Switzerland                | `ch`      |
| Brazil                     | `br`      |
| Morocco                    | `ma`      |
| Haiti                      | `ht`      |
| Scotland                   | `gb-sct`  |
| United States              | `us`      |
| Paraguay                   | `py`      |
| Australia                  | `au`      |
| Turkey                     | `tr`      |
| Germany                    | `de`      |
| Curacao                    | `cw`      |
| Ivory Coast                | `ci`      |
| Ecuador                    | `ec`      |
| Netherlands                | `nl`      |
| Japan                      | `jp`      |
| Sweden                     | `se`      |
| Tunisia                    | `tn`      |
| Belgium                    | `be`      |
| Egypt                      | `eg`      |
| Iran                       | `ir`      |
| New Zealand                | `nz`      |
| Spain                      | `es`      |
| Cape Verde                 | `cv`      |
| Saudi Arabia               | `sa`      |
| Uruguay                    | `uy`      |
| France                     | `fr`      |
| Senegal                    | `sn`      |
| Iraq                       | `iq`      |
| Norway                     | `no`      |
| Argentina                  | `ar`      |
| Algeria                    | `dz`      |
| Austria                    | `at`      |
| Jordan                     | `jo`      |
| Portugal                   | `pt`      |
| DR Congo                   | `cd`      |
| Uzbekistan                 | `uz`      |
| Colombia                   | `co`      |
| England                    | `gb-eng`  |
| Croatia                    | `hr`      |
| Ghana                      | `gh`      |
| Panama                     | `pa`      |

## Uso en código

En `types.ts`:
```ts
export interface Family {
  flagIso?: string; // ISO 3166-1 alpha-2 code (ej. "ar", "br", "gb-sct")
  ...
}
```

En componente:
```svelte
{#if family.flagIso}
  <img src="/flags/{family.flagIso}.svg" alt="" class="h-4 w-6 rounded-[2px]" />
{/if}
```

## Variantes disponibles en el paquete

- `flags/4x3/` — aspecto 4:3 (default, mejor para la mayoría de usos)
- `flags/1x1/` — cuadradas (para badges circulares)
- `css/` — también hay CSS classes si preferís cargarlas así

## Links de referencia

- Repo: https://github.com/lipis/flag-icons
- NPM: https://www.npmjs.com/package/flag-icons
- Docs: https://flagicons.lipis.dev/

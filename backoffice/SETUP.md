# El Club Backoffice — Setup

Worker de Cloudflare para crear checkout sessions de Recurrente.

## Requisitos

- Node.js 18+
- Cuenta de Cloudflare (gratis)
- API keys de Recurrente (cuenta SEPARADA de VENTUS — keys propias de El Club)

## Setup

```bash
cd backoffice

# Instalar wrangler (si no lo tenés)
npm install -g wrangler

# Login a Cloudflare
npx wrangler login

# Configurar secrets (keys de la cuenta Recurrente de El Club, NO las de VENTUS)
npx wrangler secret put RECURRENTE_PUBLIC_KEY
# → Pegar: pk_live_xxxxx (de app.recurrente.com → Desarrolladores → API)

npx wrangler secret put RECURRENTE_SECRET_KEY
# → Pegar: sk_live_xxxxx (de app.recurrente.com → Desarrolladores → API)

# Deploy
npx wrangler deploy
```

## Despues del deploy

1. Anotar la URL del Worker (ej: `https://elclub-backoffice.diegoaf10.workers.dev`)
2. Actualizar `ELCLUB_API_URL` en `assets/js/checkout.js` con esa URL
3. Probar con tarjeta de prueba: `4242 4242 4242 4242`

## Desarrollo local

```bash
npx wrangler dev
# Worker corre en http://localhost:8787
```

## Notas

- El Club tiene su propia cuenta de Recurrente (SEPARADA de VENTUS). Keys en app.recurrente.com → Desarrolladores → API
- El Worker solo crea checkout sessions — no maneja webhooks (Diego monitorea en dashboard de Recurrente)
- CORS configurado para elclub.club + localhost (desarrollo)

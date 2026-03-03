# El Club Backoffice — Setup

Worker de Cloudflare para crear checkout sessions de Recurrente.

## Requisitos

- Node.js 18+
- Cuenta de Cloudflare (gratis)
- API keys de Recurrente (mismas de VENTUS)

## Setup

```bash
cd backoffice

# Instalar wrangler (si no lo tenés)
npm install -g wrangler

# Login a Cloudflare
npx wrangler login

# Configurar secrets (usar las mismas keys de Recurrente que VENTUS)
npx wrangler secret put RECURRENTE_PUBLIC_KEY
# → Pegar: pk_live_xxxxx

npx wrangler secret put RECURRENTE_SECRET_KEY
# → Pegar: sk_live_xxxxx

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

- Las API keys de Recurrente son las mismas que usa VENTUS (cuenta compartida)
- El Worker solo crea checkout sessions — no maneja webhooks (Diego monitorea en dashboard de Recurrente)
- CORS configurado para elclub.club + localhost (desarrollo)

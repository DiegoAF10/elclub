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

## Secrets opcionales (para funcionalidad completa)

```bash
# Email de confirmación al cliente (Resend.com — gratis hasta 3k emails/mes)
npx wrangler secret put RESEND_API_KEY

# Email de Diego para alertas de venta
npx wrangler secret put DIEGO_EMAIL

# GitHub PAT para actualizar stock en products.json automáticamente
npx wrangler secret put GITHUB_TOKEN

# Svix webhook secret para verificar pagos (Recurrente → Desarrolladores → Webhooks)
npx wrangler secret put WEBHOOK_SECRET

# Admin key para crear cupones
npx wrangler secret put ADMIN_KEY
```

## Después del deploy

1. Anotar la URL del Worker (ej: `https://elclub-backoffice.diegoaf10.workers.dev`)
2. Actualizar `BACKOFFICE_URL` en `assets/js/cart.js` con esa URL
3. Configurar webhook en Recurrente: Dashboard → Desarrolladores → Webhooks → URL: `https://elclub-backoffice.diegoaf10.workers.dev/webhook/recurrente`
4. Probar con tarjeta de prueba: `4242 4242 4242 4242`

## Desarrollo local

```bash
npx wrangler dev
# Worker corre en http://localhost:8787
```

## Notas

- El Club tiene su propia cuenta de Recurrente (SEPARADA de VENTUS). Keys en app.recurrente.com → Desarrolladores → API
- El Worker crea checkout sessions + recibe webhooks de pago + actualiza stock + envía emails
- CORS configurado para elclub.club + localhost (desarrollo)
- Si `BACKOFFICE_URL` está vacío en cart.js, el botón "Pagar con tarjeta" no se muestra — solo WhatsApp
- Fallback automático: si Recurrente falla, ofrece continuar por WhatsApp

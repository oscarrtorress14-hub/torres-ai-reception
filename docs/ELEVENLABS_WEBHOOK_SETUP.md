# Preparación del webhook de ElevenLabs

## Integración en `app/main.py`

Añadir junto a los imports:

```python
from .elevenlabs_webhook import router as elevenlabs_webhook_router
```

Después de crear `app = FastAPI(...)`:

```python
app.include_router(elevenlabs_webhook_router)
```

## Configuración

Definir `ELEVENLABS_WEBHOOK_SECRET` como variable de entorno del backend usando
el secreto HMAC generado por ElevenLabs. Nunca guardarlo en Git ni compartirlo por chat.

Configurar el webhook posterior a la llamada para `post_call_transcription` y,
si interesa registrar fallos de inicio, `call_initiation_failure`.
No activar `post_call_audio` en esta fase.

## Qué hace este módulo

- Verifica `ElevenLabs-Signature` con HMAC-SHA256 y tolerancia de 30 minutos.
- Rechaza cuerpos mayores de 256 KiB.
- Evita procesar dos veces el mismo evento/conversación.
- Guarda únicamente metadatos técnicos mínimos en `call_events`.
- No guarda audio, transcripciones, números telefónicos ni datos de clientes.

## Antes de producción

1. PostgreSQL persistente en lugar de SQLite local.
2. Autenticación del panel y autorización por empresa.
3. Asociación controlada de `agent_id` a cada empresa.
4. Política de retención y borrado.
5. HTTPS, backups, monitorización y límites de tasa.
6. Pruebas de integración y validación de reintentos.

Este módulo no conecta Vodafone, no transfiere llamadas ni envía WhatsApp.
Es una base de recepción de eventos, pendiente de integrar y probar en el backend.

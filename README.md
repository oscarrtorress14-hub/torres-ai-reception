
# TORRES AI Reception — Demo MVP

Prototipo local con datos ficticios. No atiende llamadas reales, no envía mensajes de WhatsApp y no confirma reservas.

## Requisitos

- Python 3.12 recomendado.
- Dependencias definidas en `requirements.txt`.

## Ejecutar en macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Configura las credenciales administrativas antes de iniciar la aplicación:

```bash
export TORRES_ADMIN_USERNAME="admin"
export TORRES_ADMIN_PASSWORD="TU_CONTRASEÑA_SEGURA"
```

Utiliza una contraseña propia y robusta. No la guardes en Git ni la compartas.

Inicia el servidor:

```bash
uvicorn app.main:app --reload
```

Abre:

- API: http://127.0.0.1:8000/docs
- Estado del servicio: http://127.0.0.1:8000/health

Las rutas administrativas requieren autenticación HTTP Basic. `/health` permanece pública. El webhook de ElevenLabs utiliza su propia validación de firma.

## Datos de demostración

Empresa ficticia incluida: `peluqueria-demo`.

La API registra solicitudes en estado `pending`; nunca las presenta como reservas confirmadas.

No introduzcas datos personales reales en esta demostración.

## Límites y requisitos antes de producción

La demo utiliza SQLite local. No incluye telefonía, WhatsApp, pagos, grabaciones ni integraciones externas operativas.

La autenticación administrativa actual es una protección básica compartida, no un sistema completo de usuarios, roles o aislamiento de acceso por empresa.

Antes de producción serán necesarios, entre otros:

- PostgreSQL y persistencia gestionada.
- Autenticación individual, autorización y aislamiento multiempresa robusto.
- Gestión segura de secretos.
- HTTPS obligatorio.
- Rate limiting y protección contra abuso.
- Auditoría y copias de seguridad.
- Revisión de privacidad, consentimiento y cumplimiento del RGPD/LOPDGDD.
- Pruebas de seguridad y despliegue controlado.

Esta versión es exclusivamente un MVP de demostración y no debe utilizarse para gestionar clientes o reservas reales.

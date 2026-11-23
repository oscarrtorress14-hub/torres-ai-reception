# Torres AI Reception — Demo MVP

Prototipo local con datos ficticios. No atiende llamadas reales, no envía WhatsApp y no confirma reservas.

## Ejecutar en macOS
```bash
cd torres-ai-reception-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Abre http://127.0.0.1:8000/docs

Empresa ficticia incluida: `peluqueria-demo`.
La API registra solicitudes en estado `pending`; nunca las presenta como citas confirmadas.

## Límites
SQLite local para demo; sin telefonía, WhatsApp, pagos, grabaciones ni integraciones externas. No introducir datos personales reales. Antes de producción hacen falta autenticación, PostgreSQL, aislamiento multiempresa robusto, gestión de secretos, HTTPS, rate limiting, auditoría, backups y revisión RGPD/LOPDGDD.

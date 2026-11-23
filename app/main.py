from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DB = Path(__file__).resolve().parent.parent / "demo.db"
app = FastAPI(title="Torres AI Reception", version="0.1.0",
 description="Prototipo de demostración con datos ficticios; sin conexiones reales.")

TENANTS = {"peluqueria-demo": {
 "name": "Barbería Central (negocio ficticio)",
 "timezone": "Europe/Madrid",
 "opening_hours": {"lunes-viernes": "09:30-19:30", "sábado": "10:00-14:00", "domingo": "cerrado"},
 "services": [
  {"name": "Corte clásico", "duration_minutes": 30, "price_eur": 15},
  {"name": "Corte y barba", "duration_minutes": 45, "price_eur": 22},
  {"name": "Arreglo de barba", "duration_minutes": 20, "price_eur": 10}] ,
 "faq": [{"question": "¿Hace falta cita?", "answer": "Puedes solicitarla; esta demo no confirma disponibilidad."}]
}}

def db():
 c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

with db() as c:
 c.execute("""CREATE TABLE IF NOT EXISTS requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
 customer_name TEXT NOT NULL, service TEXT NOT NULL, requested_at TEXT NOT NULL,
 notes TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL)""")
 c.execute("""CREATE TABLE IF NOT EXISTS interactions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
 channel TEXT NOT NULL, summary TEXT NOT NULL, created_at TEXT NOT NULL)""")

def tenant(id):
 if id not in TENANTS: raise HTTPException(404, "Empresa no encontrada")
 return TENANTS[id]

class Booking(BaseModel):
 customer_name: str = Field(min_length=2, max_length=100)
 service: str = Field(min_length=2, max_length=100)
 requested_at: str
 notes: str = Field(default="", max_length=500)

class Interaction(BaseModel):
 channel: Literal["voice-demo", "whatsapp-demo", "web-demo"]
 summary: str = Field(min_length=3, max_length=1000)

@app.get("/health")
def health():
 return {"status": "ok", "product": "Torres AI Reception", "mode": "demo-only"}

@app.get("/api/tenants/{tenant_id}")
def get_tenant(tenant_id: str):
 return {"tenant_id": tenant_id, **tenant(tenant_id)}

@app.post("/api/tenants/{tenant_id}/booking-requests", status_code=201)
def create_booking(tenant_id: str, body: Booking):
 t = tenant(tenant_id)
 if body.service not in [s["name"] for s in t["services"]]:
  raise HTTPException(400, "Servicio no incluido en la demo")
 try: datetime.fromisoformat(body.requested_at.replace("Z", "+00:00"))
 except ValueError: raise HTTPException(400, "Fecha ISO 8601 no válida")
 with db() as c:
  cur = c.execute("INSERT INTO requests (tenant_id,customer_name,service,requested_at,notes,status,created_at) VALUES (?,?,?,?,?,'pending',?)",
   (tenant_id, body.customer_name, body.service, body.requested_at, body.notes, datetime.now(timezone.utc).isoformat()))
 return {"id": cur.lastrowid, "status": "pending", "message": "Solicitud de demo registrada; no es una reserva confirmada."}

@app.get("/api/tenants/{tenant_id}/booking-requests")
def list_bookings(tenant_id: str):
 tenant(tenant_id)
 with db() as c:
  rows = c.execute("SELECT id,customer_name,service,requested_at,notes,status,created_at FROM requests WHERE tenant_id=? ORDER BY id DESC",(tenant_id,)).fetchall()
 return [dict(r) for r in rows]

@app.post("/api/tenants/{tenant_id}/interactions", status_code=201)
def log_interaction(tenant_id: str, body: Interaction):
 tenant(tenant_id)
 with db() as c:
  cur = c.execute("INSERT INTO interactions (tenant_id,channel,summary,created_at) VALUES (?,?,?,?)",
   (tenant_id, body.channel, body.summary, datetime.now(timezone.utc).isoformat()))
 return {"id": cur.lastrowid, "logged": True}

@app.get("/api/tenants/{tenant_id}/owner-report")
def owner_report(tenant_id: str):
 t = tenant(tenant_id)
 with db() as c:
  pending = c.execute("SELECT COUNT(*) n FROM requests WHERE tenant_id=? AND status='pending'",(tenant_id,)).fetchone()["n"]
  rows = c.execute("SELECT channel,COUNT(*) n FROM interactions WHERE tenant_id=? GROUP BY channel",(tenant_id,)).fetchall()
 return {"tenant_id":tenant_id,"business_name":t["name"],"pending_booking_requests":pending,
  "interactions_by_channel":{r["channel"]:r["n"] for r in rows},"notice":"Informe simulado; no se envía por WhatsApp."}

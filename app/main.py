from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from .admin_auth import AdminAuthMiddleware
from pydantic import BaseModel, Field
from .elevenlabs_webhook import router as elevenlabs_webhook_router

DB = Path(__file__).resolve().parent.parent / "demo.db"
app = FastAPI(title="Torres AI Reception", version="0.1.0",
 description="Prototipo de demostración con datos ficticios; sin conexiones reales.")
app.include_router(elevenlabs_webhook_router)
app.add_middleware(AdminAuthMiddleware)

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


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Torres AI Reception | Panel</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0b1020;color:#edf1fa;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.layout{display:flex;min-height:100vh}
aside{width:235px;background:#10182b;border-right:1px solid #263149;padding:28px 18px}
.brand{font-size:19px;font-weight:750;margin-bottom:38px}
.brand span{color:#36d6bd}
nav a{display:block;padding:13px 14px;margin:7px 0;border-radius:10px;color:#aebbd0;text-decoration:none}
nav a.active,nav a:hover{background:#1c2942;color:white}
main{flex:1;padding:35px;max-width:1500px}
.top{display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap}
h1{font-size:27px;margin:0 0 8px}
.muted{color:#8e9bb2;font-size:14px}
.pill{background:#123d3b;color:#5de2c8;padding:8px 12px;border-radius:30px;font-size:12px}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:17px;margin:28px 0}
.card,.panel{background:#121c30;border:1px solid #26344d;border-radius:15px;padding:21px}
.card small{color:#9aa9c0}
.number{font-size:31px;font-weight:750;margin-top:12px}
.grid{display:grid;grid-template-columns:1.5fr 1fr;gap:18px}
.panel h2{font-size:17px;margin:0 0 20px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:13px 8px;border-bottom:1px solid #28344a}
th{color:#91a0b8;font-weight:550}
.status{color:#f4c76b;background:#453719;padding:5px 8px;border-radius:20px;font-size:11px}
input,select{width:100%;padding:12px;margin:7px 0 15px;background:#0b1426;color:white;border:1px solid #34435c;border-radius:8px}
label{font-size:13px;color:#aebbd0}
button{background:#24bfa9;color:#071b1a;border:0;border-radius:9px;padding:12px 17px;font-weight:700;cursor:pointer}
button:hover{background:#50ddc7}
#message{font-size:13px;margin-top:12px;color:#65dec5}
.empty{color:#91a0b8;padding:18px 0}
@media(max-width:850px){.layout{display:block}aside{width:100%;padding:16px}nav{display:flex;flex-wrap:wrap}.brand{margin-bottom:12px}main{padding:20px}.grid{grid-template-columns:1fr}}
@media(max-width:560px){.cards{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="layout">
<aside>
<div class="brand">TORRES <span>AI</span></div>
<nav>
<a class="active" href="/dashboard">▦　Resumen</a>
<a href="#solicitudes">▤　Solicitudes</a>
<a href="#nueva">＋　Nueva solicitud</a>
<a href="/docs">⚙　API de demostración</a>
</nav>
</aside>
<main>
<div class="top">
<div><h1>Panel de control</h1><div class="muted">Barbería Central · Entorno de demostración</div></div>
<div class="pill">● SISTEMA DE PRUEBA</div>
</div>
<div class="cards">
<div class="card"><small>Solicitudes pendientes</small><div class="number" id="pending">—</div></div>
<div class="card"><small>Total de solicitudes</small><div class="number" id="total">—</div></div>
<div class="card"><small>Interacciones registradas</small><div class="number" id="interactions">—</div></div>
</div>
<div class="grid">
<section class="panel" id="solicitudes">
<h2>Solicitudes recientes</h2>
<div style="overflow-x:auto">
<table>
<thead><tr><th>Cliente</th><th>Servicio</th><th>Fecha solicitada</th><th>Estado</th></tr></thead>
<tbody id="bookings"><tr><td colspan="4">Cargando...</td></tr></tbody>
</table>
</div>
<p class="muted">Las solicitudes de esta demo no son reservas confirmadas.</p>
</section>
<section class="panel" id="nueva">
<h2>Registrar solicitud de prueba</h2>
<form id="bookingForm">
<label>Nombre del cliente</label>
<input id="customer" required minlength="2" maxlength="100" placeholder="Ej. Cliente de prueba">
<label>Servicio</label>
<select id="service"></select>
<label>Fecha y hora solicitada</label>
<input id="date" type="datetime-local" required>
<label>Notas</label>
<input id="notes" maxlength="500" placeholder="Opcional">
<button type="submit">Registrar solicitud</button>
<div id="message"></div>
</form>
</section>
</div>
<p class="muted" style="margin-top:25px">Torres AI Reception · Prototipo local · Datos ficticios</p>
</main>
</div>
<script>
const tenant="peluqueria-demo";
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function load(){
 const [t,b,r]=await Promise.all([
  fetch("/api/tenants/"+tenant),
  fetch("/api/tenants/"+tenant+"/booking-requests"),
  fetch("/api/tenants/"+tenant+"/owner-report")
 ]);
 if(!t.ok||!b.ok||!r.ok) throw new Error("No se pudieron cargar los datos");
 const business=await t.json(), bookings=await b.json(), report=await r.json();
 document.getElementById("pending").textContent=report.pending_booking_requests;
 document.getElementById("total").textContent=bookings.length;
 document.getElementById("interactions").textContent=Object.values(report.interactions_by_channel).reduce((a,v)=>a+v,0);
 document.getElementById("bookings").innerHTML=bookings.length?bookings.map(x=>`<tr><td>${esc(x.customer_name)}</td><td>${esc(x.service)}</td><td>${esc(x.requested_at)}</td><td>
<select aria-label="Estado de solicitud" onchange="updateStatus(${x.id},this.value)">
<option value="pending" ${x.status==="pending"?"selected":""}>Pendiente</option>
<option value="contacted" ${x.status==="contacted"?"selected":""}>Contactado</option>
<option value="cancelled" ${x.status==="cancelled"?"selected":""}>Cancelado</option>
</select>
</td></tr>`).join(""):'<tr><td colspan="4" class="empty">Todavía no hay solicitudes</td></tr>';
 document.getElementById("service").innerHTML=business.services.map(s=>`<option value="${esc(s.name)}">${esc(s.name)} · ${esc(s.price_eur)} €</option>`).join("");
}
async function updateStatus(id,status){
 try{
  const response=await fetch("/api/tenants/"+tenant+"/booking-requests/"+id,{
   method:"PATCH",
   headers:{"Content-Type":"application/json"},
   body:JSON.stringify({status})
  });
  const result=await response.json();
  if(!response.ok)throw new Error(result.detail||"No se pudo actualizar");
  await load();
 }catch(err){
  alert(err.message);
  await load();
 }
}
document.getElementById("bookingForm").addEventListener("submit",async e=>{
 e.preventDefault();
 const message=document.getElementById("message");
 message.textContent="Registrando...";
 const date=new Date(document.getElementById("date").value);
 if(isNaN(date.getTime())){message.textContent="Introduce una fecha válida.";return}
 const body={
  customer_name:document.getElementById("customer").value,
  service:document.getElementById("service").value,
  requested_at:date.toISOString(),
  notes:document.getElementById("notes").value
 };
 try{
  const response=await fetch("/api/tenants/"+tenant+"/booking-requests",{
   method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)
  });
  const result=await response.json();
  if(!response.ok)throw new Error(result.detail||"Error al registrar");
  message.textContent="Solicitud registrada correctamente. Estado: pendiente.";
  e.target.reset();
  await load();
 }catch(err){message.textContent=err.message}
});
load().catch(err=>{document.getElementById("message").textContent=err.message});
</script>
</body>
</html>
""")


class StatusUpdate(BaseModel):
    status: Literal["pending", "contacted", "cancelled"]


@app.patch("/api/tenants/{tenant_id}/booking-requests/{request_id}")
def update_booking_status(tenant_id: str, request_id: int, body: StatusUpdate):
    tenant(tenant_id)
    with db() as c:
        row = c.execute(
            "SELECT id FROM requests WHERE id=? AND tenant_id=?",
            (request_id, tenant_id)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Solicitud no encontrada")
        c.execute(
            "UPDATE requests SET status=? WHERE id=? AND tenant_id=?",
            (body.status, request_id, tenant_id)
        )
    return {"id": request_id, "status": body.status, "updated": True}

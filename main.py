from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime
import io
import os

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise")

class LoginPayload(BaseModel):
    username: str = Field(..., alias="username")
    password: str = Field(..., alias="password")

class TenantRegister(BaseModel):
    tenant_id: str
    username: str
    password: str

class PanelRegister(BaseModel):
    panel_id: str
    name: str
    location: str
    voltage: str
    gateway_qr: str

class InventoryUpdate(BaseModel):
    part_name: str
    category: str
    quantity_change: int
    unit_cost: float
    min_threshold: int

class WebhookConfig(BaseModel):
    webhook_url: str

class PlanUpgrade(BaseModel):
    plan_name: str

class PinValidation(BaseModel):
    panel_id: str
    pin: str

class ForceFailure(BaseModel):
    panel_id: str

class AlertDispatch(BaseModel):
    panel_id: str

db_tenants = {
    "HITECH-DEFAULT": {
        "plan_name": "Enterprise",
        "status": "Ativo",
        "expires_at": "2027-12-31",
        "max_panels": 50,
        "webhook_url": "https://api.whatsapp.com/send?phone=5516999999999"
    }
}

db_users = {
    "RafaelFelipe": {"password": "123456", "role": "CEO", "tenant_id": "HITECH-DEFAULT"},
    "GerenteJoao": {"password": "123", "role": "Gerente", "tenant_id": "HITECH-DEFAULT"},
    "TecnicoCarlos": {"password": "123", "role": "Técnico de Campo", "tenant_id": "HITECH-DEFAULT"},
    "InstaladorAna": {"password": "123", "role": "Instalador", "tenant_id": "HITECH-DEFAULT"}
}

db_panels = [
    {
        "id": "PANEL-01",
        "name": "Subestação Principal A",
        "location": "Setor Industrial Sul",
        "voltage": "380V",
        "current": 142.5,
        "temperature": 68.2,
        "status": "ESTAVEL",
        "component": "Disjuntor Geral 400A",
        "predictive_failure_hours": 320,
        "recommendation": "Operação dentro da normalidade térmica.",
        "esg_waste_kwh": 12.4,
        "assigned_to": None
    },
    {
        "id": "PANEL-02",
        "name": "Banco de Baterias B",
        "location": "Sala de Automação",
        "voltage": "24V DC",
        "current": 18.2,
        "temperature": 79.5,
        "status": "CRITICO",
        "component": "Módulo Retificador 50A",
        "predictive_failure_hours": 14,
        "recommendation": "Sobreaquecimento iminente detectado nos tiristores. Substituição urgente recomendada.",
        "esg_waste_kwh": 45.1,
        "assigned_to": None
    }
]

db_audit_logs = [
    {"timestamp": str(datetime.now()), "user_name": "RafaelFelipe", "role": "CEO", "action": "LOGIN", "details": "Acesso bem-sucedido à plataforma SCADA."}
]

db_inventory = [
    {"part_name": "Contator Geral 400A", "category": "Comutação", "quantity_in_stock": 2, "min_threshold": 3, "unit_cost": 450.0},
    {"part_name": "Módulo Retificador 50A", "category": "Alimentação", "quantity_in_stock": 5, "min_threshold": 2, "unit_cost": 1200.0}
]

@app.get("/", response_class=HTMLResponse)
def read_root():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Erro: index.html não encontrado no diretório.</h1>"

@app.post("/api/token")
async def login_access_token(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    
    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        form_data = await request.form()
        username = form_data.get("username")
        password = form_data.get("password")

    user = db_users.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilizador ou senha incorretos.")
    
    db_audit_logs.insert(0, {
        "timestamp": str(datetime.now()),
        "user_name": username,
        "role": user["role"],
        "action": "LOGIN",
        "details": f"Login efetuado com sucesso na organização {user['tenant_id']}."
    })

    return {
        "access_token": f"jwt-token-{username}-secure",
        "token_type": "bearer",
        "role": user["role"],
        "tenant_id": user["tenant_id"]
    }

@app.post("/api/tenant/register")
def register_tenant(data: TenantRegister):
    if data.tenant_id in db_tenants:
        raise HTTPException(status_code=400, detail="Organização já registada.")
    db_tenants[data.tenant_id] = {
        "plan_name": "Standard",
        "status": "Ativo",
        "expires_at": "2027-12-31",
        "max_panels": 10,
        "webhook_url": ""
    }
    db_users[data.username] = {"password": data.password, "role": "CEO", "tenant_id": data.tenant_id}
    return {"message": f"Organização {data.tenant_id} registada com sucesso! Faça login."}

@app.get("/api/panels")
def get_panels():
    return {
        "tenant_id": "HITECH-DEFAULT",
        "panels": db_panels,
        "audit_logs": db_audit_logs,
        "inventory": db_inventory,
        "billing": db_tenants["HITECH-DEFAULT"]
    }

@app.post("/api/panels/register")
def register_panel(data: PanelRegister):
    db_panels.append({
        "id": data.panel_id,
        "name": data.name,
        "location": data.location,
        "voltage": data.voltage,
        "current": 10.0,
        "temperature": 35.0,
        "status": "ESTAVEL",
        "component": "Controlador IoT Gateway",
        "predictive_failure_hours": 720,
        "recommendation": "Novo painel comissionado e operacional.",
        "esg_waste_kwh": 2.0,
        "assigned_to": None
    })
    return {"message": "Painel comissionado com sucesso."}

@app.post("/api/inventory/update")
def update_inventory(data: InventoryUpdate):
    for item in db_inventory:
        if item["part_name"].lower() == data.part_name.lower():
            item["quantity_in_stock"] += data.quantity_change
            item["unit_cost"] = data.unit_cost
            item["min_threshold"] = data.min_threshold
            return {"message": "Inventário atualizado com sucesso."}
    
    db_inventory.append({
        "part_name": data.part_name,
        "category": data.category,
        "quantity_in_stock": data.quantity_change,
        "min_threshold": data.min_threshold,
        "unit_cost": data.unit_cost
    })
    return {"message": "Nova peça registada no almoxarifado."}

@app.post("/api/demo/force-failure")
def force_failure(data: ForceFailure):
    for p in db_panels:
        if p["id"] == data.panel_id:
            p["status"] = "CRITICO"
            p["temperature"] = 92.4
            p["predictive_failure_hours"] = 2
            p["recommendation"] = "ALERTA DEMO: Falha crítica forçada para demonstração comercial!"
            return {"message": f"Falha crítica simulada com sucesso no cubículo {p['id']}!"}
    raise HTTPException(status_code=404, detail="Painel não encontrado.")

@app.post("/api/tenant/upgrade-plan")
def upgrade_plan(data: PlanUpgrade):
    db_tenants["HITECH-DEFAULT"]["plan_name"] = data.plan_name
    return {"message": f"Plano atualizado com sucesso para {data.plan_name}!"}

@app.post("/api/tenant/webhook")
def save_webhook(data: WebhookConfig):
    db_tenants["HITECH-DEFAULT"]["webhook_url"] = data.webhook_url
    return {"message": "URL de Webhook guardada com sucesso!"}

@app.get("/api/export/executive-report")
def export_executive_report():
    report_content = "=== RELATÓRIO EXECUTIVO HITECH VOLTGUARD ===\nFrota Operacional: 100% Monitorada\nConformidade NR-10: Ativa\nStatus Geral: Estável com 1 alerta crítico isolado."
    return StreamingResponse(io.BytesIO(report_content.encode("utf-8")), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=relatorio_executivo_hitech.txt"})

@app.get("/api/export/audit-csv")
def export_audit_csv():
    csv_data = "Timestamp,User,Role,Action,Details\n" + "\n".join([f"{l['timestamp']},{l['user_name']},{l['role']},{l['action']},{l['details']}" for l in db_audit_logs])
    return StreamingResponse(io.BytesIO(csv_data.encode("utf-8")), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_report.csv"})

@app.post("/api/alerts/dispatch")
def dispatch_alert(data: AlertDispatch):
    return {"message": f"Alerta crítico despachado via Webhook para o painel {data.panel_id}."}

@app.post("/api/validate-nr10-pin")
def validate_pin(data: PinValidation):
    if data.pin == "1010":
        for p in db_panels:
            if p["id"] == data.panel_id:
                p["assigned_to"] = "RafaelFelipe"
        return {"message": "Assinatura NR-10 validada com sucesso."}
    raise HTTPException(status_code=400, detail="PIN inválido.")

# Servir recursos estáticos (logo.jpg, etc.)
app.mount("/static", StaticFiles(directory="."), name="static_files")

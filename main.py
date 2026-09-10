import asyncio
import json
import random
import os
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# Carrega variáveis de ambiente localmente se o arquivo .env existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise")

# Montagem estática para carregar imagens e assets corporativos
app.mount("/static", StaticFiles(directory=os.path.dirname(__file__)), name="static")

security = HTTPBearer()

panels_db = [
    {
        "id": "PANEL-01",
        "name": "Cubículo Geral de Média Tensão (MT)",
        "location": "Subestação Principal - Setor A",
        "voltage": "13.8 kV",
        "current": 454.15,
        "temperature": 70.61,
        "gateway_qr": "QR-GW-8810",
        "status": "NORMAL",
        "component": "Disjuntor Principal SF6",
        "predictive_failure_hours": 320,
        "recommendation": "Nenhuma ação necessária.",
        "esg_waste_kwh": 4.2,
        "assigned_to": None
    },
    {
        "id": "PANEL-02",
        "name": "QGBT - Alimentação de Baixa Tensão",
        "location": "Área de Utilidades / Comércio",
        "voltage": "380V AC",
        "current": 210.5,
        "temperature": 80.89,
        "gateway_qr": "QR-GW-9920",
        "status": "CRITICO",
        "component": "Borne do Contator K2",
        "predictive_failure_hours": 18,
        "recommendation": "ALERTA IMEDIATO: Risco de arco elétrico no Borne do Contator K2.",
        "esg_waste_kwh": 45.8,
        "assigned_to": None
    },
    {
        "id": "PANEL-03",
        "name": "Painel de Bombeamento / Inversor",
        "location": "Casa de Bombas / Saneamento",
        "voltage": "690V AC",
        "current": 530.0,
        "temperature": 65.0,
        "gateway_qr": "QR-GW-1104",
        "status": "NORMAL",
        "component": "Inversor de Frequência principal",
        "predictive_failure_hours": 500,
        "recommendation": "Sistema operando normalmente.",
        "esg_waste_kwh": 1.1,
        "assigned_to": None
    }
]

audit_logs = [
    {
        "timestamp": str(datetime.now()),
        "user_name": "Sistema",
        "role": "CEO",
        "action": "LOGIN_SISTEMA",
        "details": "Serviço inicializado com segurança de variáveis de ambiente."
    }
]

class TokenRequest(BaseModel):
    username: str
    password: str

class PinValidationRequest(BaseModel):
    panel_id: str
    pin: str

class NewPanelRequest(BaseModel):
    panel_id: str
    name: str
    location: str
    voltage: str
    gateway_qr: str

@app.post("/api/token")
def gerar_token(body: TokenRequest):
    # Credenciais obtidas de forma segura via variáveis de ambiente (.env ou painel Render)
    users = {
        os.getenv("CEO_USER", "RafaelFelipe"): {"role": "CEO", "pass": os.getenv("CEO_PASS", "HitechCEO")},
        os.getenv("GERENTE_USER", "GuilhermeCosta"): {"role": "Gerente", "pass": os.getenv("GERENTE_PASS", "HitechCEO")},
        os.getenv("INSTALADOR_USER", "InstaladorCampo"): {"role": "Instalador", "pass": os.getenv("INSTALADOR_PASS", "HitechCEO")},
        os.getenv("TECNICO_USER", "admin"): {"role": "Técnico de Campo", "pass": os.getenv("TECNICO_PASS", "HitechCEO")}
    }
    
    user = users.get(body.username)
    if not user or user["pass"] != body.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    return {"access_token": f"fake-jwt-token-{body.username}", "role": user["role"]}

@app.get("/api/panels")
def obter_paineis(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return {"panels": panels_db, "audit_logs": audit_logs}

@app.post("/api/validate-nr10-pin")
def validar_pin(body: PinValidationRequest):
    if body.pin != "1010":
        raise HTTPException(status_code=400, detail="PIN incorreto")
    
    for p in panels_db:
        if p["id"] == body.panel_id:
            p["assigned_to"] = "Técnico Responsável"
            audit_logs.insert(0, {
                "timestamp": str(datetime.now()),
                "user_name": "Técnico de Campo",
                "role": "Instalador/Técnico",
                "action": "ASSINATURA_NR10",
                "details": f"Intervenção autorizada sob normas NR-10 no painel {body.panel_id}"
            })
            return {"status": "success"}
            
    raise HTTPException(status_code=404, detail="Painel não encontrado")

@app.post("/api/panels/register")
def registrar_painel(body: NewPanelRequest):
    novo = {
        "id": body.panel_id,
        "name": body.name,
        "location": body.location,
        "voltage": body.voltage,
        "current": round(random.uniform(100.0, 300.0), 2),
        "temperature": round(random.uniform(40.0, 60.0), 2),
        "gateway_qr": body.gateway_qr,
        "status": "NORMAL",
        "component": "Módulo de Entrada Genérico",
        "predictive_failure_hours": 600,
        "recommendation": "Comissionado recentemente. Operação estável.",
        "esg_waste_kwh": 2.0,
        "assigned_to": None
    }
    panels_db.append(novo)
    audit_logs.insert(0, {
        "timestamp": str(datetime.now()),
        "user_name": "Instalador de Campo",
        "role": "Instalador",
        "action": "COMISSIONAMENTO_NOVO",
        "details": f"Painel {body.panel_id} integrado via QR Code {body.gateway_qr}"
    })
    return {"status": "success", "panel": novo}

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            for p in panels_db:
                if p["status"] != "CRITICO":
                    p["temperature"] = round(p["temperature"] + random.uniform(-0.3, 0.3), 2)
                    p["current"] = round(p["current"] + random.uniform(-1.5, 1.5), 2)
            
            await websocket.send_text(json.dumps({"panels": panels_db, "audit_logs": audit_logs}))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass

@app.get("/")
def home():
    caminho_html = os.path.join(os.path.dirname(__file__), "index.html")
    if not os.path.exists(caminho_html):
        return HTMLResponse(content="<h1>Erro: O arquivo index.html não foi encontrado!</h1>", status_code=404)
    with open(caminho_html, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
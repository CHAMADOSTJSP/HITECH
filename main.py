import asyncio
import json
import random
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt

# Importa o banco de dados
from database import SessionLocal, init_db, PanelModel, AuditLogModel

# Carrega variáveis de ambiente localmente se o arquivo .env existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise")

# Montagem estática para carregar assets
app.mount("/static", StaticFiles(directory=os.path.dirname(__file__)), name="static")

security = HTTPBearer()

# Configurações de segurança JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "hitech_super_secret_key_voltguard_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas de sessão

def criar_token_acesso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verificar_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado. Faça login novamente.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais de autenticação inválidas.")

# Gerenciador de conexões WebSocket ativas
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

manager = ConnectionManager()

# Dependência do FastAPI para obter a sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def seed_initial_data():
    db = SessionLocal()
    try:
        if db.query(PanelModel).first() is None:
            initial_panels = [
                PanelModel(
                    id="PANEL-01",
                    name="Cubículo Geral de Média Tensão (MT)",
                    location="Subestação Principal - Setor A",
                    voltage="13.8 kV",
                    current=454.15,
                    temperature=70.61,
                    gateway_qr="QR-GW-8810",
                    status="NORMAL",
                    component="Disjuntor Principal SF6",
                    predictive_failure_hours=320,
                    recommendation="Nenhuma ação necessária.",
                    esg_waste_kwh=4.2,
                    assigned_to=None
                ),
                PanelModel(
                    id="PANEL-02",
                    name="QGBT - Alimentação de Baixa Tensão",
                    location="Área de Utilidades / Comércio",
                    voltage="380V AC",
                    current=210.5,
                    temperature=80.89,
                    gateway_qr="QR-GW-9920",
                    status="CRITICO",
                    component="Borne do Contator K2",
                    predictive_failure_hours=18,
                    recommendation="ALERTA IMEDIATO: Risco de arco elétrico no Borne do Contator K2.",
                    esg_waste_kwh=45.8,
                    assigned_to=None
                ),
                PanelModel(
                    id="PANEL-03",
                    name="Painel de Bombeamento / Inversor",
                    location="Casa de Bombas / Saneamento",
                    voltage="690V AC",
                    current=530.0,
                    temperature=65.0,
                    gateway_qr="QR-GW-1104",
                    status="NORMAL",
                    component="Inversor de Frequência principal",
                    predictive_failure_hours=500,
                    recommendation="Sistema operando normalmente.",
                    esg_waste_kwh=1.1,
                    assigned_to=None
                )
            ]
            db.add_all(initial_panels)

            initial_log = AuditLogModel(
                timestamp=str(datetime.now()),
                user_name="Sistema",
                role="CEO",
                action="LOGIN_SISTEMA",
                details="Serviço inicializado com persistência SQLite, JWT e WebSockets otimizados."
            )
            db.add(initial_log)
            db.commit()
    finally:
        db.close()

init_db()
seed_initial_data()

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
    users = {
        os.getenv("CEO_USER", "RafaelFelipe"): {"role": "CEO", "pass": os.getenv("CEO_PASS", "HitechCEO")},
        os.getenv("GERENTE_USER", "GuilhermeCosta"): {"role": "Gerente", "pass": os.getenv("GERENTE_PASS", "HitechCEO")},
        os.getenv("INSTALADOR_USER", "InstaladorCampo"): {"role": "Instalador", "pass": os.getenv("INSTALADOR_PASS", "HitechCEO")},
        os.getenv("TECNICO_USER", "admin"): {"role": "Técnico de Campo", "pass": os.getenv("TECNICO_PASS", "HitechCEO")}
    }
    
    user = users.get(body.username)
    if not user or user["pass"] != body.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    
    access_token = criar_token_acesso({"sub": body.username, "role": user["role"]})
    return {"access_token": access_token, "role": user["role"], "token_type": "bearer"}

@app.get("/api/panels")
def obter_paineis(payload: dict = Depends(verificar_token), db: Session = Depends(get_db)):
    panels = db.query(PanelModel).all()
    logs = db.query(AuditLogModel).order_by(AuditLogModel.id.desc()).all()
    
    panels_list = [p.__dict__ for p in panels]
    for p in panels_list:
        p.pop('_sa_instance_state', None)

    logs_list = [{"timestamp": l.timestamp, "user_name": l.user_name, "role": l.role, "action": l.action, "details": l.details} for l in logs]

    return {"panels": panels_list, "audit_logs": logs_list, "usuario_autenticado": payload.get("sub")}

@app.post("/api/validate-nr10-pin")
def validar_pin(body: PinValidationRequest, payload: dict = Depends(verificar_token), db: Session = Depends(get_db)):
    if body.pin != "1010":
        raise HTTPException(status_code=400, detail="PIN incorreto")
    
    panel = db.query(PanelModel).filter(PanelModel.id == body.panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado")
    
    panel.assigned_to = payload.get("sub", "Técnico Responsável")
    
    novo_log = AuditLogModel(
        timestamp=str(datetime.now()),
        user_name=payload.get("sub", "Técnico"),
        role=payload.get("role", "Técnico"),
        action="ASSINATURA_NR10",
        details=f"Intervenção autorizada sob normas NR-10 no painel {body.panel_id}"
    )
    db.add(novo_log)
    db.commit()
    
    return {"status": "success"}

@app.post("/api/panels/register")
def registrar_painel(body: NewPanelRequest, payload: dict = Depends(verificar_token), db: Session = Depends(get_db)):
    existing = db.query(PanelModel).filter(PanelModel.id == body.panel_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="ID de painel já cadastrado.")

    novo = PanelModel(
        id=body.panel_id,
        name=body.name,
        location=body.location,
        voltage=body.voltage,
        current=round(random.uniform(100.0, 300.0), 2),
        temperature=round(random.uniform(40.0, 60.0), 2),
        gateway_qr=body.gateway_qr,
        status="NORMAL",
        component="Módulo de Entrada Genérico",
        predictive_failure_hours=600,
        recommendation="Comissionado recentemente. Operação estável.",
        esg_waste_kwh=2.0,
        assigned_to=None
    )
    db.add(novo)

    novo_log = AuditLogModel(
        timestamp=str(datetime.now()),
        user_name=payload.get("sub", "Instalador"),
        role=payload.get("role", "Instalador"),
        action="COMISSIONAMENTO_NOVO",
        details=f"Painel {body.panel_id} integrado via QR Code {body.gateway_qr}"
    )
    db.add(novo_log)
    db.commit()
    db.refresh(novo)

    panel_dict = {k: v for k, v in novo.__dict__ if k != '_sa_instance_state'}
    return {"status": "success", "panel": panel_dict}

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    db = SessionLocal()
    try:
        while True:
            panels = db.query(PanelModel).all()
            for p in panels:
                if p.status != "CRITICO":
                    p.temperature = round(p.temperature + random.uniform(-0.3, 0.3), 2)
                    p.current = round(p.current + random.uniform(-1.5, 1.5), 2)
            db.commit()

            panels_list = [{k: v for k, v in p.__dict__ if k != '_sa_instance_state'} for p in panels]
            logs = db.query(AuditLogModel).order_by(AuditLogModel.id.desc()).limit(20).all()
            logs_list = [{"timestamp": l.timestamp, "user_name": l.user_name, "role": l.role, "action": l.action, "details": l.details} for l in logs]

            data_payload = json.dumps({"panels": panels_list, "audit_logs": logs_list})
            await websocket.send_text(data_payload)
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    finally:
        db.close()

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
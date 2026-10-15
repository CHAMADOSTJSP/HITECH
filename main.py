import os
import io
import random
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import jwt
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Configuração de Segurança e JWT
SECRET_KEY = os.getenv("SECRET_KEY", "hitech_voltguard_super_secret_enterprise_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

# Configuração do Banco de Dados SQLite com SQLAlchemy
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voltguard.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos do Banco de Dados
class PanelModel(Base):
    __tablename__ = "panels"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    voltage = Column(String, nullable=False)
    current = Column(Float, default=0.0)
    temperature = Column(Float, default=0.0)
    gateway_qr = Column(String, nullable=True)
    status = Column(String, default="NORMAL")
    component = Column(String, default="Disjuntor Principal")
    predictive_failure_hours = Column(Integer, default=120)
    recommendation = Column(String, default="Operação nominal estável.")
    esg_waste_kwh = Column(Float, default=1.2)
    assigned_to = Column(String, nullable=True)

class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise")

# Rota direta para servir a logo localizada na raiz do repositório
@app.get("/logo.jpg")
def get_logo():
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="Logo não encontrada.")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Populando dados iniciais caso o banco esteja vazio
def init_db():
    db = SessionLocal()
    if db.query(PanelModel).count() == 0:
        initial_panels = [
            PanelModel(id="PANEL-01", name="Cubículo Geral de Média Tensão (MT)", location="Subestação Principal - Setor A", voltage="13.8 kV", current=454.23, temperature=70.58, gateway_qr="QR-GW-0010", status="NORMAL", component="Barramento de Cobre", predictive_failure_hours=145, recommendation="Inspeção termográfica de rotina em 60 dias.", esg_waste_kwh=0.8),
            PanelModel(id="PANEL-02", name="QGBT - Alimentação de Baixa Tensão", location="Área de Utilidades / Comércio", voltage="380V AC", current=215.5, temperature=91.19, gateway_qr="QR-GW-0070", status="CRITICO", component="Contator Geral 400A", predictive_failure_hours=18, recommendation="Substituição imediata do contator devido a desgaste nos contatos.", esg_waste_kwh=4.5),
            PanelModel(id="PANEL-03", name="Painel de Bombeamento / Incessor", location="Casa de Bombas / Saneamento", voltage="380V AC", current=530.94, temperature=65.12, gateway_qr="QR-GW-1104", status="NORMAL", component="Inversores de Frequência", predictive_failure_hours=210, recommendation="Filtros de harmônicas limpos e operacionais.", esg_waste_kwh=1.1)
        ]
        db.add_all(initial_panels)
        
        initial_logs = [
            AuditLogModel(user_name="RafaelFelipe", role="CEO", action="INICIALIZACAO_SISTEMA", details="Sistema SCADA Enterprise iniciado com sucesso na nuvem.")
        ]
        db.add_all(initial_logs)
        db.commit()
    db.close()

init_db()

# Usuários Corporativos Padrão
USERS_DB = {
    "RafaelFelipe": {"password": "123456", "role": "CEO"},
    "GerenteCarlos": {"password": "123456", "role": "Gerente"},
    "TecnicoMarcos": {"password": "123456", "role": "Técnico de Campo"},
    "InstaladorAna": {"password": "123456", "role": "Instalador"}
}

class User(BaseModel):
    username: str
    role: str

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "Técnico de Campo")
        if username is None:
            raise HTTPException(status_code=401, detail="Credenciais inválidas.")
        return User(username=username, role=role)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token expirado ou inválido.")

@app.post("/api/token")
def login(credentials: dict):
    username = credentials.get("username")
    password = credentials.get("password")
    
    user = USERS_DB.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos.")
    
    payload = {
        "sub": username,
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}

@app.get("/api/panels")
def get_panels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    panels = db.query(PanelModel).all()
    logs = db.query(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(50).all()
    
    panels_data = [
        {
            "id": p.id,
            "name": p.name,
            "location": p.location,
            "voltage": p.voltage,
            "current": p.current,
            "temperature": p.temperature,
            "gateway_qr": p.gateway_qr,
            "status": p.status,
            "component": p.component,
            "predictive_failure_hours": p.predictive_failure_hours,
            "recommendation": p.recommendation,
            "esg_waste_kwh": p.esg_waste_kwh,
            "assigned_to": p.assigned_to
        } for p in panels
    ]
    
    logs_data = [
        {
            "timestamp": str(l.timestamp),
            "user_name": l.user_name,
            "role": l.role,
            "action": l.action,
            "details": l.details
        } for l in logs
    ]
    
    return {"panels": panels_data, "audit_logs": logs_data}

@app.get("/api/export/audit-csv")
def export_audit_csv(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Acesso restrito ao perfil de CEO para exportação de auditoria.")
    
    logs = db.query(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).all()
    
    output = io.StringIO()
    output.write("ID,Data/Hora,Usuario,Cargo,Acao,Detalhes\n")
    for l in logs:
        output.write(f"{l.id},{l.timestamp},{l.user_name},{l.role},{l.action},\"{l.details}\"\n")
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hitech_voltguard_audit_report.csv"}
    )

@app.post("/api/validate-nr10-pin")
def validate_nr10_pin(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    panel_id = data.get("panel_id")
    pin = data.get("pin")
    
    if pin != "1010":
        raise HTTPException(status_code=400, detail="PIN NR-10 incorreto.")
    
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    
    panel.assigned_to = current_user.username
    
    novo_log = AuditLogModel(
        user_name=current_user.username,
        role=current_user.role,
        action="ASSINATURA_NR10",
        details=f"Intervenção autorizada e assumida no cubículo {panel_id}"
    )
    db.add(novo_log)
    db.commit()
    
    return {"status": "success", "message": "Assinatura NR-10 validada com sucesso."}

@app.post("/api/panels/register")
def register_panel(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Instalador"]:
        raise HTTPException(status_code=403, detail="Acesso não autorizado para comissionamento.")
    
    panel_id = data.get("panel_id")
    if db.query(PanelModel).filter(PanelModel.id == panel_id).first():
        raise HTTPException(status_code=400, detail="ID de painel já registado.")
    
    novo_painel = PanelModel(
        id=panel_id,
        name=data.get("name"),
        location=data.get("location"),
        voltage=data.get("voltage"),
        gateway_qr=data.get("gateway_qr"),
        status="NORMAL",
        current=round(random.uniform(100, 300), 2),
        temperature=round(random.uniform(45, 60), 2)
    )
    db.add(novo_painel)
    
    novo_log = AuditLogModel(
        user_name=current_user.username,
        role=current_user.role,
        action="COMISSIONAMENTO_NOVO_PAINEL",
        details=f"Painel {panel_id} registado e integrado via IoT Gateway."
    )
    db.add(novo_log)
    db.commit()
    
    return {"status": "success", "message": "Painel comissionado com sucesso."}

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            db = SessionLocal()
            panels = db.query(PanelModel).all()
            logs = db.query(AuditLogModel).order_by(AuditLogModel.timestamp.desc()).limit(20).all()
            
            panels_data = []
            for p in panels:
                p.current = round(max(10.0, p.current + random.uniform(-1.5, 1.5)), 2)
                p.temperature = round(max(20.0, p.temperature + random.uniform(-0.4, 0.4)), 2)
                panels_data.append({
                    "id": p.id,
                    "name": p.name,
                    "location": p.location,
                    "voltage": p.voltage,
                    "current": p.current,
                    "temperature": p.temperature,
                    "gateway_qr": p.gateway_qr,
                    "status": p.status,
                    "component": p.component,
                    "predictive_failure_hours": p.predictive_failure_hours,
                    "recommendation": p.recommendation,
                    "esg_waste_kwh": p.esg_waste_kwh,
                    "assigned_to": p.assigned_to
                })
            db.commit()
            
            logs_data = [{
                "timestamp": str(l.timestamp),
                "user_name": l.user_name,
                "role": l.role,
                "action": l.action,
                "details": l.details
            } for l in logs]
            db.close()
            
            await websocket.send_json({"panels": panels_data, "audit_logs": logs_data})
            import asyncio
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass

@app.get("/")
def serve_index():
    return FileResponse("index.html")

import os
import io
import random
import hashlib
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import jwt
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Configuração de Segurança baseada em SHA-256 nativo
SECRET_KEY = os.getenv("SECRET_KEY", "hitech_voltguard_super_secret_enterprise_key_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voltguard.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class PanelModel(Base):
    __tablename__ = "panels"
    id = Column(String, primary_key=True, index=True)
    tenant_id = Column(String, default="HITECH-DEFAULT", index=True)
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
    tenant_id = Column(String, default="HITECH-DEFAULT", index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(String, nullable=False)

class TenantSubscriptionModel(Base):
    __tablename__ = "subscriptions"
    tenant_id = Column(String, primary_key=True, index=True)
    plan_name = Column(String, default="Enterprise")
    status = Column(String, default="ACTIVE")
    expires_at = Column(DateTime, default=datetime.utcnow() + timedelta(days=365))
    max_panels = Column(Integer, default=25)
    webhook_url = Column(String, nullable=True, default="https://httpbin.org/post")

class UserModel(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    role = Column(String, default="CEO")
    tenant_id = Column(String, default="HITECH-DEFAULT")
    plan = Column(String, default="Enterprise")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise - Phase 4 (IoT Telemetry)")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        if not stored_password:
            return False
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == stored_password
    except Exception:
        return plain_password == stored_password

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

def init_db():
    db = SessionLocal()
    try:
        Base.metadata.create_all(bind=engine)
        
        default_users = [
            UserModel(username="RafaelFelipe", password=hash_password("123456"), role="CEO", tenant_id="HITECH-DEFAULT", plan="Enterprise"),
            UserModel(username="GerenteCarlos", password=hash_password("123456"), role="Gerente", tenant_id="HITECH-DEFAULT", plan="Enterprise"),
            UserModel(username="TecnicoMarcos", password=hash_password("123456"), role="Técnico de Campo", tenant_id="HITECH-DEFAULT", plan="Enterprise"),
            UserModel(username="InstaladorAna", password=hash_password("123456"), role="Instalador", tenant_id="HITECH-DEFAULT", plan="Enterprise")
        ]
        for u in default_users:
            db.merge(u)

        if db.query(PanelModel).count() == 0:
            initial_panels = [
                PanelModel(id="PANEL-01", tenant_id="HITECH-DEFAULT", name="Cubículo Geral de Média Tensão (MT)", location="Subestação Principal - Ribeirão Preto", voltage="13.8 kV", current=454.23, temperature=70.58, gateway_qr="QR-GW-0010", status="NORMAL", component="Barramento de Cobre", predictive_failure_hours=145, recommendation="Inspeção termográfica de rotina em 60 dias.", esg_waste_kwh=0.8),
                PanelModel(id="PANEL-02", tenant_id="HITECH-DEFAULT", name="QGBT - Alimentação de Baixa Tensão", location="Fábrica 01 - Setor de Utilidades", voltage="380V AC", current=215.5, temperature=91.19, gateway_qr="QR-GW-0070", status="CRITICO", component="Contator Geral 400A", predictive_failure_hours=18, recommendation="Substituição imediata do contator devido a desgaste.", esg_waste_kwh=4.5),
                PanelModel(id="PANEL-03", tenant_id="HITECH-DEFAULT", name="Painel de Bombeamento / Incessor", location="Fábrica 02 - Saneamento", voltage="380V AC", current=530.94, temperature=65.12, gateway_qr="QR-GW-1104", status="NORMAL", component="Inversores de Frequência", predictive_failure_hours=210, recommendation="Filtros operacionais.", esg_waste_kwh=1.1)
            ]
            db.add_all(initial_panels)
            db.add(TenantSubscriptionModel(tenant_id="HITECH-DEFAULT", plan_name="Enterprise", status="ACTIVE", max_panels=25, webhook_url="https://httpbin.org/post"))
            db.add(AuditLogModel(tenant_id="HITECH-DEFAULT", user_name="RafaelFelipe", role="CEO", action="INICIALIZACAO", details="Sistema Fase 4 inicializado com ingestão IoT."))
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro crítico na inicialização da BD: {e}")
    finally:
        db.close()

init_db()

class User(BaseModel):
    username: str
    role: str
    tenant_id: str
    plan: str

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        tenant_id = payload.get("tenant_id")
        plan = payload.get("plan")
        if not username:
            raise HTTPException(status_code=401, detail="Token inválido.")
        return User(username=username, role=role, tenant_id=tenant_id, plan=plan)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

@app.post("/api/token")
def login(credentials: dict, db: Session = Depends(get_db)):
    if not credentials:
        raise HTTPException(status_code=400, detail="Credenciais em falta.")
    username = credentials.get("username")
    password = credentials.get("password")
    
    db_user = db.query(UserModel).filter(UserModel.username == username).first()
    if not db_user or not verify_password(password, db_user.password):
        raise HTTPException(status_code=400, detail="Utilizador ou senha incorretos.")
    
    token = jwt.encode({"sub": db_user.username, "role": db_user.role, "tenant_id": db_user.tenant_id, "plan": db_user.plan, "exp": datetime.utcnow() + timedelta(days=1)}, SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "role": db_user.role, "plan": db_user.plan}

@app.post("/api/tenant/register")
def register_tenant(data: dict, db: Session = Depends(get_db)):
    if not data:
        raise HTTPException(status_code=400, detail="Dados em falta.")
    tenant_id = data.get("tenant_id", "").upper().strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not tenant_id or not username or not password:
        raise HTTPException(status_code=400, detail="Preencha todos os campos do registo.")
    
    if db.query(UserModel).filter(UserModel.username == username).first():
        raise HTTPException(status_code=400, detail="Este nome de utilizador já está em uso.")
    
    if db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == tenant_id).first():
        raise HTTPException(status_code=400, detail="Esta organização já está registada.")
    
    db.add(TenantSubscriptionModel(tenant_id=tenant_id, plan_name="Enterprise", status="ACTIVE", max_panels=25, webhook_url="https://httpbin.org/post"))
    db.add(UserModel(username=username, password=hash_password(password), role="CEO", tenant_id=tenant_id, plan="Enterprise"))
    db.add(PanelModel(id=f"{tenant_id}-01", tenant_id=tenant_id, name="Subestação Principal da Indústria", location="Setor Industrial Principal", voltage="13.8 kV", current=350.0, temperature=65.0, gateway_qr="QR-GW-9999", status="NORMAL", component="Barramento Principal", predictive_failure_hours=150, recommendation="Operação estável.", esg_waste_kwh=0.5))
    db.add(AuditLogModel(tenant_id=tenant_id, user_name=username, role="CEO", action="REGISTO_NOVA_EMPRESA", details=f"Organização {tenant_id} comissionada com segurança."))
    db.commit()
    
    return {"status": "success", "message": "Organização registada com segurança! Faça login."}

@app.get("/api/panels")
def get_panels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        panels = db.query(PanelModel).filter(PanelModel.tenant_id == current_user.tenant_id).all()
        
        panels_data = []
        for p in panels:
            curr = p.current
            temp = p.temperature
            if p.status != "CRITICO_FORCADO":
                curr = round(max(10.0, p.current + random.uniform(-1.2, 1.2)), 2)
                temp = round(max(20.0, p.temperature + random.uniform(-0.3, 0.3)), 2)
            
            panels_data.append({
                "id": p.id, "name": p.name, "location": p.location, "voltage": p.voltage,
                "current": curr, "temperature": temp, "gateway_qr": p.gateway_qr,
                "status": p.status, "component": p.component, "predictive_failure_hours": p.predictive_failure_hours,
                "recommendation": p.recommendation, "esg_waste_kwh": p.esg_waste_kwh, "assigned_to": p.assigned_to
            })

        logs = db.query(AuditLogModel).filter(AuditLogModel.tenant_id == current_user.tenant_id).order_by(AuditLogModel.timestamp.desc()).limit(50).all()
        sub = db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == current_user.tenant_id).first()
        
        logs_data = [{
            "timestamp": str(l.timestamp), "user_name": l.user_name, "role": l.role,
            "action": l.action, "details": l.details
        } for l in logs]
        
        billing_info = {
            "plan_name": sub.plan_name if sub else "Enterprise",
            "status": sub.status if sub else "ACTIVE",
            "expires_at": str(sub.expires_at) if sub else "2027-10-15",
            "max_panels": sub.max_panels if sub else 25,
            "webhook_url": sub.webhook_url if sub else ""
        }

        return {"panels": panels_data, "audit_logs": logs_data, "tenant_id": current_user.tenant_id, "billing": billing_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/iot/telemetry")
def ingest_iot_telemetry(data: dict, db: Session = Depends(get_db)):
    """Endpoint público para ingestão de dados IoT (Gateways / ESP32 / CLPs de Campo)"""
    if not data:
        raise HTTPException(status_code=400, detail="Dados de telemetria em falta.")
    
    panel_id = data.get("panel_id")
    tenant_id = data.get("tenant_id", "HITECH-DEFAULT").upper().strip()
    temperature = data.get("temperature")
    current = data.get("current")
    status_val = data.get("status", "NORMAL")
    
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel ou organização não encontrada.")
    
    if temperature is not None:
        panel.temperature = float(temperature)
    if current is not None:
        panel.current = float(current)
    if status_val:
        panel.status = str(status_val)
        
    if panel.temperature > 95.0:
        panel.status = "CRITICO"
        panel.recommendation = "[IoT] Alerta de temperatura extrema registada em campo!"

    db.add(AuditLogModel(
        tenant_id=tenant_id, 
        user_name="GATEWAY_IOT", 
        role="SYSTEM", 
        action="TELEMETRIA_CAMPO", 
        details=f"Telemetria recebida para {panel_id}: {panel.temperature}°C, {panel.current}A."
    ))
    db.commit()
    return {"status": "success", "message": f"Telemetria atualizada para o painel {panel_id}."}

@app.post("/api/demo/force-failure")
def force_failure(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Apenas o CEO pode acionar o simulador.")
    
    panel_id = data.get("panel_id") if data else None
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    
    panel.status = "CRITICO"
    panel.temperature = 108.5
    panel.current = 680.4
    panel.predictive_failure_hours = 2
    panel.recommendation = "[DEMO] Sobreaquecimento crítico simulado!"
    
    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="DEMO_FALHA_FORCADA", details=f"Falha crítica simulada no painel {panel_id}."))
    db.commit()
    return {"status": "success", "message": f"Falha crítica simulada no painel {panel_id}!"}

@app.get("/api/export/audit-csv")
def export_audit_csv(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    logs = db.query(AuditLogModel).filter(AuditLogModel.tenant_id == current_user.tenant_id).order_by(AuditLogModel.timestamp.desc()).all()
    output = io.StringIO()
    output.write("ID,Data/Hora,Usuario,Cargo,Acao,Detalhes\n")
    for l in logs:
        output.write(f"{l.id},{l.timestamp},{l.user_name},{l.role},{l.action},\"{l.details}\"\n")
    output.seek(0)
    filename = f"audit_{current_user.tenant_id}.csv"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/api/export/executive-report")
def export_executive_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    panels = db.query(PanelModel).filter(PanelModel.tenant_id == current_user.tenant_id).all()
    output = io.StringIO()
    output.write("====================================================\n")
    output.write(" HITECH VOLTGUARD - RELATORIO EXECUTIVO DE FROTA\n")
    output.write(f" Organizacao: {current_user.tenant_id} | Data: {datetime.utcnow()}\n")
    output.write("====================================================\n\n")
    
    for p in panels:
        output.write(f"ID: {p.id} | Nome: {p.name}\n")
        output.write(f"Localizacao: {p.location}\n")
        output.write(f"Status Atual: {p.status} | Corrente: {p.current}A | Temp: {p.temperature}C\n")
        output.write(f"Previsao Falha: {p.predictive_failure_hours}h | Recomendacao: {p.recommendation}\n")
        output.write("-" * 50 + "\n")
        
    output.seek(0)
    filename = f"hitech_executive_report_{current_user.tenant_id}.txt"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/plain", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.post("/api/tenant/upgrade-plan")
def upgrade_plan(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Apenas o CEO pode alterar o plano da organização.")
    
    new_plan = data.get("plan_name", "Enterprise") if data else "Enterprise"
    sub = db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == current_user.tenant_id).first()
    if not sub:
        sub = TenantSubscriptionModel(tenant_id=current_user.tenant_id)
        db.add(sub)
    
    sub.plan_name = new_plan
    sub.max_panels = 50 if new_plan == "Enterprise" else 15
    sub.status = "ACTIVE"
    sub.expires_at = datetime.utcnow() + timedelta(days=365)
    
    db.add(AuditLogModel(
        tenant_id=current_user.tenant_id, 
        user_name=current_user.username, 
        role=current_user.role, 
        action="BILLING_UPGRADE", 
        details=f"Plano comercial atualizado para {new_plan} (Limite: {sub.max_panels} painéis)."
    ))
    db.commit()
    return {"status": "success", "message": f"Subscrição atualizada com sucesso para o plano {new_plan}!"}

@app.post("/api/tenant/webhook")
def update_webhook(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Apenas o CEO pode configurar webhooks.")
    webhook_url = data.get("webhook_url", "") if data else ""
    sub = db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == current_user.tenant_id).first()
    if not sub:
        sub = TenantSubscriptionModel(tenant_id=current_user.tenant_id)
        db.add(sub)
    sub.webhook_url = webhook_url
    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="WEBHOOK_CONFIG", details=f"Webhook atualizado para {webhook_url}."))
    db.commit()
    return {"status": "success", "message": "Webhook configurado com sucesso!"}

async def send_real_webhook(url: str, payload: dict):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Erro ao despachar webhook para {url}: {e}")

@app.post("/api/alerts/dispatch")
async def dispatch_critical_alert(data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    panel_id = data.get("panel_id") if data else None
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    
    sub = db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == current_user.tenant_id).first()
    webhook_destino = sub.webhook_url if sub and sub.webhook_url else "Nenhum configurado"

    if sub and sub.webhook_url:
        payload = {
            "event": "CRITICAL_ALERT",
            "tenant_id": current_user.tenant_id,
            "panel_id": panel.id,
            "panel_name": panel.name,
            "location": panel.location,
            "temperature": panel.temperature,
            "current": panel.current,
            "recommendation": panel.recommendation,
            "timestamp": str(datetime.utcnow())
        }
        background_tasks.add_task(send_real_webhook, sub.webhook_url, payload)

    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="ALERTA_WEBHOOK", details=f"Alerta crítico despachado para {panel.id} via Webhook ({webhook_destino})."))
    db.commit()
    return {"status": "success", "message": f"Alerta crítico despachado com sucesso para {webhook_destino}!"}

@app.post("/api/validate-nr10-pin")
def validate_nr10_pin(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not data or data.get("pin") != "1010":
        raise HTTPException(status_code=400, detail="PIN incorreto.")
    panel = db.query(PanelModel).filter(PanelModel.id == data.get("panel_id"), PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    panel.assigned_to = current_user.username
    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="NR10", details=f"Assumido no painel {panel.id}"))
    db.commit()
    return {"status": "success", "message": "Validação OK."}

@app.post("/api/panels/register")
def register_panel(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Instalador"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    if not data:
        raise HTTPException(status_code=400, detail="Dados em falta.")
    panel_id = data.get("panel_id")
    if db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == current_user.tenant_id).first():
        raise HTTPException(status_code=400, detail="Painel já existe.")
    
    db.add(PanelModel(
        id=panel_id, tenant_id=current_user.tenant_id, 
        name=data.get("name"), location=data.get("location"), 
        voltage=data.get("voltage"), gateway_qr=data.get("gateway_qr"), 
        status="NORMAL", current=150.0, temperature=50.0
    ))
    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="COMISSIONAMENTO", details=f"Painel {panel_id} registado."))
    db.commit()
    return {"status": "success", "message": "Registado com sucesso."}

@app.get("/")
def serve_index():
    return FileResponse("index.html")

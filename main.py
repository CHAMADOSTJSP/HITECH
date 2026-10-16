import os
import io
import random
import hashlib
import httpx
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
    gateway_qr = Column(String, nullable=True, index=True)
    status = Column(String, default="NORMAL")
    component = Column(String, default="Disjuntor Principal")
    predictive_failure_hours = Column(Integer, default=120)
    recommendation = Column(String, default="Operação nominal estável.")
    esg_waste_kwh = Column(Float, default=1.2)
    assigned_to = Column(String, nullable=True)

class PanelHistoryModel(Base):
    __tablename__ = "panel_history"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    panel_id = Column(String, index=True, nullable=False)
    timestamp = Column(String, nullable=False)
    temperature = Column(Float, nullable=False)

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

class TenantRuleModel(Base):
    __tablename__ = "tenant_rules"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String, index=True, nullable=False)
    max_temperature = Column(Float, default=85.0)
    max_current = Column(Float, default=500.0)

class WorkOrderModel(Base):
    __tablename__ = "work_orders"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String, default="HITECH-DEFAULT", index=True)
    panel_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    priority = Column(String, default="ALTA")
    status = Column(String, default="ABERTA")
    assigned_technician = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)

class InventoryModel(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String, default="HITECH-DEFAULT", index=True)
    part_name = Column(String, nullable=False)
    category = Column(String, default="Elétrica / Manutenção")
    quantity_in_stock = Column(Integer, default=10)
    min_threshold = Column(Integer, default=3)
    unit_cost = Column(Float, default=150.0)

class UserModel(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    role = Column(String, default="CEO")
    tenant_id = Column(String, default="HITECH-DEFAULT")
    plan = Column(String, default="Enterprise")

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise - Master Core")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, stored_password: str) -> bool:
    try:
        if not stored_password:
            return False
        return hashlib.sha256(plain_password.encode('utf-8')).hexdigest() == stored_password
    except Exception:
        return plain_password == stored_password

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
            UserModel(username="TecnicoMarcos", password=hash_password("123456"), role="Técnico de Campo", tenant_id="HITECH-DEFAULT", plan="Enterprise")
        ]
        for u in default_users:
            db.merge(u)

        if db.query(TenantRuleModel).filter(TenantRuleModel.tenant_id == "HITECH-DEFAULT").count() == 0:
            db.add(TenantRuleModel(tenant_id="HITECH-DEFAULT", max_temperature=85.0, max_current=500.0))

        if db.query(PanelModel).count() == 0:
            p1 = PanelModel(id="PANEL-01", tenant_id="HITECH-DEFAULT", name="Cubículo Geral de Média Tensão (MT)", location="Subestação Principal - Ribeirão Preto", voltage="13.8 kV", current=454.23, temperature=70.58, gateway_qr="QR-GW-0010", status="NORMAL", component="Barramento de Cobre", predictive_failure_hours=145, recommendation="Inspeção termográfica de rotina em 60 dias.", esg_waste_kwh=0.8)
            p2 = PanelModel(id="PANEL-02", tenant_id="HITECH-DEFAULT", name="QGBT - Alimentação de Baixa Tensão", location="Fábrica 01 - Setor de Utilidades", voltage="380V AC", current=215.5, temperature=91.19, gateway_qr="QR-GW-0070", status="CRITICO", component="Contator Geral 400A", predictive_failure_hours=18, recommendation="Substituição imediata do contator devido a desgaste.", esg_waste_kwh=4.5)
            p3 = PanelModel(id="PANEL-03", tenant_id="HITECH-DEFAULT", name="Painel de Bombeamento / Incessor", location="Fábrica 02 - Saneamento", voltage="380V AC", current=530.94, temperature=65.12, gateway_qr="QR-GW-1104", status="NORMAL", component="Inversores de Frequência", predictive_failure_hours=210, recommendation="Filtros operacionais.", esg_waste_kwh=1.1)
            
            initial_panels = [p1, p2, p3]
            db.add_all(initial_panels)
            
            now = datetime.utcnow()
            for p in initial_panels:
                base_temp = p.temperature
                for i in range(5):
                    t_point = (now - timedelta(minutes=(5 - i) * 10)).strftime("%H:%M")
                    db.add(PanelHistoryModel(panel_id=p.id, timestamp=t_point, temperature=round(base_temp + random.uniform(-1.5, 1.0), 2)))

            db.add(TenantSubscriptionModel(tenant_id="HITECH-DEFAULT", plan_name="Enterprise", status="ACTIVE", max_panels=25, webhook_url="https://httpbin.org/post"))
            db.add(WorkOrderModel(tenant_id="HITECH-DEFAULT", panel_id="PANEL-02", title="Substituição de Contator QGBT", priority="CRITICA", status="EM_ANDAMENTO", assigned_technician="TecnicoMarcos", description="Sobreaquecimento detetado."))
            db.add(InventoryModel(tenant_id="HITECH-DEFAULT", part_name="Contator Geral 400A", category="Comutação", quantity_in_stock=4, min_threshold=2, unit_cost=450.0))
            db.add(AuditLogModel(tenant_id="HITECH-DEFAULT", user_name="RafaelFelipe", role="CEO", action="INICIALIZACAO", details="Sistema verificado e inicializado com sucesso."))
            
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro na BD: {e}")
    finally:
        db.close()

init_db()

class User(BaseModel):
    username: str
    role: str
    tenant_id: str
    plan: str

class TelemetryData(BaseModel):
    panel_id: str
    temperature: float
    current: float
    voltage: Optional[str] = "380V AC"
    gateway_qr: Optional[str] = None

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

@app.get("/logo.jpg")
def get_logo():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(base_dir, "logo.jpg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="Logo não encontrada.")

@app.post("/api/token")
def login(credentials: dict, db: Session = Depends(get_db)):
    username = credentials.get("username", "").strip()
    password = credentials.get("password", "").strip()
    
    db_user = db.query(UserModel).filter(UserModel.username == username).first()
    if not db_user or not verify_password(password, db_user.password):
        raise HTTPException(status_code=400, detail="Utilizador ou senha incorretos.")
    
    token = jwt.encode({"sub": db_user.username, "role": db_user.role, "tenant_id": db_user.tenant_id, "plan": db_user.plan, "exp": datetime.utcnow() + timedelta(days=1)}, SECRET_KEY, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "role": db_user.role, "plan": db_user.plan}

@app.post("/api/tenant/register")
def register_tenant(data: dict, db: Session = Depends(get_db)):
    tenant_id = data.get("tenant_id", "").upper().strip()
    admin_user = data.get("username", "").strip()
    password = data.get("password", "").strip()
    
    if not tenant_id or not admin_user or not password:
        raise HTTPException(status_code=400, detail="Dados de registo incompletos.")
    
    existing = db.query(UserModel).filter(UserModel.username == admin_user).first()
    if existing:
        raise HTTPException(status_code=400, detail="Nome de utilizador já existe.")
        
    new_user = UserModel(username=admin_user, password=hash_password(password), role="CEO", tenant_id=tenant_id, plan="Enterprise")
    db.merge(new_user)
    db.add(TenantSubscriptionModel(tenant_id=tenant_id, plan_name="Enterprise", status="ACTIVE", max_panels=25, webhook_url="https://httpbin.org/post"))
    db.add(TenantRuleModel(tenant_id=tenant_id, max_temperature=85.0, max_current=500.0))
    db.add(AuditLogModel(tenant_id=tenant_id, user_name=admin_user, role="CEO", action="REGISTO_TENANT", details=f"Organização {tenant_id} registada."))
    db.commit()
    
    return {"status": "success", "message": f"Organização {tenant_id} criada com sucesso!"}

@app.post("/api/tenant/webhook")
def save_webhook(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role != "CEO":
        raise HTTPException(status_code=403, detail="Acesso restrito a CEO.")
    webhook_url = data.get("webhook_url", "").strip()
    sub = db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == current_user.tenant_id).first()
    if sub:
        sub.webhook_url = webhook_url
        db.commit()
    return {"status": "success", "message": "URL de Webhook guardada com sucesso!"}

@app.post("/api/tenant/rules")
def update_tenant_rules(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Acesso restrito para alterar regras de alarme.")
        
    max_temp = float(data.get("max_temperature", 85.0))
    max_curr = float(data.get("max_current", 500.0))
    
    rule = db.query(TenantRuleModel).filter(TenantRuleModel.tenant_id == current_user.tenant_id).first()
    if rule:
        rule.max_temperature = max_temp
        rule.max_current = max_curr
    else:
        db.add(TenantRuleModel(tenant_id=current_user.tenant_id, max_temperature=max_temp, max_current=max_curr))
        
    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="CONFIGURAR_REGRAS", details=f"Limites alterados: Temp={max_temp}°C"))
    db.commit()
    return {"status": "success", "message": f"Regras de alarme atualizadas para Limite Térmico: {max_temp}°C"}

@app.post("/api/panels/add")
def add_panel(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Acesso restrito para adicionar painéis.")
    
    panel_id = data.get("id", "").strip().upper()
    name = data.get("name", "").strip()
    location = data.get("location", "").strip()
    voltage = data.get("voltage", "380V AC").strip()
    component = data.get("component", "Disjuntor Principal").strip()
    gateway_qr = data.get("gateway_qr", f"QR-GW-{random.randint(2000,9999)}").strip()

    if not panel_id or not name or not location:
        raise HTTPException(status_code=400, detail="Preencha os campos obrigatórios do painel.")

    existing = db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == current_user.tenant_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe um painel com este ID na organização.")

    new_panel = PanelModel(
        id=panel_id, tenant_id=current_user.tenant_id, name=name, location=location,
        voltage=voltage, current=round(random.uniform(100.0, 400.0), 2),
        temperature=round(random.uniform(45.0, 68.0), 2), gateway_qr=gateway_qr,
        status="NORMAL", component=component, predictive_failure_hours=180,
        recommendation="Painel recém-comissionado. Operação estável.", esg_waste_kwh=1.0
    )
    db.add(new_panel)
    db.add(PanelHistoryModel(panel_id=panel_id, timestamp=datetime.utcnow().strftime("%H:%M"), temperature=new_panel.temperature))
    db.add(AuditLogModel(tenant_id=current_user.tenant_id, user_name=current_user.username, role=current_user.role, action="ADICIONAR_PAINEL", details=f"Painel {panel_id} adicionado."))
    db.commit()
    return {"status": "success", "message": f"Painel {panel_id} adicionado com sucesso!"}

@app.post("/api/telemetry", tags=["Industrial Ingestion"])
def ingest_telemetry(data: TelemetryData, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    panel = db.query(PanelModel).filter(PanelModel.id == data.panel_id, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail=f"Painel {data.panel_id} não encontrado.")
    
    rule = db.query(TenantRuleModel).filter(TenantRuleModel.tenant_id == current_user.tenant_id).first()
    temp_limit = rule.max_temperature if rule else 85.0
    
    panel.temperature = data.temperature
    panel.current = data.current
    if data.voltage:
        panel.voltage = data.voltage
        
    if data.temperature > temp_limit:
        panel.status = "CRITICO"
        panel.recommendation = f"ALERTA: Temperatura ultrapassou o limite configurado ({temp_limit}°C)!"
    else:
        panel.status = "NORMAL"
        panel.recommendation = "Sistema a operar dentro dos parâmetros nominais."
        
    db.add(PanelHistoryModel(panel_id=panel.id, timestamp=datetime.utcnow().strftime("%H:%M"), temperature=panel.temperature))
    db.commit()
    return {"status": "success", "message": f"Telemetria de {data.panel_id} atualizada com base no limite de {temp_limit}°C."}

@app.post("/api/demo/force-failure")
async def force_failure(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    panel_id = data.get("panel_id")
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    
    panel.status = "CRITICO"
    panel.temperature = 94.5
    panel.predictive_failure_hours = 2
    panel.recommendation = "ALERTA CRÍTICO: Sobreaquecimento extremo detetado!"
    
    db.add(PanelHistoryModel(panel_id=panel.id, timestamp=datetime.utcnow().strftime("%H:%M"), temperature=panel.temperature))
    db.add(AuditLogModel(
        tenant_id=current_user.tenant_id,
        user_name=current_user.username,
        role=current_user.role,
        action="FORCAR_FALHA",
        details=f"Falha crítica simulada no painel {panel_id}."
    ))
    db.commit()

    sub = db.query(TenantSubscriptionModel).filter(TenantSubscriptionModel.tenant_id == current_user.tenant_id).first()
    if sub and sub.webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(sub.webhook_url, json={"event": "CRITICAL_ALERT", "panel_id": panel.id, "temperature": panel.temperature}, timeout=5.0)
        except Exception:
            pass

    await manager.broadcast({"event": "PANEL_UPDATE", "panel_id": panel.id, "status": "CRITICO"})
    return {"status": "success", "message": f"Falha crítica simulada com sucesso no cubículo {panel.id}!"}

@app.get("/api/panels")
def get_panels(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        panels = db.query(PanelModel).filter(PanelModel.tenant_id == current_user.tenant_id).all()
        
        panels_data = []
        for p in panels:
            curr = p.current
            temp = p.temperature
            if p.status != "CRITICO":
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
        rule = db.query(TenantRuleModel).filter(TenantRuleModel.tenant_id == current_user.tenant_id).first()
        work_orders = db.query(WorkOrderModel).filter(WorkOrderModel.tenant_id == current_user.tenant_id).all()
        inventory = db.query(InventoryModel).filter(InventoryModel.tenant_id == current_user.tenant_id).all()
        
        history_data = {}
        for p in panels:
            h_records = db.query(PanelHistoryModel).filter(PanelHistoryModel.panel_id == p.id).order_by(PanelHistoryModel.id.asc()).all()
            history_data[p.id] = [{"timestamp": h.timestamp, "temperature": h.temperature} for h in h_records]

        logs_data = [{"timestamp": str(l.timestamp), "user_name": l.user_name, "role": l.role, "action": l.action, "details": l.details} for l in logs]
        wo_data = [{"id": w.id, "panel_id": w.panel_id, "title": w.title, "priority": w.priority, "status": w.status, "assigned_technician": w.assigned_technician, "created_at": str(w.created_at), "description": w.description} for w in work_orders]
        inv_data = [{"id": i.id, "part_name": i.part_name, "category": i.category, "quantity_in_stock": i.quantity_in_stock, "min_threshold": i.min_threshold, "unit_cost": i.unit_cost} for i in inventory]
        
        billing_info = {
            "plan_name": sub.plan_name if sub else "Enterprise",
            "status": sub.status if sub else "ACTIVE",
            "expires_at": str(sub.expires_at) if sub else "2027-10-15",
            "max_panels": sub.max_panels if sub else 25,
            "webhook_url": sub.webhook_url if sub else "",
            "max_temperature": rule.max_temperature if rule else 85.0,
            "max_current": rule.max_current if rule else 500.0
        }

        return {
            "panels": panels_data, "audit_logs": logs_data, "work_orders": wo_data,
            "inventory": inv_data, "history": history_data, "tenant_id": current_user.tenant_id, "billing": billing_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/panels/qr/{qr_code}")
def get_panel_by_qr(qr_code: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    panel = db.query(PanelModel).filter(PanelModel.gateway_qr == qr_code, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        panel = db.query(PanelModel).filter(PanelModel.id == qr_code, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Nenhum cubículo encontrado para este código QR ou ID.")
    return {
        "id": panel.id, "name": panel.name, "location": panel.location, "voltage": panel.voltage,
        "current": panel.current, "temperature": panel.temperature, "gateway_qr": panel.gateway_qr,
        "status": panel.status, "component": panel.component, "predictive_failure_hours": panel.predictive_failure_hours,
        "recommendation": panel.recommendation, "esg_waste_kwh": panel.esg_waste_kwh, "assigned_to": panel.assigned_to
    }

@app.post("/api/inventory/update")
def update_inventory_item(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    part_name = data.get("part_name")
    category = data.get("category", "Elétrica")
    qty_change = int(data.get("quantity_change", 0))
    unit_cost = float(data.get("unit_cost", 150.0))
    min_threshold = int(data.get("min_threshold", 3))

    item = db.query(InventoryModel).filter(InventoryModel.part_name == part_name, InventoryModel.tenant_id == current_user.tenant_id).first()
    if item:
        item.quantity_in_stock += qty_change
        item.unit_cost = unit_cost
    else:
        db.add(InventoryModel(tenant_id=current_user.tenant_id, part_name=part_name, category=category, quantity_in_stock=qty_change, min_threshold=min_threshold, unit_cost=unit_cost))
    
    db.commit()
    return {"status": "success", "message": "Inventário atualizado com sucesso!"}

@app.websocket("/ws/panels")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/export/executive-report")
def export_executive_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    output = io.StringIO()
    output.write("HITECH VOLTGUARD - RELATORIO EXECUTIVO OPERACIONAL\n")
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/plain", headers={"Content-Disposition": "attachment; filename=relatorio.txt"})

@app.get("/")
def serve_index():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(base_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail=f"index.html não encontrado no caminho: {index_path}")

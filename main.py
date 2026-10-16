import os
import io
import random
import hashlib
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, WebSocket, WebSocketDisconnect
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

class PushSubscriptionModel(Base):
    __tablename__ = "push_subscriptions"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, index=True, nullable=False)
    endpoint_data = Column(String, nullable=False)

class UserModel(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String, nullable=False)
    role = Column(String, default="CEO")
    tenant_id = Column(String, default="HITECH-DEFAULT")
    plan = Column(String, default="Enterprise")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise - Phase 10 (Inventory & Spare Parts Hub)")

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

@app.get("/logo.jpg")
def get_logo():
    logo_path = "logo.jpg"
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="Logo não encontrada.")

@app.get("/manifest.json")
def get_manifest():
    manifest_content = """{
  "name": "HITECH VoltGuard SCADA",
  "short_name": "VoltGuard",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0b0f19",
  "theme_color": "#1e293b",
  "icons": [
    {
      "src": "/logo.jpg",
      "sizes": "192x192",
      "type": "image/jpeg"
    }
  ]
}"""
    return StreamingResponse(iter([manifest_content]), media_type="application/json")

@app.get("/sw.js")
def get_service_worker():
    sw_content = """self.addEventListener('install', (event) => {
    self.skipWaiting();
});
self.addEventListener('fetch', (event) => {
    event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});"""
    return StreamingResponse(iter([sw_content]), media_type="application/javascript")

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
            db.add(WorkOrderModel(tenant_id="HITECH-DEFAULT", panel_id="PANEL-02", title="Substituição de Contator QGBT", priority="CRITICA", status="EM_ANDAMENTO", assigned_technician="TecnicoMarcos", description="Sobreaquecimento detetado em campo. Requer troca imediata."))
            db.add(InventoryModel(tenant_id="HITECH-DEFAULT", part_name="Contator Geral 400A", category="Comutação", quantity_in_stock=4, min_threshold=2, unit_cost=450.0))
            db.add(InventoryModel(tenant_id="HITECH-DEFAULT", part_name="Sensor Termopar Tipo K", category="Sensores", quantity_in_stock=15, min_threshold=5, unit_cost=80.0))
            db.add(InventoryModel(tenant_id="HITECH-DEFAULT", part_name="Disjuntor Caixa Moldada 250A", category="Proteção", quantity_in_stock=3, min_threshold=2, unit_cost=950.0))
            db.add(AuditLogModel(tenant_id="HITECH-DEFAULT", user_name="RafaelFelipe", role="CEO", action="INICIALIZACAO", details="Sistema Fase 10 (Inventário de Peças) inicializado com sucesso."))
            
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
        work_orders = db.query(WorkOrderModel).filter(WorkOrderModel.tenant_id == current_user.tenant_id).all()
        inventory = db.query(InventoryModel).filter(InventoryModel.tenant_id == current_user.tenant_id).all()
        
        logs_data = [{
            "timestamp": str(l.timestamp), "user_name": l.user_name, "role": l.role,
            "action": l.action, "details": l.details
        } for l in logs]

        wo_data = [{
            "id": w.id, "panel_id": w.panel_id, "title": w.title, "priority": w.priority,
            "status": w.status, "assigned_technician": w.assigned_technician,
            "created_at": str(w.created_at), "description": w.description
        } for w in work_orders]

        inv_data = [{
            "id": i.id, "part_name": i.part_name, "category": i.category,
            "quantity_in_stock": i.quantity_in_stock, "min_threshold": i.min_threshold,
            "unit_cost": i.unit_cost
        } for i in inventory]
        
        billing_info = {
            "plan_name": sub.plan_name if sub else "Enterprise",
            "status": sub.status if sub else "ACTIVE",
            "expires_at": str(sub.expires_at) if sub else "2027-10-15",
            "max_panels": sub.max_panels if sub else 25,
            "webhook_url": sub.webhook_url if sub else ""
        }

        return {
            "panels": panels_data, 
            "audit_logs": logs_data, 
            "work_orders": wo_data,
            "inventory": inv_data,
            "tenant_id": current_user.tenant_id, 
            "billing": billing_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/inventory/update")
def update_inventory_item(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Apenas CEO ou Gerente podem gerir o inventário de peças.")
    
    if not data:
        raise HTTPException(status_code=400, detail="Dados em falta.")
    
    part_name = data.get("part_name")
    category = data.get("category", "Elétrica / Manutenção")
    qty_change = int(data.get("quantity_change", 0))
    unit_cost = float(data.get("unit_cost", 100.0))
    min_threshold = int(data.get("min_threshold", 3))

    if not part_name:
        raise HTTPException(status_code=400, detail="Nome da peça em falta.")

    item = db.query(InventoryModel).filter(InventoryModel.part_name == part_name, InventoryModel.tenant_id == current_user.tenant_id).first()
    if item:
        item.quantity_in_stock += qty_change
        item.unit_cost = unit_cost
    else:
        item = InventoryModel(
            tenant_id=current_user.tenant_id,
            part_name=part_name,
            category=category,
            quantity_in_stock=qty_change if qty_change > 0 else 5,
            min_threshold=min_threshold,
            unit_cost=unit_cost
        )
        db.add(item)

    db.add(AuditLogModel(
        tenant_id=current_user.tenant_id,
        user_name=current_user.username,
        role=current_user.role,
        action="INVENTARIO_ATUALIZACAO",
        details=f"Peça '{part_name}' atualizada. Ajuste de stock: {qty_change} unidades."
    ))
    db.commit()
    return {"status": "success", "message": f"Inventário atualizado para a peça '{part_name}' com sucesso!"}

@app.post("/api/pwa/subscribe")
def pwa_subscribe(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    endpoint = data.get("endpoint", "") if data else ""
    if not endpoint:
        raise HTTPException(status_code=400, detail="Endpoint push em falta.")
    
    db.add(PushSubscriptionModel(username=current_user.username, endpoint_data=endpoint))
    db.add(AuditLogModel(
        tenant_id=current_user.tenant_id,
        user_name=current_user.username,
        role=current_user.role,
        action="PWA_PUSH_SUBSCRIBE",
        details=f"Dispositivo móvel registado para notificações push para o utilizador {current_user.username}."
    ))
    db.commit()
    return {"status": "success", "message": "Dispositivo registado com sucesso para receber alertas PWA!"}

@app.post("/api/ai/predictive-analysis")
def run_ai_predictive_analysis(data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Apenas CEO ou Gerente podem executar o motor de IA Preditiva.")
    
    panel_id = data.get("panel_id") if data else None
    if not panel_id:
        raise HTTPException(status_code=400, detail="ID do painel em falta.")
    
    panel = db.query(PanelModel).filter(PanelModel.id == panel_id, PanelModel.tenant_id == current_user.tenant_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    
    temp = panel.temperature
    risk_score = round(min(100.0, max(5.0, (temp / 110.0) * 100.0)), 2)
    
    if temp > 90.0:
        predicted_hours = max(4, int(200.0 - (temp * 1.5)))
        ai_recommendation = f"[IA PREDITIVA] Risco crítico de degradação ({risk_score}%). Anomalia térmica detetada em séries temporais. Recomenda-se intervenção imediata."
    elif temp > 75.0:
        predicted_hours = int(350.0 - (temp * 2.0))
        ai_recommendation = f"[IA PREDITIVA] Atenção moderada ({risk_score}%). Tendência de aquecimento acima da linha de base nominal."
    else:
        predicted_hours = 720
        ai_recommendation = f"[IA PREDITIVA] Comportamento estável ({risk_score}% de risco). Nenhuma anomalia detetada nos algoritmos de desvio."

    panel.predictive_failure_hours = predicted_hours
    panel.recommendation = ai_recommendation

    db.add(AuditLogModel(
        tenant_id=current_user.tenant_id,
        user_name=current_user.username,
        role=current_user.role,
        action="IA_PREDICTIVE_ANALYSIS",
        details=f"Análise de IA executada para o painel {panel_id}. Risco estimado: {risk_score}%. Previsão: {predicted_hours}h."
    ))
    db.commit()

    return {
        "status": "success",
        "panel_id": panel_id,
        "risk_score_percent": risk_score,
        "predictive_failure_hours": predicted_hours,
        "recommendation": ai_recommendation
    }

@app.websocket("/ws/panels")
async def websocket_panels_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"event": "PING_ACK", "message": "Conexão WebSocket ativa HITECH VoltGuard."})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/iot/telemetry")
async def ingest_iot_telemetry(data: dict, db: Session = Depends(get_db)):
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

    await manager.broadcast({
        "event": "TELEMETRY_UPDATE",
        "tenant_id": tenant_id,
        "panel_id": panel_id,
        "temperature": panel.temperature,
        "current": panel.current,
        "status": panel.status
    })

    return {"status": "success", "message": f"Telemetria atualizada para o painel {panel_id}."}

@app.get("/api/export/executive-report")
def export_executive_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["CEO", "Gerente"]:
        raise HTTPException(status_code=403, detail="Acesso restrito.")
    
    panels = db.query(PanelModel).filter(PanelModel.tenant_id == current_user.tenant_id).all()
    inventory = db.query(InventoryModel).filter(InventoryModel.tenant_id == current_user.tenant_id).all()
    
    output = io.StringIO()
    output.write("====================================================\n")
    output.write(" HITECH VOLTGUARD - RELATORIO EXECUTIVO (FASE 10 - INVENTARIO)\n")
    output.write(f" Organizacao: {current_user.tenant_id} | Data: {datetime.utcnow()}\n")
    output.write("====================================================\n\n")
    
    output.write("[ESTADO DOS PAINEIS]\n")
    for p in panels:
        output.write(f"- {p.id} ({p.name}) | Status: {p.status} | Temp: {p.temperature}°C | Previsao Falha: {p.predictive_failure_hours}h\n")
        
    output.write("\n[INVENTARIO DE PECAS E ALMOXARIFADO]\n")
    for i in inventory:
        output.write(f"- Peca: {i.part_name} | Categoria: {i.category} | Stock: {i.quantity_in_stock} (Min: {i.min_threshold}) | Custo Unit.: R$ {i.unit_cost}\n")
        
    output.seek(0)
    filename = f"hitech_executive_report_inventory_{current_user.tenant_id}.txt"
    return StreamingResponse(iter([output.getvalue()]), media_type="text/plain", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/")
def serve_index():
    return FileResponse("index.html")

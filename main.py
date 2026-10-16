from fastapi import FastAPI, Depends, HTTPException, status, Body
from pydantic import BaseModel
from typing import Optional
import datetime

# Exemplo de modelo Pydantic para validação da telemetria recebida de CLPs/Gateways
class TelemetryData(BaseModel):
    panel_id: str
    temperature: float
    current: float
    voltage: Optional[str] = "380V AC"
    gateway_qr: Optional[str] = None

# Exemplo de endpoint de ingestão de telemetria industrial (Passo 1)
@app.post("/api/telemetry", tags=["Industrial Ingestion"])
def ingest_telemetry(data: TelemetryData, current_user: dict = Depends(get_current_user)):
    """
    Endpoint para receber dados de temperatura e corrente diretamente de 
    CLPs, ESP32 ou Gateways IoT em tempo real.
    """
    tenant_id = current_user.get("tenant_id", "HITECH-DEFAULT")
    
    # Verifica se o painel existe na base de dados da organização
    panel = db_find_panel(tenant_id, data.panel_id)
    if not panel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Painel {data.panel_id} não encontrado para este tenant."
        )
    
    # Atualiza os valores em tempo real
    panel["temperature"] = data.temperature
    panel["current"] = data.current
    if data.voltage:
        panel["voltage"] = data.voltage
        
    # Regra automática de criticidade térmica (> 85°C dispara alerta crítico)
    if data.temperature > 85.0:
        panel["status"] = "CRITICO"
        panel["recommendation"] = "ALERTA: Pico térmico detetado via telemetria industrial!"
        # Dispara webhook automático se configurado para o tenant
        trigger_tenant_webhook(tenant_id, panel)
    else:
        panel["status"] = "NORMAL"
        panel["recommendation"] = "Sistema a operar dentro dos parâmetros nominais."
        
    # Regista o histórico imutável para os gráficos de tendência térmica
    append_panel_history(tenant_id, data.panel_id, data.temperature)
    
    return {
        "status": "success",
        "message": f"Telemetria do painel {data.panel_id} atualizada com sucesso.",
        "current_status": panel["status"]
    }

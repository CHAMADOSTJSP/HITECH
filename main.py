import os
import logging
import httpx
from fastapi import FastAPI, APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoltGuardBackend")

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise")
router = APIRouter(prefix="/api/v1", tags=["Webhooks & Alertas"])

# Credenciais (Pode usar variáveis de ambiente no Render para maior segurança)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "SEU_BOT_TOKEN_AQUI")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "SEU_CHAT_ID_AQUI")

class WebhookPayload(BaseModel):
    panel_id: str = Field(..., example="PANEL-01")
    status: str = Field(..., example="CRÍTICO (SOBREAQUECIMENTO)")
    message: str = Field(..., example="Temperatura do barramento atingiu 88°C.")

@router.post("/webhook/trigger", status_code=status.HTTP_200_OK)
async def trigger_webhook_alert(payload: WebhookPayload):
    """
    Dispara alertas operacionais críticos em tempo real para o Telegram.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or TELEGRAM_BOT_TOKEN == "SEU_BOT_TOKEN_AQUI":
        logger.error("Credenciais do Telegram não configuradas corretamente.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Serviço de mensageria não configurado no servidor."
        )

    mensagem_telegram = (
        f"🚨 *ALERTA CRÍTICO - HITECH VOLTGUARD* 🚨\n\n"
        f"• *Painel/Ativo:* `{payload.panel_id}`\n"
        f"• *Status Operacional:* *{payload.status}*\n"
        f"• *Ocorrência:* {payload.message}\n\n"
        f"⚠️ *Ação recomendada:* Acesse o painel SCADA para verificação e emissão de O.S."
    )

    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                telegram_url,
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": mensagem_telegram,
                    "parse_mode": "Markdown"
                }
            )

        if response.status_code != 200:
            logger.error(f"Erro na API do Telegram: {response.text}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Falha na comunicação com a API de mensageria externa."
            )

        return {
            "status": "success",
            "message": f"Alerta do painel {payload.panel_id} enviado com sucesso!"
        }

    except httpx.RequestError as exc:
        logger.error(f"Erro de conexão com o Telegram: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de alerta temporariamente indisponível."
        )

app.include_router(router)

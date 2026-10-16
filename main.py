import os
import logging
import httpx
from fastapi import FastAPI, APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoltGuardBackend")

app = FastAPI(title="HITECH VoltGuard SCADA Enterprise")
router = APIRouter(prefix="/api/v1", tags=["Webhooks & Alertas"])

# Credenciais (Pode usar variáveis de ambiente no Render)
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

# Rota Raiz (Serve o painel HTML diretamente ao acessar o link do Render)
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>HITECH VoltGuard SCADA Enterprise</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #121212;
                color: #e0e0e0;
                padding: 20px;
                margin: 0;
            }
            .container {
                max-width: 500px;
                margin: 0 auto;
                background: #1e1e1e;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            }
            .btn-simular {
                background-color: #dc3545;
                color: #fff;
                border: none;
                padding: 12px 20px;
                font-weight: bold;
                border-radius: 5px;
                cursor: pointer;
                width: 100%;
                margin-bottom: 20px;
            }
            .btn-simular:hover {
                background-color: #bd2130;
            }
            .btn-acao {
                background-color: #007bff;
                color: #fff;
                border: none;
                padding: 10px 16px;
                border-radius: 5px;
                cursor: pointer;
                margin: 5px 0;
            }
            #qr-reader {
                width: 100%;
                min-height: 320px;
                background-color: #2c2c2c;
                border-radius: 8px;
                overflow: hidden;
                margin-top: 15px;
            }
            #qr-reader video {
                object-fit: cover !important;
                width: 100% !important;
                height: 100% !important;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>VoltGuard SCADA - Painel de Controle</h2>
            <hr style="border: 0.5px solid #333; margin-bottom: 20px;">

            <h3>Simulador Comercial</h3>
            <button class="btn-simular" onclick="executarSimulacaoEWebhook('PANEL-01')">
                ⚡ Forçar Falha Crítica (PANEL-01)
            </button>

            <hr style="border: 0.5px solid #333; margin: 20px 0;">

            <h3>Comissionamento por QR Code</h3>
            <p style="font-size: 14px; color: #aaa;">Aproxime o código do equipamento para mapeamento.</p>
            
            <button id="btn-iniciar-scanner" class="btn-acao" onclick="iniciarScannerMobile()">📷 Abrir Câmera</button>
            <button id="btn-parar-scanner" class="btn-acao" onclick="pararScanner()" style="background-color: #6c757d; display: none;">⏹️ Fechar Câmera</button>

            <div id="qr-reader"></div>
        </div>

        <script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
        <script>
            let html5QrcodeScanner = null;

            async function executarSimulacaoEWebhook(panelId) {
                try {
                    const response = await fetch('/api/v1/webhook/trigger', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            panel_id: panelId,
                            status: "CRÍTICO (SOBREAQUECIMENTO)",
                            message: "Temperatura do barramento atingiu 88°C no painel monitorado."
                        })
                    });

                    const data = await response.json();
                    if (response.ok) {
                        alert(`✅ Alerta enviado com sucesso para o seu Telegram!\\nPainel: ${panelId}`);
                    } else {
                        alert(`⚠️ Erro: ${data.detail || 'Falha ao acionar webhook'}`);
                    }
                } catch (error) {
                    console.error("Erro na requisição:", error);
                    alert("Erro de conexão com o servidor ao disparar o webhook.");
                }
            }

            function iniciarScannerMobile() {
                document.getElementById('btn-iniciar-scanner').style.display = 'none';
                document.getElementById('btn-parar-scanner').style.display = 'inline-block';

                setTimeout(() => {
                    if (!html5QrcodeScanner) {
                        html5QrcodeScanner = new Html5Qrcode("qr-reader");
                    }

                    const config = { fps: 10, qrbox: { width: 220, height: 220 }, aspectRatio: 1.0 };

                    html5QrcodeScanner.start(
                        { facingMode: "environment" },
                        config,
                        (decodedText) => {
                            alert(`🔍 Equipamento Comissionado: ${decodedText}`);
                            pararScanner();
                        },
                        (errorMessage) => {}
                    ).catch((err) => {
                        console.error("Erro ao iniciar câmera:", err);
                        alert("Não foi possível acessar a câmera. Verifique permissões e HTTPS.");
                        pararScanner();
                    });
                }, 150);
            }

            function pararScanner() {
                if (html5QrcodeScanner) {
                    html5QrcodeScanner.stop().then(() => {
                        html5QrcodeScanner.clear();
                        document.getElementById('btn-iniciar-scanner').style.display = 'inline-block';
                        document.getElementById('btn-parar-scanner').style.display = 'none';
                    }).catch((err) => {
                        console.error("Erro ao desligar o scanner:", err);
                    });
                }
            }
        </script>
    </body>
    </html>
    """

app.include_router(router)

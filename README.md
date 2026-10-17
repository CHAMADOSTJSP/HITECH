# HITECH VoltGuard

Monitoramento elétrico e gestão de manutenção orientada por condição para pequenas e médias instalações industriais e comerciais.

> **Status: demonstração e homologação controlada (v0.39.0).** Não é SCADA certificado e **não deve** ser ligado a proteção, intertravamento ou comando de equipamentos. Não use dados reais de clientes antes de cumprir o `DEPLOYMENT_CHECKLIST.md`.

## O que faz hoje

- Cadastro de organizações isoladas (multiempresa), usuários e papéis: **CEO**, **Gerente**, **Técnico de Campo**.
- Painéis elétricos com leitura de temperatura, corrente e tensão; estado `SEM_DADOS` até chegar a primeira leitura real.
- Telemetria por **credencial exclusiva de dispositivo** (`POST /api/device/telemetry`, token guardado só como hash).
- Alarmes com limites por organização ou por painel, histerese, reconhecimento/encerramento e **webhook assinado (HMAC)** quando um alarme real abre.
- Ordens de serviço ligadas ao alarme, com checklist, histórico, relatório imprimível e modelos.
- Ativos, manutenção preventiva, estoque, auditoria, QR de comissionamento e relatório executivo em Excel.

Dados marcados como **DEMO** (três painéis criados no cadastro) e as abas ESG/previsão são demonstrativos, não medições.

## Rodar localmente

Requer Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # defina SECRET_KEY (>= 32 caracteres)
python -m unittest discover -s tests -v
uvicorn main:app --host 127.0.0.1 --port 8000
```

Abra `http://127.0.0.1:8000`, cadastre uma organização (senha ≥ 12 caracteres) e entre. A documentação interativa da API está em `/docs`.

## Enviar uma leitura (gateway)

1. Aba **Dispositivos** → criar credencial para um painel → copiar o token (exibido uma única vez).
2. Enviar:

```bash
curl -X POST "https://SEU-SERVICO.onrender.com/api/device/telemetry" \
  -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"panel_id":"ID_DO_PAINEL","temperature":42.5,"current":118.4,"voltage":"380 V AC"}'
```

`ONLINE` significa que a credencial enviou dados recentemente; **não** comprova a saúde física do equipamento.

## Webhook de alarmes

Aba **Webhooks** (CEO): URL HTTPS pública. Cada alarme novo envia `ALARM_OPENED` com cabeçalho `X-VoltGuard-Signature: sha256=<hmac>`, onde o HMAC-SHA256 é calculado sobre o corpo bruto com o segredo de `GET /api/tenant/webhook/secret`. Há 3 tentativas e o resultado fica na auditoria.

## Publicar no Render

1. Repositório **privado** no GitHub com estes arquivos na raiz.
2. Render → **New + → Blueprint** → conectar o repositório → revisar `render.yaml`.
3. Conferir `https://SEU-SERVICO.onrender.com/health` e seguir o `DEPLOYMENT_CHECKLIST.md`.

Os planos `free` de web e PostgreSQL servem para demonstração (o web dorme por inatividade e o banco gratuito tem política de expiração). Para qualquer piloto com dados reais, use plano pago com backup e restauração testados.

## Documentos

| Arquivo | Conteúdo |
|---|---|
| `ESTRATEGIA_PRODUTO.md` | Posicionamento, cliente-alvo, etapas e métricas |
| `ROADMAP.md` | Plano de execução, critérios de pronto e responsabilidades |
| `DEPLOYMENT_CHECKLIST.md` | Verificações antes/depois do deploy |
| `CHANGELOG.md` | Histórico de versões |
| `docs/roteiro_entrevista.md` | Roteiro para entrevistas com responsáveis de manutenção |
| `docs/proposta_piloto.md` | Modelo de proposta de piloto |
| `docs/historico-readme.md` | README antigo (notas das versões 0.5–0.38) |

## Limitações conhecidas

- IDs de painel e usernames são únicos globalmente (migração para chave composta prevista no `ROADMAP.md`).
- Migrações ainda são ajustes manuais em `init_db`; Alembic é o próximo passo.
- Sem MFA, recuperação de senha por e-mail ou convite de usuários.
- Sem driver Modbus/OPC UA: a conexão com medidores exige um gateway externo (ver `ROADMAP.md`).
- Limite de requisições em memória por processo (não distribuído).

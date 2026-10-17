# Roadmap de execução — HITECH VoltGuard

Divisão de trabalho acordada: **Claude** desenvolve código, testes, documentação e material comercial. **Você** faz instalações em campo, relacionamento com clientes e as validações que dependem de ambiente real ou de pessoas.

## Fase 1 — Base confiável (código entregue na v0.39.0; falta validar)

Entregue: leituras nunca inventadas, alarme único e testado, webhook de alarmes reais assinado, usuários/papéis com efeito imediato, simulação restrita à demo, retenção de histórico, limitador por IP real, KPIs reais.

**Pronto quando:**
- [ ] `python -m unittest discover -s tests -v` passa na sua máquina (eu não consegui executar a suíte no meu ambiente, sem acesso a instalar dependências).
- [ ] Deploy no Render concluído e `DEPLOYMENT_CHECKLIST.md` (incluindo as verificações novas) 100 % marcado.

**Você:** rodar os testes e me enviar a saída completa, inclusive erros. Fazer o deploy e me avisar do que falhar.

## Fase 2 — Identidade e dados (próximo lote, Claude)

- Migrações versionadas com Alembic; baseline do esquema atual.
- Chave composta (organização + ID) para painéis e usernames por organização, eliminando o vazamento de existência de IDs entre organizações.
- Convite de usuário por link, recuperação de senha e MFA (TOTP) para CEO.
- Separar `main.py` em módulos (autenticação, painéis, alarmes, ordens, ativos, relatórios) sem mudar comportamento, coberto pelos testes.
- CSP e SRI nos scripts de terceiros; logs estruturados; endpoint de métricas.

**Pronto quando:** testes cobrem isolamento entre organizações em todos os endpoints; restauração de backup do PostgreSQL testada de ponta a ponta.

**Você:** decidir plano pago do Render (web + PostgreSQL) para o piloto; fornecer um e-mail de envio (SMTP) quando chegarmos à recuperação de senha.

## Fase 3 — Conectividade real (Claude + você em campo)

- Gateway de referência em Node-RED: leitura **somente leitura** de um medidor Modbus RTU/TCP, buffer local e envio ao VoltGuard com reenvio.
- Evento de telemetria padronizado: instante de origem, qualidade, unidade, ID idempotente (evita duplicados em reenvio).
- Medidas trifásicas por fase e indicadores de qualidade de energia, conforme o medidor escolhido.
- Frescor de dados e estado do dispositivo separados do estado do ativo na interface.

**Pronto quando:** um medidor real, em bancada, alimenta um painel por 7 dias sem perda de dados e com alarme validado contra uma condição provocada.

**Você:** escolher e comprar o medidor e o gateway de bancada (preciso do modelo e do manual do protocolo), instalar e testar em laboratório, e fotografar/documentar a instalação.

## Fase 4 — Piloto

- Ordens de serviço mais móveis (fotos, checklist por ativo, QR), notificação por e-mail/WhatsApp com escalonamento, relatório mensal por site.
- Linha de base e indicadores do piloto (tempo de detecção, de reconhecimento e de conclusão; alarmes sem ação).

**Pronto quando:** um cliente real usa por 30 dias com critérios de sucesso assinados e há revisão independente de segurança.

**Você:** captar o cliente, conduzir a instalação, coletar a linha de base antes de ligar o sistema. Contratar a revisão de segurança e a revisão jurídica (LGPD, contrato, SLA).

## Decisões que só você pode tomar (mudam o que eu construo)

1. Segmento inicial (ex.: alimentos/refrigeração, logística, edifícios comerciais).
2. O cliente já tem medidores/gateways ou a HITECH fornece hardware e instalação?
3. Venda de software puro, projeto de integração ou solução combinada com parceiro?
4. Quem presta suporte quando um alarme não chega? Horário de atendimento prometido.
5. Nuvem, on-premises ou híbrido para os primeiros clientes?

## Regras de qualidade (valem para todo lote)

- Nenhum valor exibido como medição sem origem real; dado simulado sempre marcado.
- Cada mudança de comportamento tem teste e entrada no `CHANGELOG.md`.
- Nenhuma função de comando, proteção ou escrita em equipamento.
- Funcionalidade nova só entra se uma fase acima ou uma entrevista com cliente a justificar.

# Proposta de piloto — HITECH VoltGuard

> **Modelo.** Campos entre [colchetes] devem ser preenchidos. **Valores, prazos e cláusulas jurídicas precisam ser definidos por você e revisados por advogado antes do envio.** Não prometa resultados que não estejam medidos.

**Cliente:** [razão social]  **Site do piloto:** [endereço]  **Responsável do cliente:** [nome/cargo]
**HITECH:** [responsável]  **Data:** [data]  **Validade da proposta:** [30 dias]

## 1. Objetivo
Avaliar, durante [30/60/90] dias, se o monitoramento contínuo de [N] quadros elétricos e o fluxo alarme → ordem de serviço reduzem o tempo de detecção e de resposta a condições anormais, em comparação com a rotina atual.

## 2. O que será entregue
- Monitoramento de **temperatura e corrente** em [N] pontos: [lista dos quadros].
- Painel web, alarmes com limites acordados, ordens de serviço ligadas aos alarmes e histórico.
- Notificação de alarme por [webhook/e-mail/outro — definir].
- Usuários para [N] pessoas (papéis: gestor e técnico).
- Relatório de resultados ao final.
- Treinamento de [X] horas.

## 3. O que **não** faz parte
- Proteção elétrica, intertravamento, comando ou desligamento de equipamentos. O VoltGuard **apenas lê e informa**; não substitui relés de proteção, SCADA certificado nem o julgamento de profissional habilitado.
- Certificação, laudos ou conformidade normativa.
- Alterações no sistema elétrico do cliente além da instalação de sensores/gateway aprovada por responsável técnico.

## 4. Responsabilidades
| HITECH | Cliente |
|---|---|
| Configurar a plataforma e os alarmes | Indicar responsável e substituto para os alarmes |
| Fornecer [gateway/sensores — definir] | Permitir acesso físico e rede para o gateway |
| Dar suporte em [horário] | Registrar nas ordens de serviço o que for feito |
| Entregar relatório final | Fornecer dados da rotina atual (linha de base) |

Instalação elétrica: executada por [profissional habilitado — definir quem], com procedimentos de segurança do cliente.

## 5. Linha de base e critérios de sucesso (a preencher juntos **antes** de ligar)
| Indicador | Hoje (linha de base) | Meta do piloto | Como medir |
|---|---|---|---|
| Tempo entre a condição anormal e a detecção | [ ] | [ ] | Carimbo do alarme × registro do cliente |
| Tempo até o reconhecimento / até a ordem | [ ] | [ ] | Auditoria da plataforma |
| Inspeções manuais por mês | [ ] | [ ] | Registro do cliente |
| Alarmes sem ação ou falsos positivos | — | ≤ [ ]% | Classificação pelo técnico |
| Paradas relacionadas aos pontos monitorados | [ ] | [ ] | Registro do cliente |

O piloto é considerado bem-sucedido se [critério objetivo acordado, ex.: "pelo menos X dos Y indicadores atingirem a meta e a equipe operar o fluxo sem apoio da HITECH na última semana"].

## 6. Cronograma
| Etapa | Prazo |
|---|---|
| Levantamento e linha de base | [ ] |
| Instalação e validação dos dados | [ ] |
| Operação assistida | [ ] |
| Relatório e decisão | [ ] |

## 7. Condições comerciais
- Investimento do piloto: [valor] — inclui [itens]; hardware: [comprado pelo cliente / cedido / locado].
- Em caso de continuidade: assinatura de [valor ou faixa] por [site / faixa de ativos], mais implantação de [valor] por site adicional. [Definir após medir custo real de gateway, conectividade, suporte e instalação.]
- Condição de crédito: [ex.: o valor do piloto é abatido da implantação se houver contratação em até X dias].

## 8. Dados, privacidade e segurança
- Dados coletados: leituras elétricas, registros de ordens de serviço e dados de usuários necessários ao acesso ([nome, e-mail]).
- Finalidade: execução do piloto. Retenção: [prazo]; exclusão ou devolução ao final, a pedido.
- Papéis LGPD (controlador/operador), subprocessadores e medidas de segurança: [definir com advogado].
- Acessos à rede do cliente limitados ao gateway, somente leitura, em rede segmentada.

## 9. Limites do serviço
Disponibilidade, janelas de manutenção, canal e horário de suporte, e limites de responsabilidade: [definir com advogado]. Durante o piloto o serviço é oferecido **sem SLA** [ou: com SLA de X, conforme anexo].

## 10. Aceite
Cliente: ______________________  HITECH: ______________________  Data: ____/____/______

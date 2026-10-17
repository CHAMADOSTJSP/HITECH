# Checklist de implantação — Render

## Antes do deploy

- [ ] Repositório GitHub privado criado.
- [ ] Arquivos do pacote extraídos diretamente na raiz do repositório.
- [ ] `.env`, banco local e segredos reais não foram enviados ao Git.
- [ ] `render.yaml` revisado; planos/região/recursos confirmados no painel do Render.
- [ ] Dependências e testes locais executados em ambiente com as dependências de `requirements.txt` instaladas.

## Durante o deploy

- [ ] Blueprint criou serviço web e banco PostgreSQL.
- [ ] `SECRET_KEY` foi gerada pelo Render e está definida como variável secreta.
- [ ] `DATABASE_URL` aponta para o banco correto.
- [ ] Build e start terminaram sem erros.
- [ ] `/health` responde HTTP 200.

## Testes pós-deploy

- [ ] Criar organização de teste com senha de pelo menos 12 caracteres.
- [ ] Fazer login e sair.
- [ ] Confirmar que os painéis iniciais estão marcados como dados de demonstração.
- [ ] Testar leitura QR manual; testar câmera somente em navegador/ambiente com permissão.
- [ ] Criar ordem de serviço e alterar estado.
- [ ] Testar exportação CSV autenticada.
- [ ] Testar regra de alarme e validar os limites com dados simulados.
- [ ] Criar item de estoque, aumentar saldo e confirmar que ajuste negativo indevido é rejeitado.
- [ ] Criar duas organizações de teste e verificar que uma não consegue consultar o painel da outra.
- [ ] Confirmar que nenhum equipamento real ou função de comando/proteção está conectado.

## Antes de qualquer piloto com dados reais

- [ ] Plano PostgreSQL persistente escolhido e política de expiração confirmada.
- [ ] Backup e restauração testados.
- [ ] Revisão independente de segurança e testes de isolamento concluídos.
- [ ] Migrações de banco revisadas com backup.
- [ ] Política de privacidade, retenção, suporte e resposta a incidentes definida.
- [ ] Telemetria real validada em laboratório, com identidade por dispositivo e rede de aquisição isolada.

## Verificações adicionais (v0.39.0)

- [ ] `python -m unittest discover -s tests -v` passa localmente com as dependências instaladas.
- [ ] `TRUST_PROXY=1`: fazer 11 logins errados seguidos de dois IPs diferentes e confirmar que o bloqueio vale por IP, não para todos.
- [ ] Criar usuário Técnico de Campo; confirmar que não acessa abas de gestão e que `POST /api/telemetry` retorna 403.
- [ ] Desativar um usuário e confirmar que a sessão aberta dele recebe 401 na requisição seguinte.
- [ ] Adicionar um painel novo e confirmar que aparece "Sem dado" (nunca valores numéricos) até o primeiro envio do dispositivo.
- [ ] Configurar um webhook de teste (ex.: serviço de captura de requisições), enviar leitura acima do limite por um dispositivo e validar a assinatura `X-VoltGuard-Signature` com o segredo da aba de CEO.
- [ ] Confirmar que o painel `DEMO` não é usado em nenhuma demonstração com dados reais.

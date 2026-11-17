# Registros de Decisões de Arquitetura (ADR)
## Projeto: Monitor de Rastreamento de Encomendas Multi-Transportadora

Este documento consolida as principais Decisões de Arquitetura de Software (Architecture Decision Records) adotadas no desenvolvimento do sistema automatizado de monitoramento e notificação de encomendas.

---

### Índice de Decisões

- [ADR-001: Rastreamento Direto via APIs Reversas vs. Web Scraping / LinkeTrack](#adr-001-rastreamento-direto-via-apis-reversas-vs-web-scraping--linketrack)
- [ADR-002: Implementação Criptográfica Pura em Python (Zero-Dependency RSA) para a Anjun Express](#adr-002-implementação-criptográfica-pura-em-python-zero-dependency-rsa-para-a-anjun-express)
- [ADR-003: Persistência de Estado em Arquivo Texto Delimitado por Pipe (`pacotes.txt`)](#adr-003-persistência-de-estado-em-arquivo-texto-delimitado-por-pipe-pacotestxt)
- [ADR-004: Estratégia de Rastreamento da Última Milha Híbrida (Cainiao EDI + Anjun Express Brasil)](#adr-004-estratégia-de-rastreamento-da-última-milha-híbrida-cainiao-edi--anjun-express-brasil)
- [ADR-005: Política de Agendamento Dual (Notificação por Evento vs. Relatório Diário Matinal)](#adr-005-política-de-agendamento-dual-notificação-por-evento-vs-relatório-diário-matinal)
- [ADR-006: Cliente SMTP Agnóstico com Desacoplamento entre Usuário e Remetente (`EMAIL_FROM`)](#adr-006-cliente-smtp-agnóstico-com-desacoplamento-entre-usuário-e-remetente-email_from)

---

## ADR-001: Rastreamento Direto via APIs Reversas vs. Web Scraping / LinkeTrack

### Status
**Aprovado e Implementado**

### Contexto
O monitoramento de encomendas em compras online no Brasil enfrenta dois problemas históricos:
1. **Descontinuação de agregadores públicos**: Serviços terceiros como a API da LinkeTrack (`api.linketrack.com`) tornaram-se inoperantes ou passaram a exigir planos pagos instáveis.
2. **Bloqueios anti-bot e CAPTCHA**: Portais web oficiais (especialmente Correios com Cloudflare Turnstile CAPTCHA) bloqueiam requisições de scrapers convencionais (BeautifulSoup, Selenium, Puppeteer).
3. **Fragilidade de parsing HTML**: Mudanças de layout no front-end quebram seletores CSS e exigem manutenção frequente.

### Decisão
Optou-se por realizar a engenharia reversa das chamadas assíncronas (REST/JSON) utilizadas pelas plataformas oficiais web e mobile das próprias transportadoras:
- **Shopee (SPX)**: Consumo direto da API interna (`/api/v2/fleet_order/tracking/search`) replicando a assinatura SHA-256 com sal em base64.
- **AliExpress / Cainiao**: Consumo dos endpoints internos globais (`detail.json` e `getCity.json`).
- **Anjun Express**: Consumo da API do portal Nuxt (`/track/open/website/query`).

### Consequências
- **Positivas**:
  - Respostas JSON estruturadas, rápidas (< 1 segundo) e com consumo mínimo de banda e CPU.
  - Imunidade a alterações cosméticas de layout HTML/CSS.
  - Eliminação de custos e dependências de serviços terceiros intermediários.
- **Negativas / Mitigações**:
  - Se a transportadora alterar seus segredos criptográficos de assinatura ou rotas de API, é necessário atualizar a lógica do tracker correspondente.

---

## ADR-002: Implementação Criptográfica Pura em Python (Zero-Dependency RSA) para a Anjun Express

### Status
**Aprovado e Implementado**

### Contexto
A API oficial de rastreamento da Anjun Express exige um cabeçalho HTTP `token`, gerado a partir do horário de Pequim (UTC+8) criptografado com RSA (PKCS#1 v1.5) usando uma chave pública de 1024 bits.

No entanto:
- Em distribuições Linux recentes (Debian 12+, Ubuntu 23.04+), o **PEP 668** bloqueia o `pip install` global com o erro `error: externally-managed-environment`.
- Instalar pacotes criptográficos pesados como `cryptography` ou `pycryptodome` exige dependências de sistema C (OpenSSL, Rust, headers de compilação) ou rodas binárias (`wheels`), dificultando a portabilidade em servidores Linux mínimos e contêineres sem privilégios de root.

### Decisão
Implementar a criptografia RSA PKCS#1 v1.5 em **Python puro**, utilizando estritamente a biblioteca padrão:
- Exponenciação modular nativa `pow(m, e, n)`.
- Geração de padding aleatório seguro via `os.urandom`.
- Conversão de bytes com `int.from_bytes()` e `.to_bytes()`.
- Codificação Base64 com `base64.b64encode`.

### Consequências
- **Positivas**:
  - Zero dependências externas além do pacote `requests`.
  - Instalação e execução instantânea em qualquer ambiente Windows, macOS ou Linux sem erros de compilação ou conflitos com o PEP 668.
  - Desempenho de fração de milissegundo para chaves RSA de 1024 bits.
- **Negativas / Mitigações**:
  - Chave pública e parâmetros de algoritmo ficam codificados no módulo `trackers/anjun.py`. Caso a Anjun Express rotacione sua chave pública, a nova chave precisará ser inserida no código.

---

## ADR-003: Persistência de Estado em Arquivo Texto Delimitado por Pipe (`pacotes.txt`)

### Status
**Aprovado e Implementado**

### Contexto
Para identificar se houve mudança de status de um pacote a cada execução horária, o sistema precisa persistir o último estado conhecido (`ultimo_status`, `ultima_data_hora`, `localidade`).
Alternativas consideradas:
- Banco de dados relacional (SQLite, PostgreSQL).
- Arquivo JSON ou SQLite dedicado.
- Manter o estado no próprio arquivo de entrada do usuário.

### Decisão
Utilizar o próprio arquivo de configuração do usuário (`pacotes.txt`) como armazenamento de estado, empregando o formato delimitado por pipe (`|`):
```text
CODIGO | DESCRICAO | ULTIMO_STATUS | ULTIMA_DATA_HORA | LOCALIDADE
```
O script lê o arquivo, processa as encomendas e regrava preservando comentários (`#`) e compatibilidade retroativa com arquivos que contenham apenas `CODIGO DESCRICAO`.

### Consequências
- **Positivas**:
  - Arquivo único de configuração e estado, 100% legível e editável por humanos via Bloco de Notas, Nano, Vim ou VS Code.
  - Zero overhead de configuração, migrações de esquema ou dependências de drivers de banco.
  - Facilmente auditável e versionável.
- **Negativas / Mitigações**:
  - Concorrência de escrita não suportada (não há problema, pois o agendador executa em processo único sequencial).

---

## ADR-004: Estratégia de Rastreamento da Última Milha Híbrida (Cainiao EDI + Anjun Express Brasil)

### Status
**Aprovado e Implementado**

### Contexto
Pacotes comprados no AliExpress passam por transporte internacional pela Cainiao e, ao aterrissarem no Brasil, são transferidos para operadores logísticos locais para a "última milha" (last mile):
1. **Correios do Brasil**: O portal oficial de rastreamento dos Correios implementou proteção rígida por Cloudflare Turnstile CAPTCHA. Tentar contornar o CAPTCHA violaria políticas de conformidade, segurança e quebraria com frequência.
2. **Anjun Express**: A Anjun mantém um sistema próprio de entrega no Brasil com rastreamento detalhado de centros de distribuição (hubs) estaduais e municipais.

### Decisão
Implementar uma arquitetura de resolução híbrida e inteligente:
1. **Parceria Correios**: A Cainiao possui integração EDI direta de servidor para servidor com os Correios. Os eventos ocorridos nos Correios no Brasil são sincronizados e retornados pela API global da Cainiao, que além disso fornece o link oficial e telefone do parceiro. Não é necessário raspar o site dos Correios.
2. **Parceria Anjun Express**:
   - A Cainiao indica no campo `currentStatusCpInfo.cpName` quando a entrega é feita pela Anjun.
   - O módulo `cainiao.py` invoca automaticamente o módulo `anjun.py` para consultar a base nacional da Anjun Express.
   - Se a Anjun já possuir eventos mais recentes ou detalhados no Brasil, esses eventos enriquecidos assumem a liderança do relatório.
3. **Extração de Destino**: O endpoint `getCity.json` da Cainiao é consultado para antecipar a cidade brasileira final de entrega (ex: "Belo Horizonte").

### Consequências
- **Positivas**:
  - Respeito integral às diretrizes anti-bot dos Correios, sem tentativas de burlar CAPTCHA.
  - Rastreamento ponta a ponta: da China até a entrega na porta do cliente.
  - Identificação de localização em todas as fases do frete.

---

## ADR-005: Política de Agendamento Dual (Notificação por Evento vs. Relatório Diário Matinal)

### Status
**Aprovado e Implementado**

### Contexto
O monitor roda periodicamente (a cada hora). No entanto, o usuário:
- Deseja ser alertado por e-mail imediatamente se qualquer pacote tiver movimentação nova.
- Não quer receber e-mails a cada hora se nada se alterou (evitar fadiga de notificações e consumo de cota SMTP).
- Exige receber um resumo geral com o panorama de **todas** as encomendas pelo menos uma vez ao dia, logo no início da manhã (a partir das 08h), mesmo que nenhum pacote tenha mudado de status.

### Decisão
Implementar a regra de decisão no `main.py`:
1. O agendador do sistema operacional (Cron no Linux ou Agendador de Tarefas no Windows) executa o script a cada 60 minutos.
2. O script calcula o diff entre o status e data/hora atuais e os anteriores de cada pacote gravado em `pacotes.txt`.
3. Se houver `atualizado == True`, dispara imediatamente um e-mail com assunto `🔔 [Atualização] Status de Encomendas - DD/MM/AAAA às HH:MM`.
4. Se `hora >= 8` e a data de hoje ainda não estiver registrada no arquivo marcador oculto `.last_daily_report`:
   - Dispara o resumo geral com assunto `📦 [Relatório Diário] Status das Encomendas - DD/MM/AAAA às HH:MM`.
   - Grava a data no `.last_daily_report`.
5. Fora dessas duas condições, o script finaliza silenciosamente sem disparar e-mail.
6. Uma flag manual `--force` permite testar o envio a qualquer momento.

### Consequências
- **Positivas**:
  - Equilíbrio perfeito entre proatividade em eventos críticos e tranquilidade na caixa de entrada.
  - Garantia de auditoria diária matinal consistente.
  - Mecanismo resiliente a reinicializações de máquina através do arquivo marcador `.last_daily_report`.

---

## ADR-006: Cliente SMTP Agnóstico com Desacoplamento entre Usuário e Remetente (`EMAIL_FROM`)

### Status
**Aprovado e Implementado**

### Contexto
O envio de alertas deve funcionar tanto em contas pessoais (Gmail, Outlook, Yahoo) quanto em servidores corporativos de intranet (como relays SMTP internos com restrições de remetente).
Muitos servidores corporativos:
- Bloqueiam conexões para a internet (Gmail inacessível).
- Exigem STARTTLS na porta 587.
- Autenticam com uma credencial de serviço (ex: `usuario_servico`), mas rejeitam o envio (`553 5.7.1 Sender address rejected`) caso o cabeçalho `From:` não coincida com o e-mail autorizado (ex: `servico@empresa.gov.br`).

### Decisão
Criar o módulo [emailer.py](emailer.py) com parametrização completa via variáveis de ambiente:
- `EMAIL_HOST`: Endereço do servidor SMTP.
- `EMAIL_PORT`: Porta (padrão 587).
- `EMAIL_HOST_USER` e `EMAIL_HOST_PASSWORD`: Credenciais de autenticação (opcionais se o relay for autenticado por IP).
- `EMAIL_FROM`: Endereço exato a ser utilizado no cabeçalho `From:`.
- `EMAIL_DESTINATARIO`: E-mail de destino das notificações.
- `EMAIL_USE_TLS` e `EMAIL_USE_SSL`: Controle explícito do tipo de criptografia de transporte.

### Consequências
- **Positivas**:
  - Compatibilidade garantida com qualquer infraestrutura corporativa ou de nuvem.
  - Envio limpo em formato texto simples estruturado (`MIMEText(corpo, "plain", "utf-8")`), garantindo renderização perfeita em qualquer cliente de e-mail (web, desktop e mobile) sem filtros de spam por HTML malformado.
  - Inclusão automática de links clicáveis de rastreamento para conferência rápida pelo destinatário.

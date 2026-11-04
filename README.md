# Claudinho — Alexa + Claude

Skill Alexa (pt-BR) que envia o que você fala para o [Claude](https://www.anthropic.com/claude) e lê a resposta em voz alta.

```
Alexa, pergunte ao claudinho o que é um buraco negro
Alexa, pergunte ao claudinho          (abre a skill e espera a pergunta)
```

A skill lembra das últimas 6 trocas enquanto a sessão estiver aberta, então dá para fazer perguntas de continuação ("e por que isso acontece?").

## Estrutura

| Caminho | O que é |
|---|---|
| `skill.json` | Manifesto da skill (nome, locale, endpoints do Lambda hospedado) |
| `interactionModels/custom/pt-BR.json` | Modelo de interação: invocação `claudinho` e o `ChatIntent` |
| `lambda/lambda_function.py` | Código da skill (ASK SDK + Anthropic SDK) |
| `lambda/requirements.txt` | Dependências Python (`ask-sdk-core`, `anthropic`, `boto3`) |
| `lambda/anthropic_key.txt` | **Sua chave do Claude — não vem no repositório** (está no `.gitignore`) |

---

## 1. Criar a skill no console da Alexa

1. Acesse o [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) com a mesma conta Amazon do seu Echo.
2. Clique em **Create Skill**.
3. Preencha:
   - **Skill name:** `claudinho`
   - **Primary locale:** `Portuguese (BR)`
   - **Type of experience:** Other → **Custom**
   - **Hosting services:** **Alexa-hosted (Python)**
   - **Hosting region:** a que preferir (ex.: US East)
4. Em **Templates**, escolha **Start from Scratch** e clique em **Create Skill**. A criação leva cerca de 1 minuto.

## 2. Baixar o código-fonte

Escolha uma das opções:

- **Pelo console:** na aba **Code**, clique em **Download Skill** para baixar um `.zip` com `skill.json`, `interactionModels/` e `lambda/`.
- **Pelo ASK CLI:**
  ```bash
  npm install -g ask-cli
  ask configure
  ask init --hosted-skill-id <ID-da-skill>   # o ID aparece em "Copy Skill ID" na lista de skills
  ```
- **Deste repositório:**
  ```bash
  git clone https://github.com/Bravodin/claude-skill-alexa.git
  ```
  Neste caso, use o código daqui no lugar do template gerado no passo 1.

> **Importante:** o repositório **não traz a chave do Claude**. Depois de clonar, você precisa criar o arquivo `lambda/anthropic_key.txt` com a sua própria chave (passos 3 e 4). Sem ele, a Alexa responde *"A chave da API do Claude não está configurada corretamente."*

## 3. Obter a chave da API do Claude

1. Acesse o [Claude Console](https://console.anthropic.com/) e faça login.
2. Em **Billing**, adicione créditos. A API é paga por uso, separada da assinatura do Claude.ai.
3. Em **API Keys**, clique em **Create Key** e copie a chave (`sk-ant-...`). Ela só é mostrada uma vez.

> Nunca faça commit da chave. O arquivo `lambda/anthropic_key.txt` já está no `.gitignore`.

## 4. Integrar com o Claude (subir o código)

### Modelo de interação
1. No console da Alexa, aba **Build** → **Interaction Model** → **JSON Editor**.
2. Cole o conteúdo de `interactionModels/custom/pt-BR.json`.
3. Clique em **Save** e depois em **Build skill**.

### Código do Lambda
1. Aba **Code**.
2. Substitua `lambda/lambda_function.py` e `lambda/requirements.txt` pelos deste repositório.
3. Clique com o botão direito na pasta `lambda` → **Create File** → `lambda/anthropic_key.txt`.
4. Cole **só a chave** no arquivo, sem aspas e sem espaços.
5. Clique em **Save** e depois em **Deploy**. O primeiro deploy instala o pacote `anthropic` e leva um pouco mais.

> O código também aceita a chave pela variável de ambiente `ANTHROPIC_API_KEY`, mas skills Alexa-hosted não permitem configurar variáveis de ambiente. Por isso usamos o arquivo.

## 5. Testar

1. Aba **Test** → mude de *Off* para **Development**.
2. Digite ou fale:
   - `pergunte ao claudinho qual a capital da Austrália`
   - `pergunte ao claudinho` → depois `me explica como funciona um arco-íris`
3. Com a skill em *Development*, ela já funciona em qualquer Echo logado na mesma conta Amazon.

### Como fazer perguntas

A pergunta precisa começar com uma das frases do `ChatIntent`, por exemplo: *me diga, me explica, me conta, quero saber, o que é, qual, quem, quando, onde, como, por que, quanto*. Para aceitar outras formas, acrescente amostras em `interactionModels/custom/pt-BR.json`.

## Configuração

No topo de `lambda/lambda_function.py`:

| Constante | Padrão | Para quê |
|---|---|---|
| `MODEL` | `claude-haiku-5-5` | Modelo usado. Rápido e barato, bom para voz. Veja [Custos](#custos-e-billing) antes de trocar. |
| `CLAUDE_TIMEOUT_SECONDS` | `7.0` | A Alexa espera cerca de 8s pela resposta. |
| `MAX_TURNS` | `6` | Trocas guardadas na sessão antes de recomeçar a conversa. |
| `SYSTEM_PROMPT` | — | Personalidade e estilo das respostas (curtas, sem markdown). |

## Custos e billing

A skill é paga com os **créditos da API** do [Claude Console](https://console.anthropic.com/), e não com a assinatura do Claude.ai.

| | Assinatura Claude.ai (Pro/Max) | Créditos da API (Console) |
|---|---|---|
| Para que serve | Site, app e Claude Code com login da conta | Chamadas feitas com a chave `sk-ant-...` |
| Usado por esta skill? | **Não** | **Sim** |
| Cobrança | Mensal, fixa | Pré-paga, por token, em dólar |

### Quanto custa cada pergunta

São valores aproximados: o custo varia com o tamanho da resposta e com o histórico da conversa, que é reenviado a cada pergunta.

| Modelo | Preço (entrada / saída por 1M tokens) | Por pergunta | Com ~US$2,70 (≈ R$15) |
|---|---|---|---|
| `claude-haiku-5-5` (padrão) | US$0,10 / US$0,50 | ~US$0,0005 | vários milhares de perguntas |
| `claude-sonnet-5-5` | US$2 / US$10 | ~US$0,007 | ~400 perguntas |
| `claude-opus-5-5` | US$4 / US$20 | ~US$0,01 a 0,02 | ~150 a 250 perguntas |

Modelos maiores também demoram mais e podem estourar o limite de ~8s da Alexa.

### Acompanhar e limitar o gasto

- **Usage** e **Billing** no Console mostram o consumo e o saldo.
- Em **Settings → Limits**, defina um limite de gasto mensal para evitar surpresas.
- Sem créditos, a API retorna erro e a Alexa diz *"Tive um problema ao falar com o Claude."*

## Problemas comuns

| A Alexa diz… | Causa provável |
|---|---|
| "A chave da API do Claude não está configurada corretamente." | `lambda/anthropic_key.txt` está faltando, vazio ou com a chave errada. |
| "O Claude demorou demais para responder." | A resposta passou dos 7s. Faça uma pergunta mais curta. |
| "Não entendi…" | A frase não bateu com nenhuma amostra do `ChatIntent`. Comece com "me diga", "o que é" etc. |
| "Tive um problema ao falar com o Claude." | Erro da API (ex.: sem créditos). Veja os logs em **Code → CloudWatch Logs**. |

## Melhorias futuras (TODO)

- **Enviar por email o resumo da conversa** ("me manda por email o resumo"). Detalhes no `# TODO` em `lambda/lambda_function.py`:
  - ferramenta `enviar_email` para o Claude;
  - envio pelo Gmail com senha de app;
  - histórico guardado no S3 para resumir sessões anteriores.

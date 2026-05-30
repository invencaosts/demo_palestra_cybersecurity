# CyberDemo — Demo de Detecção de Ameaças com IA

Sistema de demonstração ao vivo que simula um SOC (Security Operations Center) com detecção de ataques em tempo real usando **Qwen rodando localmente via LM Studio** como motor de inteligência artificial.

## Visão Geral

O projeto é composto por três serviços independentes:

| Serviço | Arquivo | Porta | Descrição |
|---|---|---|---|
| API (backend) | `api.py` | 8000 | Gera logs, gerencia estado e expõe endpoints de simulação |
| Dashboard | `dashboard.py` | 8501 | Tela do projetor — exibe logs, gráfico e alertas em tempo real |
| Controle | `controle.py` | 8502 | Painel do apresentador — acessado pelo celular |

A IA (Qwen via LM Studio) analisa os logs a cada ciclo, classifica o padrão e aciona automaticamente o estado de alerta no dashboard sem nenhuma regra hardcoded.

## Pré-requisitos

- Python 3.10+
- [LM Studio](https://lmstudio.ai) instalado
- Modelo Qwen baixado e carregado no LM Studio

## Instalação

### 1. Configurar o LM Studio

1. Baixe e instale o [LM Studio](https://lmstudio.ai)
2. Na aba **Discover**, pesquise por `Qwen2.5` e baixe o modelo desejado (ex: `Qwen2.5-7B-Instruct`)
3. Vá em **Local Server** (ícone `<->` na barra lateral) e clique em **Start Server**
4. Selecione o modelo Qwen carregado na lista do servidor

> O LM Studio expõe o servidor local em `http://localhost:1234` por padrão.

### 2. Instalar dependências Python

```bash
pip install -r requirements.txt
```

## Configuração

Não é necessária nenhuma variável de ambiente para começar — o modelo padrão é `qwen2.5-7b-instruct` e o endpoint é `http://localhost:1234/v1`. As variáveis opcionais são:

```bash
# Trocar o identificador do modelo (opcional — o nome deve bater com o exibido no LM Studio)
export QWEN_MODEL="qwen2.5-14b-instruct"

# Trocar o endpoint do LM Studio se estiver em outra máquina (opcional)
export LMSTUDIO_BASE_URL="http://outra-maquina:1234/v1"

# Trocar o endpoint da API se os serviços rodarem em máquinas diferentes (opcional)
export API_URL="http://outra-maquina:8000"
```

> O modelo também pode ser alterado pelo painel de controle durante a apresentação, sem reiniciar os serviços.

## Execução

Primeiro, certifique-se de que o **LM Studio está com o servidor local iniciado** e o modelo Qwen carregado.

Depois, abra três terminais e execute um serviço em cada:

```bash
# Terminal 1 — API
python api.py

# Terminal 2 — Dashboard (projetor)
streamlit run dashboard.py --server.port 8501

# Terminal 3 — Controle (celular)
streamlit run controle.py --server.port 8502
```

Acesse no celular via `http://<IP_DA_MAQUINA>:8502`. Para descobrir o IP:

```bash
# Linux / Mac
hostname -I

# Windows
ipconfig | findstr "IPv4"
```

O celular e o notebook precisam estar na mesma rede Wi-Fi.

## Fluxo da Demonstração

### Fluxo 1 — Ataque Detectado
1. Abra o dashboard no projetor — logs chegando, gráfico em movimento, badge "Monitorando..."
2. No celular, clique **"💣 SIMULAR ATAQUE"**
3. A API injeta 50 logs de força bruta do IP `185.220.101.45`
4. O Qwen detecta o padrão e chama `/set-state` automaticamente
5. Dashboard exibe overlay vermelho piscando com o IP bloqueado

### Reset entre fluxos
Clique **"🔄 RESETAR SISTEMA"** no celular — overlay desaparece, logs voltam ao normal.

### Fluxo 2 — Falso Positivo
1. Clique **"👤 SIMULAR FALSO POSITIVO"** — aguarde ~6 segundos
2. A API injeta 3 tentativas esparsas (2s de intervalo entre cada uma) do IP `192.168.1.10`
3. O Qwen classifica como `FALSO_POSITIVO` por detectar comportamento humano
4. Overlay laranja aparece destacando que o sistema distingue bots de humanos

## Arquitetura da IA

O dashboard chama o Qwen a cada 15 segundos em estado normal ou imediatamente se detectar mais de 8 logs novos em um ciclo (indicativo de ataque). O prompt usa few-shot learning com exemplos de cada categoria:

- **ATAQUE** — mesmo IP com 10+ requisições consecutivas para endpoints sensíveis (`/admin/login`) com status 401
- **FALSO_POSITIVO** — mesmo IP com 2–5 tentativas espaçadas para `/login` com comportamento humano
- **NORMAL** — IPs variados, métodos e endpoints diversos, sem concentração de erros

A IA retorna JSON estruturado e, ao detectar ameaça, aciona diretamente o endpoint `/set-state` da API.

### Como funciona a integração com LM Studio

O `dashboard.py` usa o SDK `openai` apontado para o servidor local do LM Studio (`http://localhost:1234/v1`), que expõe uma API compatível com o formato OpenAI. O LM Studio não exige chave de API — o campo é preenchido com `"lm-studio"` apenas para satisfazer o SDK. O modelo roda inteiramente offline, sem nenhuma requisição saindo da sua máquina.

```
dashboard.py  →  openai SDK  →  http://localhost:1234/v1  →  LM Studio  →  Qwen
```

## Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/logs` | Últimos 50 logs |
| GET | `/status` | Estado atual do sistema |
| GET | `/attack` | Injeta 50 logs de força bruta |
| GET | `/false-positive` | Injeta 3 tentativas humanas (demora ~6s) |
| GET | `/reset` | Limpa logs e reseta estado |
| GET | `/set-state` | Atualiza estado (usado pela IA) |
| GET | `/set-qwen-model` | Salva nome do modelo em memória |
| GET | `/get-qwen-model` | Retorna modelo ativo |
| GET | `/docs` | Documentação interativa (Swagger) |

## Solução de Problemas

### Porta já em uso
```bash
# Linux / Mac
lsof -ti:8000 | xargs kill -9
lsof -ti:8501 | xargs kill -9
lsof -ti:8502 | xargs kill -9

# Windows
netstat -ano | findstr :8000
Stop-Process -Id <PID> -Force
```

### Celular não acessa a API
Libere as portas no firewall:
```bash
# Linux (firewalld)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --add-port=8501/tcp --permanent
sudo firewall-cmd --add-port=8502/tcp --permanent
sudo firewall-cmd --reload
```

### Erros do LM Studio / Qwen

| Mensagem | Solução |
|---|---|
| `Connection refused` | Verifique se o servidor local do LM Studio está iniciado |
| `model not found` | Confirme que o nome do modelo no painel de controle bate com o carregado no LM Studio |
| Resposta lenta | Use um modelo menor (`Qwen2.5-3B`) ou ative aceleração de GPU no LM Studio |
| JSON inválido na resposta | Tente um modelo maior (`Qwen2.5-14B`) para mais precisão |

## Dependências

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
streamlit==1.41.1
requests>=2.32.3
openai>=1.0.0
altair<5.4.0
```

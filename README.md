# CyberDemo — Demo de Detecção de Ameaças com IA

Sistema de demonstração ao vivo que simula um SOC (Security Operations Center) com detecção de ataques em tempo real usando Google Gemini como motor de inteligência artificial.

## Visão Geral

O projeto é composto por três serviços independentes:

| Serviço | Arquivo | Porta | Descrição |
|---|---|---|---|
| API (backend) | `api.py` | 8000 | Gera logs, gerencia estado e expõe endpoints de simulação |
| Dashboard | `dashboard.py` | 8501 | Tela do projetor — exibe logs, gráfico e alertas em tempo real |
| Controle | `controle.py` | 8502 | Painel do apresentador — acessado pelo celular |

A IA (Gemini) analisa os logs a cada ciclo, classifica o padrão e aciona automaticamente o estado de alerta no dashboard sem nenhuma regra hardcoded.

## Pré-requisitos

- Python 3.10+
- Chave de API do Google Gemini ([aigenai.google.dev](https://aistudio.google.com/app/apikey))

## Instalação

```bash
pip install -r requirements.txt
```

## Configuração

Exporte sua chave do Gemini antes de iniciar os serviços:

```bash
# Linux / Mac
export GEMINI_API_KEY="sua-chave-aqui"

# Windows (PowerShell)
$env:GEMINI_API_KEY = "sua-chave-aqui"
```

> A chave também pode ser inserida pelo painel de controle durante a apresentação, sem necessidade de reiniciar os serviços.

A variável `API_URL` é opcional (padrão: `http://localhost:8000`). Defina-a no terminal do `controle.py` se os serviços rodarem em máquinas diferentes.

## Execução

Abra três terminais e execute um serviço em cada:

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
4. O Gemini detecta o padrão e chama `/set-state` automaticamente
5. Dashboard exibe overlay vermelho piscando com o IP bloqueado

### Reset entre fluxos
Clique **"🔄 RESETAR SISTEMA"** no celular — overlay desaparece, logs voltam ao normal.

### Fluxo 2 — Falso Positivo
1. Clique **"👤 SIMULAR FALSO POSITIVO"** — aguarde ~6 segundos
2. A API injeta 3 tentativas esparsas (2s de intervalo entre cada uma) do IP `192.168.1.10`
3. O Gemini classifica como `FALSO_POSITIVO` por detectar comportamento humano
4. Overlay laranja aparece destacando que o sistema distingue bots de humanos

## Arquitetura da IA

O dashboard chama o Gemini a cada 15 segundos em estado normal ou imediatamente se detectar mais de 8 logs novos em um ciclo (indicativo de ataque). O prompt usa few-shot learning com exemplos de cada categoria:

- **ATAQUE** — mesmo IP com 10+ requisições consecutivas para endpoints sensíveis (`/admin/login`) com status 401
- **FALSO_POSITIVO** — mesmo IP com 2–5 tentativas espaçadas para `/login` com comportamento humano
- **NORMAL** — IPs variados, métodos e endpoints diversos, sem concentração de erros

A IA retorna JSON estruturado e, ao detectar ameaça, aciona diretamente o endpoint `/set-state` da API.

## Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/logs` | Últimos 50 logs |
| GET | `/status` | Estado atual do sistema |
| GET | `/attack` | Injeta 50 logs de força bruta |
| GET | `/false-positive` | Injeta 3 tentativas humanas (demora ~6s) |
| GET | `/reset` | Limpa logs e reseta estado |
| GET | `/set-state` | Atualiza estado (usado pela IA) |
| GET | `/set-gemini-key` | Salva chave do Gemini em memória |
| GET | `/get-gemini-key` | Retorna chave salva |
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

### Erros do Gemini

| Mensagem | Solução |
|---|---|
| `429 quota exceeded` | Aguarde o reset diário ou ative billing no Google Cloud |
| `API_KEY_INVALID` | Verifique se a chave foi copiada sem espaços extras |
| `model not found` | O modelo usado é `gemini-1.5-flash` — confirme acesso na sua chave |
| Timeout | Verifique conexão com a internet |

> O plano gratuito tem limite diário de requisições. O dashboard chama a IA a cada 15 segundos em estado normal — use com moderação antes da apresentação.

## Dependências

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
streamlit==1.41.1
requests>=2.32.3
google-generativeai==0.8.3
altair<5.4.0
```

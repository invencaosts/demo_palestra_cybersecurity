# Como Rodar a Demo de Cibersegurança

## 1. Configurar o LM Studio

1. Baixe e instale o [LM Studio](https://lmstudio.ai)
2. Na aba **Discover**, pesquise por `Qwen2.5` e baixe o modelo desejado
   - Recomendado: `Qwen2.5-7B-Instruct` (bom equilíbrio entre velocidade e qualidade)
   - Máquinas com pouca RAM: `Qwen2.5-3B-Instruct`
   - Mais precisão: `Qwen2.5-14B-Instruct`
3. Vá em **Local Server** (ícone `<->` na barra lateral)
4. Selecione o modelo Qwen na lista e clique em **Start Server**

O servidor sobe em `http://localhost:1234` por padrão.

---

## 2. Instalar dependências Python

```bash
pip install -r requirements.txt
```

---

## 3. Variáveis de ambiente (todas opcionais)

| Variável | Padrão | Uso |
|---|---|---|
| `QWEN_MODEL` | `qwen2.5-7b-instruct` | Identificador do modelo carregado no LM Studio |
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | LM Studio em outra máquina |
| `API_URL` | `http://localhost:8000` | API em outra máquina |

**Mac / Linux**
```bash
export QWEN_MODEL="qwen2.5-14b-instruct"
```

**Windows (PowerShell)**
```powershell
$env:QWEN_MODEL = "qwen2.5-14b-instruct"
```

> O modelo também pode ser alterado diretamente pelo painel de controle durante a apresentação, sem reiniciar os serviços.

---

## 4. Rodar os 3 servidores (um terminal cada)

**Terminal 1 — API (backend)**
```bash
python api.py
```
Aguarde: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 — Dashboard (tela do projetor)**
```bash
streamlit run dashboard.py --server.port 8501
```
Acesse: http://localhost:8501

**Terminal 3 — Controle (celular do apresentador)**
```bash
streamlit run controle.py --server.port 8502
```
Acesse pelo celular: http://IP_DA_MAQUINA:8502

---

## 5. Descobrir o IP da máquina

**Mac / Linux**
```bash
ip a | grep "inet " | grep -v 127.0.0.1
# ou
hostname -I
```

**Windows**
```powershell
ipconfig | findstr "IPv4"
```

O celular e o notebook precisam estar na **mesma rede Wi-Fi**.

---

## 6. Ordem da demonstração ao vivo

### Fluxo 1 — Ataque detectado
1. Abra o dashboard no projetor — logs chegando, gráfico se movendo, badge "🤖 IA: Monitorando..."
2. No celular, acesse http://IP_DA_MAQUINA:8502 e clique **"💣 SIMULAR ATAQUE"**
3. A API injeta 50 logs de força bruta. O Qwen detecta e chama `/set-state`
4. O dashboard exibe o overlay vermelho piscando com IP bloqueado
5. Explique para a plateia que foi a IA quem tomou a decisão, não uma regra hardcoded

### Reset entre fluxos
- No celular, clique **"🔄 RESETAR SISTEMA"**
- O overlay desaparece, logs voltam ao normal

### Fluxo 2 — Falso positivo
1. Explique o conceito de falso positivo para a plateia
2. Clique **"👤 SIMULAR FALSO POSITIVO"** — aguarde ~6 segundos
3. O Qwen analisa as 3 tentativas esparsas e classifica como FALSO_POSITIVO
4. Overlay laranja aparece com a mensagem sobre comportamento humano
5. Demonstre que o sistema distingue bots de humanos

---

## 7. Se der erro

### Porta já em uso
```bash
# Linux / Mac
lsof -ti:8000 | xargs kill -9
lsof -ti:8501 | xargs kill -9
lsof -ti:8502 | xargs kill -9
```
```powershell
# Windows
netstat -ano | findstr :8000
Stop-Process -Id <PID> -Force
```

### Celular não acessa a API
- Confirme que celular e notebook estão na mesma rede Wi-Fi
- Libere as portas no firewall:
```bash
# Linux (firewalld)
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --add-port=8501/tcp --permanent
sudo firewall-cmd --add-port=8502/tcp --permanent
sudo firewall-cmd --reload
```

### LM Studio / Qwen com problema

| Mensagem | Solução |
|---|---|
| `Connection refused` | Verifique se o servidor local do LM Studio está iniciado |
| `model not found` | Confirme que o identificador do modelo no painel bate com o carregado no LM Studio |
| Resposta muito lenta | Use `Qwen2.5-3B` ou ative aceleração de GPU nas configurações do LM Studio |
| JSON inválido na resposta | Use um modelo maior (`Qwen2.5-14B`) para mais precisão |

---

| Serviço     | URL                        |
|-------------|----------------------------|
| API         | http://localhost:8000      |
| Docs da API | http://localhost:8000/docs |
| Dashboard   | http://localhost:8501      |
| Controle    | http://localhost:8502      |

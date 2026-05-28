# Como Rodar a Demo de Cibersegurança

## 1. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 2. Definir variáveis de ambiente

**Mac / Linux**
```bash
export GEMINI_API_KEY="sua-chave-aqui"
```

**Windows (PowerShell)**
```powershell
$env:GEMINI_API_KEY = "sua-chave-aqui"
```

A chave do Gemini é **obrigatória** para o núcleo do sistema funcionar — é a IA quem decide se há ataque ou não. Sem ela, o dashboard monitora os logs mas não aciona alertas.

A variável `API_URL` é opcional (padrão: `http://localhost:8000`). Defina-a no terminal do `controle.py` se rodar em máquina diferente da API.

---

## 3. Rodar os 3 servidores (um terminal cada)

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

## 4. Descobrir o IP da máquina

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

## 5. Ordem da demonstração ao vivo

### Fluxo 1 — Ataque detectado
1. Abra o dashboard no projetor — logs chegando, gráfico se movendo, badge "🤖 IA: Monitorando..."
2. No celular, acesse http://IP_DA_MAQUINA:8502 e clique **"💣 SIMULAR ATAQUE"**
3. A API injeta 50 logs de força bruta. O Gemini detecta e chama `/set-state`
4. O dashboard exibe o overlay vermelho piscando com IP bloqueado
5. Explique para a plateia que foi a IA quem tomou a decisão, não uma regra hardcoded

### Reset entre fluxos
- No celular, clique **"🔄 RESETAR SISTEMA"**
- O overlay desaparece, logs voltam ao normal

### Fluxo 2 — Falso positivo
1. Explique o conceito de falso positivo para a plateia
2. Clique **"👤 SIMULAR FALSO POSITIVO"** — aguarde ~6 segundos
3. O Gemini analisa os 3 tentativas esparsas e (idealmente) classifica como FALSO_POSITIVO
4. Overlay laranja aparece com a mensagem sobre comportamento humano
5. Demonstre que o sistema distingue bots de humanos

---

## 6. Se der erro

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

### Gemini retornando erro de cota (429)
O plano gratuito tem limite de requisições por dia. O dashboard chama a IA a cada 4 segundos em estado normal — use com moderação antes da apresentação.

| Mensagem              | Solução                                                        |
|-----------------------|----------------------------------------------------------------|
| `429 quota exceeded`  | Aguarde reset diário ou ative billing no Google Cloud          |
| `API_KEY_INVALID`     | Verifique se a chave foi copiada sem espaços extras            |
| `model not found`     | O modelo é `gemini-2.5-flash` — confirme acesso na sua chave  |
| Timeout               | Verifique conexão com a internet                               |

---

| Serviço     | URL                        |
|-------------|----------------------------|
| API         | http://localhost:8000      |
| Docs da API | http://localhost:8000/docs |
| Dashboard   | http://localhost:8501      |
| Controle    | http://localhost:8502      |

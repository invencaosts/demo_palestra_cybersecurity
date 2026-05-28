# dependencies: streamlit requests google-generativeai

import os
import re
import time
import json

import requests
import streamlit as st

API_BASE = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(layout="wide", page_title="SOC - Centro de Operações")

st.markdown("""
<style>
.stApp { background-color: #0d1117; color: #c9d1d9; }
.stApp header { background-color: #0d1117; }
@keyframes pulse {
    0%, 100% { opacity: 0.95; }
    50%       { opacity: 0.72; }
}
</style>
""", unsafe_allow_html=True)

# ── session state ────────────────────────────────────────────────────────────
for key, default in [
    ("requests_per_second", []),
    ("last_gemini_call",    0.0),
    ("gemini_result",       "Monitorando..."),
    ("last_log_count",      0),
    ("last_tick",           time.time()),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── helpers ──────────────────────────────────────────────────────────────────
def fetch_logs() -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/logs", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def fetch_status() -> dict:
    try:
        r = requests.get(f"{API_BASE}/status", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {"estado": "NORMAL", "ip_bloqueado": None, "mensagem": ""}


def get_gemini_key() -> str:
    """Tenta env var primeiro, depois busca da API (definida pelo controle.py)."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        r = requests.get(f"{API_BASE}/get-gemini-key", timeout=2)
        return r.json().get("key", "")
    except Exception:
        return ""


# ── PROMPT COM TREINAMENTO (few-shot) ────────────────────────────────────────
SYSTEM_PROMPT = """Você é um sistema especialista em detecção de ameaças cibernéticas.
Analise os logs de acesso abaixo e classifique o padrão observado.

REGRAS DE CLASSIFICAÇÃO:

1. ATAQUE — indique quando observar:
   - Mesmo IP com 10 ou mais requisições consecutivas em menos de 60 segundos
   - Múltiplas tentativas de acesso a endpoints sensíveis como /admin/login com status 401
   - Volume anômalo de requisições POST com falha vindo de um único IP externo
   Exemplo de padrão de ATAQUE:
   [{"ip":"185.220.101.45","method":"POST","endpoint":"/admin/login","status_code":401},
    {"ip":"185.220.101.45","method":"POST","endpoint":"/admin/login","status_code":401},
    ... (repetido 10+ vezes em segundos)]

2. FALSO_POSITIVO — indique quando observar:
   - Mesmo IP com apenas 2 a 5 tentativas de login com status 401
   - Intervalo de tempo lento entre as tentativas (comportamento humano, não robótico)
   - Endpoint /login (não /admin/login) com poucas tentativas
   Exemplo de padrão de FALSO_POSITIVO:
   [{"ip":"192.168.1.10","method":"POST","endpoint":"/login","status_code":401},
    (pausa de ~2s)
    {"ip":"192.168.1.10","method":"POST","endpoint":"/login","status_code":401},
    (pausa de ~2s)
    {"ip":"192.168.1.10","method":"POST","endpoint":"/login","status_code":401}]

3. NORMAL — indique quando observar:
   - IPs variados fazendo requisições diversas
   - Mix de métodos GET/POST em endpoints comuns
   - Sem concentração de erros num único IP

Responda APENAS com JSON no formato exato (sem markdown, sem texto extra):
{"veredicto": "NORMAL" | "ATAQUE" | "FALSO_POSITIVO", "ip": "IP suspeito ou null", "motivo": "uma frase curta em português"}
"""


def analisar_com_gemini(logs: list[dict], api_key: str) -> str:
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=SYSTEM_PROMPT,
        )

        payload = json.dumps(logs[-15:], ensure_ascii=False, indent=2)
        prompt  = f"Analise estes logs e classifique:\n{payload}"

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Remove possíveis blocos markdown que o modelo insira mesmo assim
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*",     "", text)
        text = text.strip()

        result   = json.loads(text)
        veredicto = result.get("veredicto", "NORMAL")
        ip        = result.get("ip") or ""
        motivo    = result.get("motivo", "")

        # IA aciona o alerta diretamente
        if veredicto in ("ATAQUE", "FALSO_POSITIVO"):
            try:
                requests.get(
                    f"{API_BASE}/set-state",
                    params={"estado": veredicto, "ip": ip, "mensagem": motivo},
                    timeout=3,
                )
            except Exception:
                pass

        return veredicto

    except json.JSONDecodeError:
        # Gemini às vezes retorna texto livre; tenta extrair a palavra-chave
        text_upper = response.text.upper() if 'response' in dir() else ""
        if "ATAQUE" in text_upper:
            return "ATAQUE"
        if "FALSO" in text_upper:
            return "FALSO_POSITIVO"
        return "NORMAL"

    except Exception as exc:
        return f"Erro: {exc}"


# ── dados ────────────────────────────────────────────────────────────────────
logs   = fetch_logs()
status = fetch_status()
estado      = status.get("estado", "NORMAL")
ip_bloqueado = status.get("ip_bloqueado") or "—"

now               = time.time()
current_log_count = len(logs)
new_logs_delta    = max(current_log_count - st.session_state.last_log_count, 0)
elapsed           = max(now - st.session_state.last_tick, 0.001)
elapsed_gemini    = now - st.session_state.last_gemini_call

# req/s
rps = round(new_logs_delta / elapsed, 2)
st.session_state.requests_per_second.append({"req/s": rps})
if len(st.session_state.requests_per_second) > 60:
    st.session_state.requests_per_second = st.session_state.requests_per_second[-60:]
st.session_state.last_log_count = current_log_count
st.session_state.last_tick      = now

# ── Gemini — núcleo do sistema ────────────────────────────────────────────────
gemini_key = get_gemini_key()

# Chama imediatamente se chegaram muitos logs novos (ataque) ou a cada 4s no normal
should_call = (
    gemini_key
    and estado == "NORMAL"
    and (elapsed_gemini >= 15 or new_logs_delta > 8)
)
if should_call:
    st.session_state.gemini_result = analisar_com_gemini(logs, gemini_key)
    st.session_state.last_gemini_call = now

# ── overlay fullscreen ───────────────────────────────────────────────────────
if estado == "ATAQUE":
    bg    = "rgba(180,0,0,0.88)"
    titulo = "🚨 ATAQUE DETECTADO"
    corpo  = (
        f"IP {ip_bloqueado} BLOQUEADO<br><br>"
        "⚠️ Notificando equipe de Cibersegurança sobre possível ataque.<br>"
        "Fluxo 1 finalizado."
    )
elif estado == "FALSO_POSITIVO":
    bg    = "rgba(160,60,0,0.88)"
    titulo = "⚠️ ANOMALIA DETECTADA"
    corpo  = (
        f"IP {ip_bloqueado} BLOQUEADO<br><br>"
        "⚠️ Notificando equipe de Cibersegurança.<br>"
        "ATENÇÃO: Possível Falso Positivo — IA identificou padrão suspeito<br>"
        "mas comportamento pode ser humano."
    )
else:
    bg = None

if bg:
    st.markdown(f"""
<div style="
    position: fixed;
    top: 0; left: 0;
    width: 100vw; height: 100vh;
    background: {bg};
    animation: pulse 1s ease-in-out infinite;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 40px;
    box-sizing: border-box;
">
  <div style="font-size:3.2rem;font-weight:800;color:#fff;
              text-shadow:0 2px 16px rgba(0,0,0,0.7);line-height:1.2;">
    {titulo}
  </div>
  <div style="font-size:1.3rem;color:#ffe8e8;margin-top:28px;line-height:2;">
    {corpo}
  </div>
</div>
""", unsafe_allow_html=True)

# ── conteúdo principal ────────────────────────────────────────────────────────
st.markdown(
    "<h2 style='color:#58a6ff;margin-bottom:4px;'>🛡️ Centro de Operações de Segurança</h2>",
    unsafe_allow_html=True,
)

col_chart, col_badge = st.columns([4, 1])

with col_chart:
    st.subheader("Requisições por Segundo")
    st.line_chart(st.session_state.requests_per_second, height=200)

with col_badge:
    st.subheader("Análise da IA")
    result = st.session_state.gemini_result
    if "ATAQUE" in result:
        st.error(f"🤖 {result}")
    elif "FALSO_POSITIVO" in result:
        st.warning(f"🤖 {result}")
    elif result.startswith("Erro"):
        st.warning(f"🤖 {result}")
    else:
        st.info("🤖 Monitorando...")

    if not gemini_key:
        st.caption("⚠️ IA desativada\nDefina a chave no painel de controle")

st.divider()

# ── tabela de logs ────────────────────────────────────────────────────────────
st.subheader("Últimos Logs")
if logs:
    display = []
    for row in reversed(logs[-50:]):
        tipo = row.get("tipo", "normal")
        if tipo == "ataque":
            ip_cell = f"🔴 {row['ip']}"
        elif tipo == "falso_positivo":
            ip_cell = f"🟡 {row['ip']}"
        else:
            ip_cell = row["ip"]
        display.append({
            "Timestamp":  row["timestamp"][11:19],
            "IP":         ip_cell,
            "Método":     row["method"],
            "Endpoint":   row["endpoint"],
            "Status":     row["status_code"],
            "Resp (ms)":  row["response_time_ms"],
        })
    st.dataframe(display, use_container_width=True, height=380)
else:
    st.info("Nenhum log ainda. A API está rodando em localhost:8000?")

time.sleep(2)
st.rerun()
# dependencies: streamlit requests openai

import os
import re
import time
import json
import threading

import requests
import streamlit as st

API_BASE = os.environ.get("API_URL", "http://localhost:8000")

# Estado global do thread de IA — compartilhado entre todos os reruns/sessões do Streamlit.
# st.session_state não é confiável em threads de background (missing ScriptRunContext).
_ai_lock  = threading.Lock()
_ai_state: dict = {
    "running":   False,
    "result":    None,
    "last_call": time.time(),  # compartilhado entre todas as sessões/abas
}

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
    ("qwen_result",         "Monitorando..."),
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


def get_qwen_model() -> str:
    """Tenta env var primeiro, depois busca da API (definida pelo controle.py)."""
    model = os.environ.get("QWEN_MODEL", "")
    if model:
        return model
    try:
        r = requests.get(f"{API_BASE}/get-qwen-model", timeout=2)
        return r.json().get("model", "qwen/qwen3-4b-thinking-2507")
    except Exception:
        return "qwen/qwen3-4b-thinking-2507"


def get_lmstudio_base_url() -> str:
    return os.environ.get("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")


# ── PROMPT OBJETIVO (evita raciocínio excessivo no modelo Thinking) ──────────
SYSTEM_PROMPT = """Classifique os logs de acesso como ATAQUE, FALSO_POSITIVO ou NORMAL.

ATAQUE: mesmo IP fez 3+ requisições POST em /admin/login com status 401 em sequência (timestamps próximos = comportamento de bot).
FALSO_POSITIVO: mesmo IP fez tentativas em /login (não /admin/login) com pausas longas entre elas (intervalo >1s = comportamento humano).
NORMAL: IPs variados, endpoints diversos, sem concentração de falhas num único IP.

Responda SOMENTE com este JSON (sem markdown, sem explicação):
{"veredicto": "NORMAL" | "ATAQUE" | "FALSO_POSITIVO", "ip": "IP suspeito ou null", "motivo": "frase curta em português"}
"""


def _extract_json_verdict(content: str) -> dict | None:
    """Procura JSON com 'veredicto' no conteúdo — inclusive dentro de blocos <think>."""
    candidates = []

    # 1. texto limpo após remover blocos think
    clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    clean = re.sub(r"```(?:json)?\s*", "", clean).strip()
    if clean:
        candidates.append(clean)

    # 2. JSON embutido em qualquer lugar do conteúdo bruto (inclusive dentro de <think>)
    for m in re.finditer(r'\{[^{}]*"veredicto"[^{}]*\}', content, re.DOTALL):
        candidates.append(m.group())

    for text in candidates:
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue

    return None


def analisar_com_qwen(logs: list[dict], model: str) -> str:
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            base_url=get_lmstudio_base_url(),
            api_key="lm-studio",
        )

        # Campos mínimos — UUID/response_time/tipo não ajudam na detecção e inflam o prompt
        def _slim(r: dict) -> dict:
            return {
                "ip":       r["ip"],
                "method":   r["method"],
                "endpoint": r["endpoint"],
                "status":   r["status_code"],
                "time":     r["timestamp"][11:19],  # apenas HH:MM:SS
            }

        recent = logs[-5:]
        has_attack_pattern = sum(
            1 for r in recent
            if r.get("endpoint") == "/admin/login" and r.get("status_code") == 401
        ) >= 2
        sample = [_slim(r) for r in (logs[-15:] if has_attack_pattern else recent)]

        payload = json.dumps(sample, ensure_ascii=False)  # sem indent — menos tokens

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Logs: {payload}"},
            ],
            temperature=0.1,
            max_tokens=1024,
            timeout=120,
        )

        msg      = response.choices[0].message
        content  = msg.content or ""
        # Qwen3 Thinking escreve o JSON dentro do reasoning_content quando o orçamento de tokens
        # esgota antes do bloco <think> fechar — busca lá também como fallback
        reasoning = getattr(msg, "reasoning_content", None) or ""
        search_in = content or reasoning   # prefere content; usa reasoning se content vazio

        result = _extract_json_verdict(search_in)

        if result is None:
            upper = search_in.upper()
            veredicto = "ATAQUE" if "ATAQUE" in upper else ("FALSO_POSITIVO" if "FALSO" in upper else "NORMAL")
            result = {"veredicto": veredicto, "ip": None, "motivo": ""}

        veredicto = result.get("veredicto", "NORMAL")
        ip        = result.get("ip") or ""
        motivo    = result.get("motivo", "")

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
elapsed_qwen      = now - _ai_state["last_call"]  # global — evita chamadas duplicadas de múltiplas abas

# req/s
rps = round(new_logs_delta / elapsed, 2)
st.session_state.requests_per_second.append({"req/s": rps})
if len(st.session_state.requests_per_second) > 60:
    st.session_state.requests_per_second = st.session_state.requests_per_second[-60:]
st.session_state.last_log_count = current_log_count
st.session_state.last_tick      = now

# ── Qwen (LM Studio) — núcleo do sistema ────────────────────────────────────
qwen_model = get_qwen_model()

# Propaga resultado da thread para o session state (operação segura na thread principal)
if _ai_state["result"] is not None:
    st.session_state.qwen_result = _ai_state["result"]
    _ai_state["result"] = None

def _run_qwen_bg(logs_snapshot: list, model: str) -> None:
    try:
        _ai_state["result"] = analisar_com_qwen(logs_snapshot, model)
    finally:
        _ai_state["running"] = False  # garante reset mesmo em caso de exceção

# Detecta padrão de falso positivo nos logs recentes para acionar a IA imediatamente.
# O simulador injeta apenas 3 logs (new_logs_delta <= 3), então o trigger > 8 nunca dispara.
_recent10 = logs[-10:] if logs else []
_fp_hits   = sum(
    1 for r in _recent10
    if r.get("endpoint") == "/login" and r.get("status_code") == 401
)
has_fp_pattern = _fp_hits >= 2

# Chama imediatamente se: ataque (muitos logs), falso positivo detectado, ou ciclo normal de 15s
should_call = (
    qwen_model
    and estado == "NORMAL"
    and not _ai_state["running"]
    and (elapsed_qwen >= 15 or new_logs_delta > 8 or has_fp_pattern)
)
if should_call:
    with _ai_lock:
        if not _ai_state["running"]:   # double-check sob o lock evita threads duplicadas
            _ai_state["running"]   = True
            _ai_state["last_call"] = now
            threading.Thread(
                target=_run_qwen_bg,
                args=(list(logs), qwen_model),
                daemon=True,
            ).start()

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
    result = st.session_state.qwen_result
    if _ai_state["running"]:
        st.info("⏳ Analisando...")
    elif "ATAQUE" in result:
        st.error(f"🤖 {result}")
    elif "FALSO_POSITIVO" in result:
        st.warning(f"🤖 {result}")
    elif result.startswith("Erro"):
        st.warning(f"🤖 {result}")
    else:
        st.info("🤖 Monitorando...")

    st.caption(f"Modelo: {qwen_model}")

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
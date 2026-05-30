# dependencies: streamlit requests openai

import os
import re
import time
import json
import threading

import requests
import streamlit as st

API_BASE = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(layout="wide", page_title="SOC - Centro de Operações")

@st.cache_resource
def _ai_globals() -> dict:
    # cache_resource persiste entre reruns e sessões — o código de módulo é
    # re-executado a cada rerun, então Lock() e _ai_state criados no topo
    # do script seriam recriados a cada 2s, zerando running=False e
    # destruindo o mecanismo de lock.
    return {
        "lock":      threading.Lock(),
        "running":   False,
        "result":    None,
        "last_call": time.time(),
        "epoch":     0,   # incrementado a cada reset — descarta resultados de threads antigas
    }

_ai = _ai_globals()

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
    ("last_log_count",      None),   # None = não inicializado; será preenchido após 1ª busca
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
    start_epoch = _ai["epoch"]   # captura epoch no início — mudança indica reset

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            base_url=get_lmstudio_base_url(),
            api_key="lm-studio",
        )

        def _slim(r: dict) -> dict:
            return {
                "ip":       r["ip"],
                "method":   r["method"],
                "endpoint": r["endpoint"],
                "status":   r["status_code"],
                "time":     r["timestamp"][11:19],
            }

        # 5 logs são suficientes para o padrão "3+ = ATAQUE/FP".
        # Com 15 logs o modelo gastava 3000 tokens só em thinking e nunca escrevia JSON.
        sample  = [_slim(r) for r in logs[-5:]]
        payload = json.dumps(sample, ensure_ascii=False)

        content_buf   = ""
        reasoning_buf = ""

        # Streaming permite cancelar a geração imediatamente quando o reset é clicado
        with client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": f"Logs: {payload}"},
            ],
            temperature=0.1,
            max_tokens=3000,
            timeout=120,
            stream=True,
        ) as stream:
            for chunk in stream:
                if _ai["epoch"] != start_epoch:
                    # Reset clicado durante a análise — fecha conexão e para
                    return "NORMAL"
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        content_buf += delta.content
                    rc = getattr(delta, "reasoning_content", None)
                    if rc:
                        reasoning_buf += rc

        search_in = content_buf or reasoning_buf
        result    = _extract_json_verdict(search_in)

        if result is None:
            # Olha apenas os últimos 600 chars do reasoning — é onde o modelo conclui.
            # rfind no texto inteiro é enganoso: o modelo discute todas as categorias
            # antes de concluir (ex.: "ATAQUE não se aplica... FALSO_POSITIVO também não...
            # portanto NORMAL"), e o fallback encontra a última menção, não a conclusão.
            tail  = (search_in[-600:] if len(search_in) > 600 else search_in).upper()
            pos   = {
                "ATAQUE":         tail.rfind("ATAQUE"),
                "FALSO_POSITIVO": tail.rfind("FALSO_POSITIVO"),
                "NORMAL":         tail.rfind("NORMAL"),
            }
            veredicto = max(pos, key=lambda k: pos[k]) if any(v >= 0 for v in pos.values()) else "NORMAL"
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
elapsed           = max(now - st.session_state.last_tick, 0.001)

if st.session_state.last_log_count is None:
    st.session_state.last_log_count = current_log_count

new_logs_delta = max(current_log_count - st.session_state.last_log_count, 0)

# ── Detecta Reset ────────────────────────────────────────────────────────────
# Dois sinais independentes: queda abrupta no log_queue (reset clicado enquanto
# a IA ainda analisa) OU transição de estado para NORMAL (reset após detecção).
_prev_log   = st.session_state.get("_prev_log_count", current_log_count)
_prev_estado = st.session_state.get("_prev_estado", estado)

reset_detected = (
    (_prev_log > 10 and current_log_count < 3)           # log_queue foi zerado
    or (_prev_estado != "NORMAL" and estado == "NORMAL")  # saiu de ATAQUE/FP
)
st.session_state["_prev_log_count"] = current_log_count
st.session_state["_prev_estado"]    = estado

if reset_detected:
    _ai["epoch"]    += 1   # sinaliza à thread de streaming para fechar conexão
    _ai["running"]   = False
    _ai["result"]    = None
    _ai["last_call"] = time.time()
    st.session_state.qwen_result = "Monitorando..."

# req/s
rps = round(new_logs_delta / elapsed, 2)
st.session_state.requests_per_second.append({"req/s": rps})
if len(st.session_state.requests_per_second) > 60:
    st.session_state.requests_per_second = st.session_state.requests_per_second[-60:]
st.session_state.last_log_count = current_log_count
st.session_state.last_tick      = now

# ── Qwen (LM Studio) — núcleo do sistema ────────────────────────────────────
qwen_model = get_qwen_model()

if _ai["result"] is not None:
    st.session_state.qwen_result = _ai["result"]
    _ai["result"] = None

def _run_qwen_bg(logs_snapshot: list, model: str, epoch: int) -> None:
    try:
        result = analisar_com_qwen(logs_snapshot, model)
        if _ai["epoch"] == epoch:
            _ai["result"] = result
    finally:
        if _ai["epoch"] == epoch:
            _ai["running"]   = False
            _ai["last_call"] = time.time()  # reseta timer após terminar — evita loop imediato

# A IA só analisa quando ataque ou falso positivo é simulado.
# A API seta ai_trigger=True; o dashboard consome e despacha a thread.
should_call = (
    qwen_model
    and not _ai["running"]
    and status.get("ai_trigger", False)
)
if should_call:
    with _ai["lock"]:
        if not _ai["running"] and status.get("ai_trigger", False):
            _ai["running"]   = True
            _ai["last_call"] = now
            try:
                requests.get(f"{API_BASE}/clear-trigger", timeout=2)
            except Exception:
                pass
            threading.Thread(
                target=_run_qwen_bg,
                args=(list(logs), qwen_model, _ai["epoch"]),
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
    if _ai["running"]:
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
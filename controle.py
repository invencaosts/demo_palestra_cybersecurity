# dependencies: streamlit requests

import os
import time

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Controle CyberDemo", layout="centered")

st.markdown("""
<style>
.stApp { background-color: #0d1117; color: #c9d1d9; }
.stApp header { background-color: #0d1117; }
</style>
""", unsafe_allow_html=True)

st.title("🎮 Painel de Controle")
st.markdown(
    "<p style='color:#888;font-size:0.9rem;margin-top:-12px;'>Acesso restrito ao apresentador</p>",
    unsafe_allow_html=True,
)

st.divider()


def call_api(path: str, params: dict | None = None) -> bool:
    try:
        requests.get(f"{API_URL}{path}", params=params, timeout=30)
        return True
    except Exception as exc:
        st.error(f"Erro ao chamar a API: {exc}")
        return False


# ── botões de simulação ───────────────────────────────────────────────────────
if st.button("💣 SIMULAR ATAQUE", use_container_width=True, type="primary"):
    if call_api("/attack"):
        st.toast("Ataque injetado! A IA vai detectar em instantes.", icon="💣")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

if st.button("👤 SIMULAR FALSO POSITIVO", use_container_width=True):
    if call_api("/false-positive"):
        st.toast("Falso positivo injetado. Leva ~6 segundos.", icon="👤")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

if st.button("🔄 RESETAR SISTEMA", use_container_width=True):
    if call_api("/reset"):
        st.toast("Sistema resetado.", icon="🔄")

st.divider()

# ── configurar modelo Qwen (LM Studio) ───────────────────────────────────────
st.markdown("**🤖 Modelo Qwen (LM Studio)**")
qwen_model_input = st.text_input(
    "Modelo",
    placeholder="ex: qwen/qwen3-4b-thinking-2507",
    label_visibility="collapsed",
)
if st.button("Salvar modelo", use_container_width=True):
    if qwen_model_input.strip():
        if call_api("/set-qwen-model", {"model": qwen_model_input.strip()}):
            st.toast("Modelo salvo com sucesso!", icon="🤖")
    else:
        st.toast("Digite o nome do modelo antes de salvar.", icon="⚠️")

# indicador de modelo ativo
try:
    r = requests.get(f"{API_URL}/get-qwen-model", timeout=3)
    current_model = r.json().get("model", "")
except Exception:
    current_model = ""

st.caption(f"🟢 Modelo ativo: {current_model}" if current_model else "🔴 Modelo não definido")

st.divider()

# ── badge de status ───────────────────────────────────────────────────────────
try:
    r      = requests.get(f"{API_URL}/status", timeout=3)
    estado = r.json().get("estado", "NORMAL")
except Exception:
    estado = "ERRO"

COLOR = {
    "NORMAL":          ("#1b5e20", "✅ NORMAL"),
    "ATAQUE":          ("#b71c1c", "🚨 ATAQUE"),
    "FALSO_POSITIVO":  ("#bf360c", "⚠️ FALSO POSITIVO"),
}
bg, label = COLOR.get(estado, ("#333", f"? {estado}"))

st.markdown(f"""
<div style="
    background:{bg};
    padding:16px 20px;
    border-radius:8px;
    text-align:center;
">
  <span style="font-size:1.4rem;font-weight:700;color:#fff;">{label}</span>
</div>
""", unsafe_allow_html=True)

time.sleep(3)
st.rerun()
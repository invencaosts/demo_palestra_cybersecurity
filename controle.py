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

# ── configurar chave Gemini ───────────────────────────────────────────────────
st.markdown("**🔑 Gemini API Key**")
gemini_key_input = st.text_input(
    "Chave",
    type="password",
    placeholder="Cole sua chave aqui",
    label_visibility="collapsed",
)
if st.button("Salvar chave", use_container_width=True):
    if gemini_key_input.strip():
        if call_api("/set-gemini-key", {"key": gemini_key_input.strip()}):
            st.toast("Chave salva com sucesso!", icon="🔑")
    else:
        st.toast("Digite uma chave antes de salvar.", icon="⚠️")

# indicador de chave ativa
try:
    r = requests.get(f"{API_URL}/get-gemini-key", timeout=3)
    key_set = bool(r.json().get("key", ""))
except Exception:
    key_set = False

st.caption("🟢 Chave ativa" if key_set else "🔴 Chave não definida")

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
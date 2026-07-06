import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_video_ideas import CATEGORY_LABELS, generate_ideas, load_history  # noqa: E402

st.set_page_config(
    page_title="Gerador de Ideias",
    page_icon="💡",
    layout="centered",
)

st.title("Gerador de Ideias de Vídeo")
st.caption("Tema, roteiro em português e palavras-chave em inglês via Ollama.")

if "ideas" not in st.session_state:
    st.session_state.ideas = []
if "last_csv" not in st.session_state:
    st.session_state.last_csv = None

with st.sidebar:
    count = st.number_input("Quantidade", min_value=1, max_value=10, value=5, step=1)
    history = load_history()
    st.metric("Ideias no histórico", len(history.get("entries", [])))

generate = st.button("Gerar", type="primary", use_container_width=True)

if generate:
    with st.spinner("Gerando ideias com Ollama... pode levar alguns minutos."):
        try:
            ideas, csv_path = generate_ideas(count=count, save=True)
            st.session_state.ideas = ideas
            st.session_state.last_csv = csv_path
        except Exception as exc:
            st.error(f"Erro ao gerar: {exc}")
            st.stop()

if st.session_state.last_csv:
    st.success(f"CSV salvo em: `{st.session_state.last_csv}`")

if not st.session_state.ideas:
    st.info("Clique em **Gerar** para criar novas ideias.")
else:
    for index, idea in enumerate(st.session_state.ideas, start=1):
        category = CATEGORY_LABELS.get(idea["category"], idea["category"])
        st.divider()
        st.subheader(f"Ideia {index}")
        st.markdown(f"**Categoria:** {category}")
        st.markdown("**Tema do vídeo**")
        st.code(idea["theme"], language=None)
        st.markdown("**Roteiro do vídeo**")
        st.text_area(
            label="roteiro",
            value=idea["script"],
            height=100,
            key=f"script_{index}",
            label_visibility="collapsed",
        )
        st.markdown("**Palavras-chave do vídeo (inglês)**")
        st.code(idea["keywords"], language=None)

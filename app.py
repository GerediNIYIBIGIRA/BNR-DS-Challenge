"""BNR RAG System — Streamlit Web Interface

Run with:
    streamlit run app.py
"""
from __future__ import annotations

import os
import sys
import logging

from dotenv import load_dotenv
import streamlit as st

load_dotenv()
logging.basicConfig(level=logging.WARNING)

# ── Cloud / HF Spaces: inject secrets into env vars ──────────────────────────
# st.secrets is populated from the HF Spaces / Streamlit Cloud secrets panel.
# We push values into os.environ so all downstream modules pick them up via
# os.getenv() without needing to know about Streamlit.
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    if "CHROMADB_MODE" in st.secrets:
        os.environ["CHROMADB_MODE"] = st.secrets["CHROMADB_MODE"]
    if "LLM_MODEL" in st.secrets:
        os.environ["LLM_MODEL"] = st.secrets["LLM_MODEL"]
except Exception:
    pass  # st.secrets not available in local dev — fall through to .env

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BNR Document Assistant",
    # page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.answer-box {
    background: #f0f4ff;
    border-left: 4px solid #1a3c8f;
    padding: 1rem 1.2rem;
    border-radius: 4px;
    font-size: 0.97rem;
    white-space: pre-wrap;
}
.chunk-box {
    background: #fafafa;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 0.8rem;
    font-size: 0.85rem;
    font-family: monospace;
}
.badge {
    display: inline-block;
    background: #1a3c8f;
    color: white;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 0.78rem;
    margin-right: 6px;
}
</style>
""", unsafe_allow_html=True)


# ── Pipeline cache ────────────────────────────────────────────────────────────

@st.cache_resource(
    show_spinner="Building knowledge index from corpus … (first load ~30 s)"
)
def get_pipeline(api_key: str, top_k: int = 5):
    from src.rag_pipeline import RAGPipeline
    # rebuild_index=True is safe here: for ephemeral DB it's always needed;
    # for local persistent DB @st.cache_resource prevents repeated rebuilds.
    return RAGPipeline(api_key=api_key, rebuild_index=True, top_k=top_k)


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[str, int, bool]:
    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/"
            "Coat_of_arms_of_Rwanda.svg/120px-Coat_of_arms_of_Rwanda.svg.png",
            width=80,
        )
        st.title("BNR Document\nIntelligence")
        st.caption("RAG Prototype — DS Challenge #1")
        st.markdown("---")

        # On HF Spaces the key comes from secrets; show a masked placeholder
        _env_key = os.getenv("ANTHROPIC_API_KEY", "")
        api_key = st.text_input(
            "Anthropic API Key",
            value=_env_key,
            type="password",
            help="Set via HF Spaces secrets or local .env — or paste here.",
        )
        top_k = st.slider("Chunks to retrieve", min_value=3, max_value=10, value=5)
        show_ctx = st.toggle("Show retrieved context", value=True)

        st.markdown("---")
        st.markdown("**Corpus (4 documents)**")
        st.markdown("""
- Rwanda FinScope 2024
- Payment System Law 2021
- GSMA Mobile Money 2025
- IMF Financial Access Survey
        """)

        st.markdown("---")
        if st.button("Rebuild index"):
            st.cache_resource.clear()
            st.rerun()

        st.caption("Developed and powered by Geredi Niyibigira")

    return api_key, top_k, show_ctx


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    api_key, top_k, show_ctx = render_sidebar()

    st.title("BNR Document Intelligence Assistant")
    st.caption(
        "Ask questions grounded in the BNR corpus. "
        "Answers cite the source document and page."
    )

    if not api_key:
        st.info("Enter your Anthropic API key in the sidebar to begin.")
        return

    # Load pipeline
    try:
        pipeline = get_pipeline(api_key, top_k)
    except Exception as exc:
        st.error(f"Failed to load pipeline: {exc}")
        return

    # ── Example questions ─────────────────────────────────────────────────────
    st.markdown("#### Try an example question")
    examples = [
        "What are the main barriers to financial inclusion in rural Rwanda?",
        "How does mobile money usage differ by gender?",
        "What are the NBR's powers in overseeing the payment system?",
        "Has digital payment adoption increased in Rwanda?",
        "How does Rwanda compare to global mobile money trends?",
    ]

    clicked: str | None = None
    cols = st.columns(len(examples))
    for col, q in zip(cols, examples):
        if col.button(q[:38] + "…", use_container_width=True, help=q):
            clicked = q

    # Write to session state BEFORE the widget renders so it picks up the value
    if clicked:
        st.session_state["question_input"] = clicked

    # ── Query input ───────────────────────────────────────────────────────────
    st.markdown("#### Or type your own question")
    question = st.text_area(
        label="Question",
        label_visibility="collapsed",
        height=90,
        placeholder="Type your question here …",
        key="question_input",
    )

    run = st.button("Search & Answer", type="primary", disabled=not question.strip())

    # ── Results ───────────────────────────────────────────────────────────────
    if run and question.strip():
        with st.spinner("Retrieving context and generating answer …"):
            try:
                result = pipeline.query(question.strip())
            except Exception as exc:
                st.error(f"Error: {exc}")
                return

        st.markdown("---")

        # Answer
        st.markdown("### Answer")
        st.markdown(
            f'<div class="answer-box">{result["answer"]}</div>',
            unsafe_allow_html=True,
        )

        # Metadata badges
        st.markdown(
            f'<span class="badge">Model: {result["model"]}</span>'
            f'<span class="badge">Latency: {result["latency_ms"]:.0f} ms</span>'
            f'<span class="badge">Tokens in/out: {result["input_tokens"]} / {result["output_tokens"]}</span>'
            f'<span class="badge">Chunks retrieved: {result["num_chunks_retrieved"]}</span>',
            unsafe_allow_html=True,
        )

        # Retrieved context (collapsible)
        if show_ctx and result.get("context_used"):
            st.markdown("")
            with st.expander(
                f"Retrieved context ({len(result['context_used'])} chunks)",
                expanded=False,
            ):
                for i, chunk in enumerate(result["context_used"], start=1):
                    st.markdown(
                        f"**[{i}]** `{chunk.source_name}`  |  "
                        f"Page **{chunk.page}**  |  "
                        f"Similarity **{chunk.similarity:.3f}**"
                    )
                    st.markdown(
                        f'<div class="chunk-box">'
                        f'{chunk.text[:600].replace(chr(10), "<br>")}'
                        f'{"…" if len(chunk.text) > 600 else ""}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("")


if __name__ == "__main__":
    main()

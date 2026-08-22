"""
app.py — RAGForge Streamlit Interface
======================================

Run with:
    streamlit run app.py

CHANGES IN THIS REVISION (Phase 3, Step 1)
--------------------------------------------
Added a Retrieval Strategy selector to the sidebar so each retrieval
mode can be exercised and compared live in the UI:

  dense          → vector search only (baseline)
  bm25           → keyword search only (baseline)
  hybrid         → dense + bm25 + RRF, no reranking
  hybrid_rerank  → hybrid + CrossEncoder (Phase 2 default)

Each response now shows the active strategy and retrieval latency
separately from generation latency, making trade-offs visible.

Phase 2 items preserved:
- Conversation-aware query rewriting + spellcheck.
- Streaming generation.
- Source attribution + retrieved-context expander.
"""

import html
import time

import streamlit as st

st.set_page_config(
    page_title="RAGForge — Phase 2",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0f1117; }

    .source-badge {
        display: inline-block;
        background: #1e2a3a;
        border: 1px solid #2d4a6e;
        border-radius: 6px;
        padding: 2px 10px;
        margin: 2px;
        font-size: 0.82em;
        color: #7eb8f7;
        font-family: monospace;
    }

    .chunk-box {
        background: #161b26;
        border-left: 3px solid #3b82f6;
        border-radius: 4px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 0.88em;
        color: #d1d5db;
    }

    .distance-badge {
        font-size: 0.75em;
        color: #6b7280;
    }

    .timing-badge {
        font-size: 0.78em;
        color: #6b7280;
        font-family: monospace;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)


def _import_modules():
    try:
        from src.retriever import retrieve_with_timing
        from src.generator import generate_answer_stream
        from src.vector_store import get_collection_stats
        from src.config import config
        from src.query_rewriter import rewrite_query
        return retrieve_with_timing, generate_answer_stream, get_collection_stats, config, rewrite_query
    except ImportError as e:
        st.error(f"❌ Import error: {e}\n\nRun: `pip install -r requirements.txt`")
        st.stop()


# Phase 3: strategy descriptions shown as help text in the UI
_STRATEGY_HELP = {
    "dense": "Vector search only. Fast semantic baseline. Weak on exact keywords.",
    "bm25": "Keyword search only. Fast lexical baseline. Weak on paraphrases.",
    "hybrid": "Dense + BM25 fused with Reciprocal Rank Fusion. Best of both worlds, no reranking overhead.",
    "hybrid_rerank": "Hybrid + CrossEncoder reranking. Highest accuracy. Adds ~50-200ms latency.",
}


def render_sidebar(get_collection_stats, config):
    with st.sidebar:
        st.title("🔍 RAGForge")
        st.caption("Advanced RAG System — Phase 3")
        st.divider()

        st.subheader("📦 Vector Store Status")
        try:
            stats = get_collection_stats()
            chunk_count = stats["total_chunks"]
            if chunk_count == 0:
                st.warning("⚠️ Vector store is empty!\n\nRun ingestion first:")
                st.code("python -m src.ingest", language="bash")
            else:
                st.success(f"✅ {chunk_count:,} chunks indexed")
                st.caption(f"Collection: `{stats['collection_name']}`")
                st.caption(f"DB path: `{stats['db_path']}`")
        except Exception as e:
            st.error(f"Could not read vector store:\n{e}")

        st.divider()

        # Phase 3: Retrieval Strategy selector
        st.subheader("🔎 Retrieval Strategy")
        strategies = ["dense", "bm25", "hybrid", "hybrid_rerank"]
        strategy_labels = {
            "dense": "Dense (vector only)",
            "bm25": "BM25 (keyword only)",
            "hybrid": "Hybrid (Dense + BM25 + RRF)",
            "hybrid_rerank": "Hybrid + Reranker ⭐",
        }
        strategy = st.radio(
            "Select strategy",
            options=strategies,
            format_func=lambda s: strategy_labels[s],
            index=strategies.index(st.session_state.get("strategy", "hybrid_rerank")),
            label_visibility="collapsed",
        )
        st.session_state.strategy = strategy
        st.caption(_STRATEGY_HELP[strategy])

        st.divider()

        st.subheader("⚙️ Settings")
        top_k = st.slider(
            "Chunks to retrieve (top-k)",
            min_value=1,
            max_value=config.TOP_K_MAX,
            value=config.TOP_K,
            help="How many document chunks to retrieve per query. More = more context but slower."
        )

        st.divider()

        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.retrieval_data = {}
            st.session_state.timing_data = {}
            st.session_state.rewritten_queries = {}
            st.rerun()

        st.divider()

        with st.expander("📚 Phase 3 Features"):
            st.markdown("""
**Phase 3 (Step 1)**
- **Configurable strategy**: dense / bm25 / hybrid / hybrid+rerank
- **Per-step latency**: see retrieval vs generation time separately
- **Experiment harness**: `python experiments/hybrid_vs_dense.py`

**Phase 2 (preserved)**
- Spellcheck + Query rewriting
- Conversation-aware prompting
- Semantic chunking + Incremental ingest + OCR
            """)

    return top_k, strategy


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "retrieval_data" not in st.session_state:
        st.session_state.retrieval_data = {}
    if "timing_data" not in st.session_state:
        st.session_state.timing_data = {}
    if "rewritten_queries" not in st.session_state:
        st.session_state.rewritten_queries = {}
    if "strategy" not in st.session_state:
        st.session_state.strategy = "hybrid_rerank"


def render_chat_history():
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message["role"] == "user" and i in st.session_state.rewritten_queries:
                rewritten = st.session_state.rewritten_queries[i]
                if rewritten != message["content"]:
                    st.caption(f"🔄 Rewritten: *{rewritten}*")

            if message["role"] == "assistant" and i in st.session_state.retrieval_data:
                render_sources_and_context(st.session_state.retrieval_data[i])
                if i in st.session_state.timing_data:
                    render_timing(st.session_state.timing_data[i])


def render_timing(timing: dict):
    strategy_label = timing.get("strategy", "?")
    st.markdown(
        f"<div class='timing-badge'>⏱️ strategy: <b>{strategy_label}</b> · "
        f"retrieval: {timing['retrieval_ms']}ms · "
        f"generation: {timing['generation_ms']}ms</div>",
        unsafe_allow_html=True,
    )


def render_sources_and_context(retrieved_chunks: list):
    """Render source citations and an expandable retrieved-context section."""
    if not retrieved_chunks:
        return

    st.markdown("**Sources:**")
    source_strings = []
    seen = set()
    for chunk in retrieved_chunks:
        source = html.escape(str(chunk.get("source", "unknown")))
        page = html.escape(str(chunk.get("page", "?")))
        key = f"{source}__p{page}"
        if key not in seen:
            seen.add(key)
            source_strings.append(f'<span class="source-badge">📄 {source} — page {page}</span>')

    st.markdown(" ".join(source_strings), unsafe_allow_html=True)

    with st.expander(f"🔍 Retrieved Context ({len(retrieved_chunks)} chunks)", expanded=False):
        from src.config import config as _cfg
        preview_len = _cfg.MAX_CHUNK_PREVIEW_CHARS

        for i, chunk in enumerate(retrieved_chunks, start=1):
            source = html.escape(str(chunk.get("source", "?")))
            page = html.escape(str(chunk.get("page", "?")))
            
            # Phase 2: Hybrid + Reranker adds distance and/or rerank_score
            dist_str = f"{chunk.get('distance', '?'):.4f}" if "distance" in chunk else "?"
            score_str = f"{chunk.get('rerank_score', '?'):.4f}" if "rerank_score" in chunk else "?"
            
            raw_text = chunk.get("text", "")
            text = html.escape(raw_text[:preview_len])
            suffix = "..." if len(raw_text) > preview_len else ""

            st.markdown(
                f"<div class='chunk-box'>"
                f"<b>Chunk #{i}</b> &nbsp;"
                f"<span class='distance-badge'>dist: {dist_str} | rerank: {score_str}</span><br>"
                f"<b>Source:</b> {source} &nbsp;|&nbsp; <b>Page:</b> {page}<br><br>"
                f"{text}{suffix}"
                f"</div>",
                unsafe_allow_html=True
            )


def main():
    retrieve_with_timing, generate_answer_stream, get_collection_stats, config, rewrite_query = _import_modules()

    init_session_state()
    top_k, strategy = render_sidebar(get_collection_stats, config)

    st.title("🔍 RAGForge")
    st.caption(
        "Ask questions about your documents. "
        "Answers are grounded in retrieved document context — no hallucination."
    )

    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(
                "👋 Hello! I'm RAGForge (Phase 3). "
                "Select a **Retrieval Strategy** in the sidebar to experiment with different approaches.\n\n"
                "Available strategies:\n"
                "- **Dense** — semantic vector search baseline\n"
                "- **BM25** — keyword search baseline\n"
                "- **Hybrid** — best of both worlds via RRF\n"
                "- **Hybrid + Reranker** — highest accuracy, most compute\n\n"
                "Ask anything about your documents! 🎯"
            )

    render_chat_history()

    if user_query := st.chat_input("Ask a question about your documents..."):
        if not user_query.strip():
            st.warning("Please enter a question.")
            st.stop()

        # Phase 2: Query Rewriting and Normalization
        with st.spinner("🔄 Understanding question..."):
            from src.query_rewriter import normalize_query
            
            # First, resolve any conversational follow-up references
            rewritten_query = rewrite_query(
                user_query, 
                st.session_state.messages, 
                max_turns=config.CONVERSATION_HISTORY_TURNS
            )
            
            # Then fix any typos so embedding works reliably
            final_query = normalize_query(rewritten_query)

        user_msg_index = len(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": user_query})
        st.session_state.rewritten_queries[user_msg_index] = final_query

        with st.chat_message("user"):
            st.markdown(user_query)
            if final_query != user_query:
                st.caption(f"🔄 Rewritten: *{final_query}*")

        with st.chat_message("assistant"):
            retrieved_chunks = []
            retrieval_ms = 0
            generation_ms = 0
            answer = None

            # ── Retrieve ──────────────────────────────────────────────────────
            with st.spinner(f"🔍 Searching documents [{strategy}]..."):
                try:
                    retrieved_chunks, retrieval_meta = retrieve_with_timing(
                        final_query, top_k=top_k, strategy=strategy
                    )
                    retrieval_ms = retrieval_meta["total_ms"]
                except RuntimeError as e:
                    answer = f"❌ Retrieval error: {e}\n\nMake sure you've run ingestion: `python -m src.ingest`"
                except ValueError as e:
                    answer = f"⚠️ {e}"

            # ── Generate (streamed) ──────────────────────────────────────────
            if answer is None:
                try:
                    t1 = time.perf_counter()
                    # Phase 2: pass history to the generator (exclude the current message)
                    stream = generate_answer_stream(
                        final_query, 
                        retrieved_chunks, 
                        conversation_history=st.session_state.messages[:-1]
                    )
                    answer = st.write_stream(stream)
                    generation_ms = round((time.perf_counter() - t1) * 1000)
                except ValueError as e:
                    answer = (
                        f"❌ Configuration error: {e}\n\n"
                        "Add your API key to `.env`:\n```\nLLM_API_KEY=your_key_here\n```"
                    )
                    st.markdown(answer)
                except RuntimeError as e:
                    answer = f"❌ Generation error: {e}"
                    st.markdown(answer)
            else:
                st.markdown(answer)

            # ── Sources + context (only if we actually got chunks) ───────────
            if retrieved_chunks:
                render_sources_and_context(retrieved_chunks)
                timing = {
                    "strategy": strategy,
                    "retrieval_ms": retrieval_ms,
                    "generation_ms": generation_ms,
                }
                render_timing(timing)

        # Save to session state
        msg_index = len(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.retrieval_data[msg_index] = retrieved_chunks
        if retrieved_chunks:
            st.session_state.timing_data[msg_index] = {
                "strategy": strategy,
                "retrieval_ms": retrieval_ms,
                "generation_ms": generation_ms,
            }


if __name__ == "__main__":
    main()

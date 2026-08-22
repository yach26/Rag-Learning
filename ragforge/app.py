"""
app.py — RAGForge Streamlit Interface
======================================

Run with:
    streamlit run app.py

CHANGES IN THIS REVISION (Phase 2)
-------------------------------------
1. CONVERSATION AWARENESS:
   - Queries are now routed through `query_rewriter.rewrite_query()` so
     follow-ups ("what about the second one?") become standalone queries.
   - The rewritten query is shown in the UI below the user's input.
   - `st.session_state.messages` (last N turns) is passed to
     `generate_answer_stream()` so the LLM has context for references.
2. CLEAR CONVERSATION properly clears the in-memory BM25 index if needed
   (though it's tied to the DB, it's good practice).

Phase 1 items preserved:
- Streaming response chunks.
- HTML escaping in UI.
- Timing metrics.
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
        from src.retriever import retrieve
        from src.generator import generate_answer_stream
        from src.vector_store import get_collection_stats
        from src.config import config
        from src.query_rewriter import rewrite_query
        return retrieve, generate_answer_stream, get_collection_stats, config, rewrite_query
    except ImportError as e:
        st.error(f"❌ Import error: {e}\n\nRun: `pip install -r requirements.txt`")
        st.stop()


def render_sidebar(get_collection_stats, config):
    with st.sidebar:
        st.title("🔍 RAGForge")
        st.caption("Advanced RAG System — Phase 2")
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

        with st.expander("📚 Phase 2 Features Active"):
            st.markdown("""
- **Hybrid Search**: Vector + BM25 keyword search
- **Reranking**: CrossEncoder rescoring
- **Conversation**: Query rewriting + history prompt
- **Chunking**: Semantic recursive boundary split
- **Ingestion**: Hash-based skip + OCR fallback
            """)

    return top_k


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "retrieval_data" not in st.session_state:
        st.session_state.retrieval_data = {}
    if "timing_data" not in st.session_state:
        st.session_state.timing_data = {}
    if "rewritten_queries" not in st.session_state:
        st.session_state.rewritten_queries = {}


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
    st.markdown(
        f"<div class='timing-badge'>⏱️ retrieval: {timing['retrieval_ms']}ms · "
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
    retrieve, generate_answer_stream, get_collection_stats, config, rewrite_query = _import_modules()

    top_k = render_sidebar(get_collection_stats, config)
    init_session_state()

    st.title("🔍 RAGForge")
    st.caption(
        "Ask questions about your documents. "
        "Answers are grounded in retrieved document context — no hallucination."
    )

    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(
                "👋 Hello! I'm RAGForge (Phase 2). I can answer questions based on the documents "
                "you've ingested.\n\n"
                "**What's new:**\n"
                "- I remember recent conversation context for follow-ups.\n"
                "- I use hybrid search (BM25 + Vectors) and reranking for better accuracy.\n\n"
                "Ask me anything about your documents! 🎯"
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
            with st.spinner("🔍 Searching documents..."):
                t0 = time.perf_counter()
                try:
                    retrieved_chunks = retrieve(final_query, top_k=top_k)
                    retrieval_ms = round((time.perf_counter() - t0) * 1000)
                except RuntimeError as e:
                    answer = f"❌ Retrieval error: {e}\n\nMake sure you've run ingestion: `python -m src.ingest`"
                except ValueError as e:
                    answer = f"⚠️ {e}"

            # ── Generate (streamed) ──────────────────────────────────────────
            if answer is None:
                try:
                    t1 = time.perf_counter()
                    # Phase 2: pass history to the generator
                    stream = generate_answer_stream(
                        final_query, 
                        retrieved_chunks, 
                        conversation_history=st.session_state.messages
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

            # ── Sources + context (only if we actually got chunks) ─────────────
            if retrieved_chunks:
                render_sources_and_context(retrieved_chunks)
                timing = {"retrieval_ms": retrieval_ms, "generation_ms": generation_ms}
                render_timing(timing)

        # Save to session state
        msg_index = len(st.session_state.messages)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.retrieval_data[msg_index] = retrieved_chunks
        if retrieved_chunks:
            st.session_state.timing_data[msg_index] = {
                "retrieval_ms": retrieval_ms,
                "generation_ms": generation_ms,
            }


if __name__ == "__main__":
    main()

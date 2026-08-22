"""
app.py — RAGForge Streamlit Interface
======================================

Run with:
    streamlit run app.py

This is the main UI. It connects retrieval + generation into an interactive
chat interface that also exposes the internal RAG workings (retrieved chunks,
sources, distances) so you can see exactly how the system reaches its answers.
"""

import streamlit as st

# ── Page Configuration ────────────────────────────────────────────────────────
# Must be the very first Streamlit call
st.set_page_config(
    page_title="RAGForge — Beginner RAG System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f1117; }

    /* Source badge */
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

    /* Chunk preview box */
    .chunk-box {
        background: #161b26;
        border-left: 3px solid #3b82f6;
        border-radius: 4px;
        padding: 10px 14px;
        margin: 6px 0;
        font-size: 0.88em;
        color: #d1d5db;
    }

    /* Distance badge */
    .distance-badge {
        font-size: 0.75em;
        color: #6b7280;
    }
</style>
""", unsafe_allow_html=True)


# ── Lazy imports (after page config) ─────────────────────────────────────────
# We import lazily so Streamlit's watcher doesn't trigger on startup errors

def _import_modules():
    """Import project modules, catching missing dependencies early."""
    try:
        from src.retriever import retrieve
        from src.generator import generate_answer
        from src.vector_store import get_collection_stats
        return retrieve, generate_answer, get_collection_stats
    except ImportError as e:
        st.error(f"❌ Import error: {e}\n\nRun: `pip install -r requirements.txt`")
        st.stop()


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar(get_collection_stats):
    """Render the sidebar with system status and configuration info."""
    with st.sidebar:
        st.title("🔍 RAGForge")
        st.caption("Beginner RAG System — Phase 1")
        st.divider()

        # Vector DB status
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

        # Settings
        st.subheader("⚙️ Settings")
        top_k = st.slider(
            "Chunks to retrieve (top-k)",
            min_value=1,
            max_value=10,
            value=5,
            help="How many document chunks to retrieve per query. More = more context but slower."
        )

        st.divider()

        # How it works
        with st.expander("📚 How RAG works"):
            st.markdown("""
**1. Ingestion** (offline)
- Load PDF/TXT/MD documents
- Split into small chunks
- Embed each chunk → vector
- Store in ChromaDB

**2. Retrieval** (per query)
- Embed the user query
- Find nearest chunk vectors
- Return top-k chunks

**3. Generation** (per query)
- Build prompt with chunks as context
- Call Gemini LLM
- Return grounded answer
            """)

    return top_k


# ── Chat History ──────────────────────────────────────────────────────────────

def init_session_state():
    """Initialize Streamlit session state for conversation history."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "retrieval_data" not in st.session_state:
        st.session_state.retrieval_data = {}  # message_index → retrieved chunks


def render_chat_history():
    """Display all previous messages in the conversation."""
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            # Show retrieved context for assistant messages
            if message["role"] == "assistant" and i in st.session_state.retrieval_data:
                render_sources_and_context(
                    st.session_state.retrieval_data[i],
                    message_index=i,
                )


def render_sources_and_context(retrieved_chunks: list, message_index: int):
    """
    Render source citations and an expandable retrieved context section.

    This is the key learning feature — it shows you exactly what chunks
    the LLM received as context for each answer.
    """
    if not retrieved_chunks:
        return

    # ── Source badges ─────────────────────────────────────────────────────────
    st.markdown("**Sources:**")
    source_strings = []
    seen = set()
    for chunk in retrieved_chunks:
        source = chunk.get("source", "unknown")
        page = chunk.get("page", "?")
        key = f"{source}__p{page}"
        if key not in seen:
            seen.add(key)
            source_strings.append(f'<span class="source-badge">📄 {source} — page {page}</span>')

    st.markdown(" ".join(source_strings), unsafe_allow_html=True)

    # ── Expandable retrieved context ──────────────────────────────────────────
    with st.expander(f"🔍 Retrieved Context ({len(retrieved_chunks)} chunks)", expanded=False):
        st.caption(
            "These are the exact document chunks that were given to the LLM as context. "
            "If the answer seems wrong, check whether the right chunks were retrieved."
        )
        for i, chunk in enumerate(retrieved_chunks, start=1):
            source = chunk.get("source", "?")
            page = chunk.get("page", "?")
            distance = chunk.get("distance", "?")
            text = chunk.get("text", "")

            st.markdown(
                f"<div class='chunk-box'>"
                f"<b>Chunk #{i}</b> &nbsp;"
                f"<span class='distance-badge'>distance: {distance} (lower = more relevant)</span><br>"
                f"<b>Source:</b> {source} &nbsp;|&nbsp; <b>Page:</b> {page}<br><br>"
                f"{text[:800]}{'...' if len(text) > 800 else ''}"
                f"</div>",
                unsafe_allow_html=True
            )


# ── Main App ──────────────────────────────────────────────────────────────────

def main():
    retrieve, generate_answer, get_collection_stats = _import_modules()

    top_k = render_sidebar(get_collection_stats)
    init_session_state()

    # ── Page header ───────────────────────────────────────────────────────────
    st.title("🔍 RAGForge")
    st.caption(
        "Ask questions about your documents. "
        "Answers are grounded in retrieved document context — no hallucination."
    )

    # ── Welcome message on first load ─────────────────────────────────────────
    if not st.session_state.messages:
        with st.chat_message("assistant"):
            st.markdown(
                "👋 Hello! I'm RAGForge. I can answer questions based on the documents "
                "you've ingested.\n\n"
                "**To get started:**\n"
                "1. Add documents to `data/documents/`\n"
                "2. Run `python -m src.ingest`\n"
                "3. Ask me anything about those documents!\n\n"
                "I will only answer from the documents — I won't make things up. 🎯"
            )

    # ── Chat history ──────────────────────────────────────────────────────────
    render_chat_history()

    # ── Chat input ────────────────────────────────────────────────────────────
    if user_query := st.chat_input("Ask a question about your documents..."):

        # Validate input
        if not user_query.strip():
            st.warning("Please enter a question.")
            st.stop()

        # Display user message
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})

        # Generate response
        with st.chat_message("assistant"):
            retrieved_chunks = []

            # ── Retrieve ──────────────────────────────────────────────────────
            with st.spinner("🔍 Searching documents..."):
                try:
                    retrieved_chunks = retrieve(user_query, top_k=top_k)
                except RuntimeError as e:
                    st.error(f"❌ Retrieval error: {e}")
                    st.info("Make sure you've run ingestion: `python -m src.ingest`")
                    st.stop()
                except ValueError as e:
                    st.warning(str(e))
                    st.stop()

            # ── Generate ──────────────────────────────────────────────────────
            with st.spinner("🤖 Generating answer..."):
                try:
                    answer = generate_answer(user_query, retrieved_chunks)
                except ValueError as e:
                    # Missing API key
                    st.error(f"❌ Configuration error: {e}")
                    st.info(
                        "Add your API key to `.env`:\n```\nLLM_API_KEY=your_key_here\n```"
                    )
                    st.stop()
                except RuntimeError as e:
                    st.error(f"❌ Generation error: {e}")
                    st.stop()

            # ── Display answer ────────────────────────────────────────────────
            st.markdown(answer)

            # ── Show sources + context ────────────────────────────────────────
            message_index = len(st.session_state.messages)  # index of the upcoming assistant msg
            render_sources_and_context(retrieved_chunks, message_index)

        # Save assistant message + retrieval data to session
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.retrieval_data[len(st.session_state.messages) - 1] = retrieved_chunks


if __name__ == "__main__":
    main()

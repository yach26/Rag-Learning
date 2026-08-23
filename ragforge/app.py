"""
app.py — RAGForge Professional Document Q&A Interface
======================================================
ChatGPT & Gemini inspired UI architecture.

Run with:
    streamlit run app.py
"""

import html
import re
import time
from pathlib import Path
import streamlit as st

# ── Page Configuration ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAGForge — Document Intelligence",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject Modern Professional UI Styles (GPT/Gemini Aesthetic) ─────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Global reset & typography */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .stApp {
        background-color: #131314;
        color: #e3e3e3;
    }

    /* Main container bounds */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    .main .block-container {
        max-width: 52rem;
        padding-top: 2rem;
        padding-bottom: 7rem;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1e1e20;
        border-right: 1px solid #2d2e31;
    }

    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #f1f3f4;
        font-weight: 600;
        font-size: 0.95rem;
        letter-spacing: 0.01em;
        text-transform: uppercase;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }

    .sidebar-brand-title {
        font-size: 1.25rem;
        font-weight: 700;
        color: #f1f3f4;
        letter-spacing: -0.02em;
        margin-bottom: 0.15rem;
    }

    .sidebar-brand-sub {
        font-size: 0.8rem;
        color: #8e918f;
        margin-bottom: 1.25rem;
    }

    /* Status Pill */
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.01em;
    }

    .status-ok {
        background-color: rgba(168, 199, 250, 0.12);
        color: #a8c7fa;
        border: 1px solid rgba(168, 199, 250, 0.3);
    }

    .status-warn {
        background-color: rgba(242, 184, 181, 0.12);
        color: #f2b8b5;
        border: 1px solid rgba(242, 184, 181, 0.3);
    }

    /* Welcome / Empty State Grid */
    .welcome-container {
        padding: 2.5rem 1rem 1.5rem 1rem;
        text-align: center;
    }

    .welcome-title {
        font-size: 2.2rem;
        font-weight: 600;
        background: linear-gradient(135deg, #c4c7c5 0%, #ffffff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        letter-spacing: -0.03em;
    }

    .welcome-subtitle {
        color: #8e918f;
        font-size: 0.95rem;
        margin-bottom: 2rem;
    }

    .card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 12px;
        margin-top: 1rem;
    }

    .feature-card {
        background: #1e1e20;
        border: 1px solid #2d2e31;
        border-radius: 12px;
        padding: 16px;
        text-align: left;
        transition: border-color 0.2s ease, background 0.2s ease;
    }

    .feature-card:hover {
        border-color: #444746;
        background: #252629;
    }

    .feature-card-header {
        font-size: 0.88rem;
        font-weight: 600;
        color: #e3e3e3;
        margin-bottom: 4px;
    }

    .feature-card-desc {
        font-size: 0.78rem;
        color: #8e918f;
        line-height: 1.4;
    }

    /* Chat Messages */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 1rem 0 !important;
    }

    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li {
        color: #e3e3e3;
        line-height: 1.7;
        font-size: 0.95rem;
    }

    /* User Message Bubble */
    [data-testid="stChatMessage"][data-tester="user"],
    [data-testid="stChatMessage"]:has([aria-label*="user"]) {
        background-color: transparent !important;
    }

    /* Chat Input Bar */
    [data-testid="stChatInput"] {
        padding-bottom: 1.5rem;
    }

    [data-testid="stChatInput"] textarea {
        background-color: #1e1e20 !important;
        border: 1px solid #333538 !important;
        color: #e3e3e3 !important;
        border-radius: 24px !important;
        padding: 12px 18px !important;
        font-size: 0.95rem !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.2) !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        border-color: #a8c7fa !important;
        box-shadow: 0 0 0 1px #a8c7fa !important;
    }

    /* Source Citation Cards */
    .source-badge {
        display: inline-block;
        background: #28292c;
        border: 1px solid #38393c;
        border-radius: 6px;
        padding: 3px 10px;
        margin: 3px 6px 3px 0;
        font-size: 0.76rem;
        color: #c4c7c5;
        font-family: 'JetBrains Mono', monospace;
    }

    .chunk-box {
        background: #1e1e20;
        border-left: 3px solid #a8c7fa;
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        font-size: 0.84rem;
        color: #c4c7c5;
        line-height: 1.6;
    }

    .meta-badge {
        font-size: 0.74rem;
        color: #8e918f;
        font-family: 'JetBrains Mono', monospace;
    }

    .timing-badge {
        font-size: 0.74rem;
        color: #8e918f;
        font-family: 'JetBrains Mono', monospace;
        margin-top: 10px;
        padding-top: 8px;
        border-top: 1px solid #2d2e31;
    }

    /* UI Controls Polish */
    .stButton button {
        border-radius: 8px !important;
        background-color: #28292c !important;
        border: 1px solid #38393c !important;
        color: #e3e3e3 !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        transition: background 0.15s ease, border-color 0.15s ease !important;
    }

    .stButton button:hover {
        background-color: #333538 !important;
        border-color: #444746 !important;
        color: #ffffff !important;
    }

    /* Hide default Streamlit chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


def _import_modules():
    try:
        from src.retriever import retrieve_with_timing
        from src.generator import generate_answer_stream, generate_answer_with_correction
        from src.vector_store import get_collection_stats, clear_collection
        from src.config import config
        from src.query.rewrite import rewrite_query, normalize_query
        from src.query.expansion import expand_query
        from src.cache import get_cached_answer, set_cached_answer, clear_cache
        from src.guardrails import check_input, check_output
        from src.bm25_store import invalidate_index
        return (
            retrieve_with_timing,
            generate_answer_stream,
            generate_answer_with_correction,
            get_collection_stats,
            clear_collection,
            config,
            rewrite_query,
            normalize_query,
            expand_query,
            get_cached_answer,
            set_cached_answer,
            clear_cache,
            check_input,
            check_output,
            invalidate_index,
        )
    except ImportError as e:
        st.error(f"Initialization Error: {e}\n\nPlease run: `pip install -r requirements.txt`")
        st.stop()


_STRATEGY_HELP = {
    "dense": "Dense vector search using embedding cosine similarity.",
    "bm25": "Lexical BM25 keyword matching for exact terms.",
    "hybrid": "Reciprocal Rank Fusion of Dense and BM25 results.",
    "hybrid_rerank": "Hybrid search refined with CrossEncoder reranking.",
    "multi_query": "Multi-angle query expansion aggregated then reranked.",
    "hyde": "Hypothetical document embedding for abstract questions.",
    "graph_augmented": "Graph entity matching merged with dense retrieval.",
}


def _fmt_score(value, default="—"):
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return default


def render_sidebar(get_collection_stats, clear_collection, invalidate_index, clear_cache, config):
    with st.sidebar:
        st.markdown('<div class="sidebar-brand-title">RAGForge</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-brand-sub">Enterprise Document Intelligence</div>', unsafe_allow_html=True)
        st.divider()

        st.markdown("### Index Status")
        try:
            stats = get_collection_stats()
            chunk_count = stats["total_chunks"]
            if chunk_count == 0:
                st.markdown(
                    '<span class="status-pill status-warn">Index Empty</span>',
                    unsafe_allow_html=True,
                )
                st.caption("No documents indexed. Upload files below or run ingestion.")
            else:
                st.markdown(
                    f'<span class="status-pill status-ok">{chunk_count:,} Chunks Indexed</span>',
                    unsafe_allow_html=True,
                )
                st.caption("Persistent disk store (`ragforge/chroma_db`). Retains vectors across app restarts.")
        except Exception as e:
            st.error(f"Store state unavailable: {e}")

        st.divider()

        st.markdown("### Retrieval Strategy")
        strategies = [
            "dense", "bm25", "hybrid", "hybrid_rerank",
            "multi_query", "hyde", "graph_augmented",
        ]
        strategy_labels = {
            "dense": "Dense (Vector)",
            "bm25": "BM25 (Keyword)",
            "hybrid": "Hybrid (Dense + BM25)",
            "hybrid_rerank": "Hybrid + Reranker",
            "multi_query": "Multi-Query",
            "hyde": "HyDE (Hypothetical)",
            "graph_augmented": "Graph-Augmented",
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

        if strategy == "graph_augmented":
            graph_path = config.PROJECT_ROOT / "data" / "entity_graph.json"
            if not graph_path.exists():
                st.warning("Entity graph not built. Run `python -m src.graph_builder` first.")

        st.divider()

        st.markdown("### Parameters")
        top_k = st.slider(
            "Top Chunks (k)",
            min_value=1,
            max_value=config.TOP_K_MAX,
            value=config.TOP_K,
            help="Number of document chunks retrieved per query.",
        )

        with st.expander("Document Management", expanded=False):
            uploaded_files = st.file_uploader(
                "Upload PDF, Markdown, or TXT",
                type=["pdf", "md", "txt"],
                accept_multiple_files=True,
            )

            if st.button("Process Documents", use_container_width=True):
                if uploaded_files:
                    try:
                        config.DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
                        with st.spinner("Saving documents..."):
                            for uf in uploaded_files:
                                dest = config.DOCUMENTS_DIR / uf.name
                                dest.write_bytes(uf.getbuffer())

                        with st.spinner("Ingesting and indexing..."):
                            from src.ingest import run_ingestion_pipeline
                            run_ingestion_pipeline()
                        st.success("Ingestion complete.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ingestion error: {e}")
                else:
                    st.warning("Upload at least one file.")

            delete_source_files = st.checkbox(
                "Also delete document files from disk",
                value=False,
                help="Check this to remove raw document files from data/documents/",
            )

            if st.button("Purge Vector Store", use_container_width=True):
                try:
                    clear_collection()
                    invalidate_index()
                    clear_cache()

                    if config.HASH_STORE_PATH.exists():
                        config.HASH_STORE_PATH.unlink()

                    graph_path = config.PROJECT_ROOT / "data" / "entity_graph.json"
                    if graph_path.exists():
                        graph_path.unlink()

                    if delete_source_files and config.DOCUMENTS_DIR.exists():
                        for f in config.DOCUMENTS_DIR.iterdir():
                            if f.is_file() and f.name != ".gitkeep":
                                f.unlink()

                    st.success("Database purged successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Purge error: {e}")

        st.divider()

        st.markdown("### RAG Pipeline Controls")
        enable_rewrite = st.checkbox(
            "Conversational Rewriting",
            value=True,
            help="Rewrite follow-up questions into standalone queries.",
        )
        enable_expansion = st.checkbox(
            "Query Expansion",
            value=False,
            help="Generate synonym expansions before search.",
        )
        enable_correction = st.checkbox(
            "Self-Correction",
            value=False,
            help="Evaluate answer draft accuracy before presentation.",
        )
        enable_cache = st.checkbox(
            "Response Cache",
            value=True,
            help="Serve identical queries instantly from cache.",
        )
        enable_guardrails = st.checkbox(
            "Safety Guardrails",
            value=True,
            help="Block prompt injection and unsafe content.",
        )

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Cache", use_container_width=True):
                clear_cache()
                st.success("Cache cleared.")
        with col2:
            if st.button("Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.retrieval_data = {}
                st.session_state.timing_data = {}
                st.session_state.rewritten_queries = {}
                st.rerun()

    return top_k, strategy, enable_rewrite, enable_expansion, enable_correction, enable_cache, enable_guardrails


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


def sanitize_mermaid_code(code: str) -> str:
    """Pre-process Mermaid diagram code to fix common LLM syntax errors."""
    if not code:
        return code

    # Normalize non-standard Unicode hyphens, dashes, and smart quotes per line
    # so they don't break word-boundary anchors later
    replacements = [
        ("\u2011", "-"),  # non-breaking hyphen
        ("\u2013", "-"),  # en dash
        ("\u2014", "-"),  # em dash
        ("\u201c", '"'),  # left double quote
        ("\u201d", '"'),  # right double quote
        ("\u2018", "'"),  # left single quote
        ("\u2019", "'"),  # right single quote
    ]
    for bad, good in replacements:
        code = code.replace(bad, good)

    # Quote any unquoted bracket label that contains parentheses.
    # Matches: ID[some text (with parens) more text]  -->  ID["some text (with parens) more text"]
    # The node ID can be any non-whitespace chars up to the '['.
    # We skip labels that are already quoted (start with ").
    def _quote_label(m: re.Match) -> str:
        node_id = m.group(1)
        label = m.group(2)
        return f'{node_id}["{label}"]'

    code = re.sub(
        r'([A-Za-z0-9_][A-Za-z0-9_-]*)\[([^"\]\n]*\([^"\]\n]*\)[^"\]\n]*)\]',
        _quote_label,
        code,
    )
    return code


def render_mermaid_chart(code: str):
    code = sanitize_mermaid_code(code.strip())
    if not code:
        return

    if hasattr(st, "mermaid_chart"):
        try:
            st.mermaid_chart(code)
            return
        except Exception:
            pass

    # Safely format JS string template literal
    js_code = code.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    mermaid_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #1e1e20;
                color: #e3e3e3;
                font-family: 'Inter', system-ui, -apple-system, sans-serif;
            }}
            .mermaid-container {{
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 16px;
                background-color: #1e1e20;
                border: 1px solid #333538;
                border-radius: 8px;
                box-sizing: border-box;
                min-height: 140px;
            }}
            #graphDiv {{
                width: 100%;
                display: flex;
                justify-content: center;
            }}
            svg {{
                max-width: 100% !important;
                height: auto !important;
            }}
            .error-box {{
                color: #f2b8b5;
                font-size: 0.82rem;
                font-family: monospace;
                padding: 10px;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>
        <div class="mermaid-container">
            <div id="graphDiv">Rendering diagram...</div>
        </div>
        <script>
            (function() {{
                try {{
                    mermaid.initialize({{
                        startOnLoad: false,
                        theme: 'dark',
                        securityLevel: 'loose'
                    }});
                    const rawCode = `{js_code}`;
                    const id = 'mermaid_' + Math.random().toString(36).substring(2, 7);
                    mermaid.render(id, rawCode)
                        .then(function(result) {{
                            document.getElementById('graphDiv').innerHTML = result.svg;
                        }})
                        .catch(function(err) {{
                            console.error("Mermaid render error:", err);
                            document.getElementById('graphDiv').innerHTML = 
                                '<div class="error-box">Diagram Render Note:<br>' + (err.str || err.message || err) + '</div>';
                        }});
                }} catch (e) {{
                    console.error("Mermaid init error:", e);
                    document.getElementById('graphDiv').innerHTML = 
                        '<div class="error-box">Diagram Init Error:<br>' + e.message + '</div>';
                }}
            }})();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(mermaid_html, height=420, scrolling=True)


def render_message_content(content: str):
    if not content:
        return

    pattern = r"(```\s*mermaid[\s\S]*?```)"
    if not re.search(pattern, content, re.IGNORECASE):
        st.markdown(content)
        return

    parts = re.split(pattern, content, flags=re.IGNORECASE)
    for part in parts:
        if not part:
            continue
        if re.match(r"^```\s*mermaid", part, re.IGNORECASE):
            match = re.search(r"```\s*mermaid\s*\n?([\s\S]*?)\n?```", part, re.IGNORECASE)
            if match:
                render_mermaid_chart(match.group(1).strip())
            else:
                st.markdown(part)
        else:
            st.markdown(part)


def render_chat_history():
    for i, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            render_message_content(message["content"])

            if message["role"] == "user" and i in st.session_state.rewritten_queries:
                rewritten = st.session_state.rewritten_queries[i]
                if rewritten != message["content"]:
                    st.caption(f"Standalone Query: *{rewritten}*")

            if message["role"] == "assistant" and i in st.session_state.retrieval_data:
                render_sources_and_context(st.session_state.retrieval_data[i])
                if i in st.session_state.timing_data:
                    render_timing(st.session_state.timing_data[i])


def render_timing(timing: dict):
    strategy_label = timing.get("strategy", "hybrid")
    st.markdown(
        f"<div class='timing-badge'>"
        f"strategy: <b>{html.escape(strategy_label)}</b> · "
        f"retrieval: {timing['retrieval_ms']} ms · "
        f"generation: {timing['generation_ms']} ms"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_sources_and_context(retrieved_chunks: list):
    if not retrieved_chunks:
        return

    source_strings = []
    seen = set()
    for chunk in retrieved_chunks:
        source = html.escape(str(chunk.get("source", "unknown")))
        page = html.escape(str(chunk.get("page", "?")))
        key = f"{source}__p{page}"
        if key not in seen:
            seen.add(key)
            source_strings.append(
                f'<span class="source-badge">{source} · p.{page}</span>'
            )

    st.markdown("<div style='margin-top: 0.8rem;'><b>Sources</b></div>", unsafe_allow_html=True)
    st.markdown(" ".join(source_strings), unsafe_allow_html=True)

    with st.expander(f"Inspect Context ({len(retrieved_chunks)} Chunks)", expanded=False):
        from src.config import config as _cfg
        preview_len = _cfg.MAX_CHUNK_PREVIEW_CHARS

        for i, chunk in enumerate(retrieved_chunks, start=1):
            source = html.escape(str(chunk.get("source", "?")))
            page = html.escape(str(chunk.get("page", "?")))
            dist_str = _fmt_score(chunk.get("distance")) if "distance" in chunk else "—"
            score_str = _fmt_score(chunk.get("rerank_score")) if "rerank_score" in chunk else "—"

            raw_text = chunk.get("text", "")
            text = html.escape(raw_text[:preview_len])
            suffix = "..." if len(raw_text) > preview_len else ""

            st.markdown(
                f"<div class='chunk-box'>"
                f"<b>Chunk {i}</b> &nbsp;·&nbsp; "
                f"<span class='meta-badge'>distance: {dist_str} | rerank: {score_str}</span><br>"
                f"<b>Source:</b> {source} &nbsp;·&nbsp; <b>Page:</b> {page}<br><br>"
                f"{text}{suffix}"
                f"</div>",
                unsafe_allow_html=True,
            )


def main():
    (
        retrieve_with_timing,
        generate_answer_stream,
        generate_answer_with_correction,
        get_collection_stats,
        clear_collection,
        config,
        rewrite_query,
        normalize_query,
        expand_query,
        get_cached_answer,
        set_cached_answer,
        clear_cache,
        check_input,
        check_output,
        invalidate_index,
    ) = _import_modules()

    init_session_state()

    top_k, strategy, enable_rewrite, enable_expansion, enable_correction, enable_cache, enable_guardrails = (
        render_sidebar(get_collection_stats, clear_collection, invalidate_index, clear_cache, config)
    )

    if not st.session_state.messages:
        st.markdown(
            '<div class="welcome-container">'
            '<div class="welcome-title">What would you like to know?</div>'
            '<div class="welcome-subtitle">Ask questions grounded directly in your indexed document knowledge base.</div>'
            '<div class="card-grid">'
            '<div class="feature-card">'
            '<div class="feature-card-header">Dense Vector Search</div>'
            '<div class="feature-card-desc">Semantic matching using SentenceTransformer embedding similarity.</div>'
            '</div>'
            '<div class="feature-card">'
            '<div class="feature-card-header">Hybrid + Reranker</div>'
            '<div class="feature-card-desc">Reciprocal Rank Fusion with CrossEncoder relevance scoring.</div>'
            '</div>'
            '<div class="feature-card">'
            '<div class="feature-card-header">Multi-Query Expansion</div>'
            '<div class="feature-card-desc">Generates alternative phrasings for high-recall retrieval.</div>'
            '</div>'
            '<div class="feature-card">'
            '<div class="feature-card-header">Graph-Augmented RAG</div>'
            '<div class="feature-card-desc">Combines entity relationships with vector search context.</div>'
            '</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    render_chat_history()

    if user_query := st.chat_input("Ask RAGForge a question..."):
        if not user_query.strip():
            st.warning("Please enter a question.")
            st.stop()

        with st.spinner("Processing query..."):
            rewritten_query = user_query
            if enable_rewrite:
                rewritten_query = rewrite_query(
                    user_query,
                    st.session_state.messages,
                    max_turns=config.CONVERSATION_HISTORY_TURNS,
                )

            spellchecked_query = normalize_query(rewritten_query)
            final_query = spellchecked_query
            if enable_expansion:
                final_query = expand_query(spellchecked_query)

        user_msg_index = len(st.session_state.messages)
        st.session_state.messages.append({"role": "user", "content": user_query})
        st.session_state.rewritten_queries[user_msg_index] = final_query

        with st.chat_message("user"):
            st.markdown(user_query)

        if enable_guardrails:
            is_safe, error_msg = check_input(user_query)
            if not is_safe:
                with st.chat_message("assistant"):
                    st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                st.stop()

        retrieved_chunks = []
        retrieval_ms = 0
        generation_ms = None
        answer = ""

        with st.chat_message("assistant"):
            cached_ans = None
            if enable_cache:
                cached_ans = get_cached_answer(user_query, strategy)

            if cached_ans:
                st.caption("Served from Cache")
                generation_ms = 0
                st.markdown(cached_ans)
                answer = cached_ans
            else:
                if final_query != user_query:
                    st.caption(f"Optimized Query: *{final_query}*")

                with st.spinner(f"Retrieving context ({strategy})..."):
                    try:
                        retrieved_chunks, retrieval_meta = retrieve_with_timing(
                            final_query, top_k=top_k, strategy=strategy
                        )
                        retrieval_ms = retrieval_meta["total_ms"]
                    except (RuntimeError, ValueError) as e:
                        answer = f"Retrieval error: {e}"
                        st.error(answer)
                    except Exception as e:
                        answer = f"Unexpected retrieval error: {e}"
                        st.error(answer)

                if not answer:
                    with st.spinner("Generating answer..."):
                        t0 = time.perf_counter()
                        try:
                            if enable_correction:
                                answer_stream = generate_answer_with_correction(
                                    final_query, retrieved_chunks, st.session_state.messages[:-1]
                                )
                            else:
                                answer_stream = generate_answer_stream(
                                    final_query, retrieved_chunks, st.session_state.messages[:-1]
                                )

                            stream_container = st.empty()
                            with stream_container:
                                answer = st.write_stream(answer_stream)
                            generation_ms = round((time.perf_counter() - t0) * 1000)

                            if enable_guardrails and answer and not answer.startswith("Configuration error"):
                                is_safe, error_msg = check_output(answer)
                                if not is_safe:
                                    st.error(error_msg)
                                    answer = error_msg

                            if enable_cache and answer and not answer.lower().startswith("configuration error"):
                                set_cached_answer(user_query, strategy, answer)

                            # Re-render using render_message_content so Mermaid blocks
                            # are replaced with the actual rendered diagram.
                            stream_container.empty()
                            render_message_content(answer)

                        except ValueError as e:
                            answer = (
                                f"Configuration Error: {e}\n\n"
                                "Add your API key to `.env`:\n```\nGROQ_API_KEY=your_key_here\n```"
                            )
                            st.error(answer)
                        except RuntimeError as e:
                            answer = f"Generation Error: {e}"
                            st.error(answer)

                if retrieved_chunks:
                    render_sources_and_context(retrieved_chunks)
                    if generation_ms is not None:
                        render_timing({
                            "strategy": strategy,
                            "retrieval_ms": retrieval_ms,
                            "generation_ms": generation_ms,
                        })

        if answer:
            msg_index = len(st.session_state.messages)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.session_state.retrieval_data[msg_index] = retrieved_chunks
            if retrieved_chunks and generation_ms is not None:
                st.session_state.timing_data[msg_index] = {
                    "strategy": strategy,
                    "retrieval_ms": retrieval_ms,
                    "generation_ms": generation_ms,
                }


if __name__ == "__main__":
    main()

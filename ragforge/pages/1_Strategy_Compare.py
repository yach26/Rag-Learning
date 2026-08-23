"""
pages/1_Strategy_Compare.py — Side-by-side retrieval latency dashboard
"""

import time
import streamlit as st

st.set_page_config(page_title="RAGForge — Strategy Compare", layout="wide")
st.title("Strategy comparison")
st.caption("Runs retrieval only (no generation). Use this to ablate latency vs hit quality.")

query = st.text_input("Query", placeholder="Ask something grounded in your documents")
top_k = st.slider("top_k", 1, 15, 5)
strategies = st.multiselect(
    "Strategies",
    ["dense", "bm25", "hybrid", "hybrid_rerank", "multi_query", "hyde", "graph_augmented"],
    default=["dense", "bm25", "hybrid", "hybrid_rerank"],
)

run = st.button("Run comparison", type="primary")
if run and not query.strip():
    st.warning("Enter a query first.")
elif run:
    from src.retriever import retrieve_with_timing

    rows = []
    cols = st.columns(max(len(strategies), 1))
    for i, strategy in enumerate(strategies):
        with cols[i]:
            st.subheader(strategy)
            t0 = time.perf_counter()
            try:
                chunks, meta = retrieve_with_timing(query, top_k=top_k, strategy=strategy)
                elapsed = meta["total_ms"]
                st.metric("Latency", f"{elapsed} ms")
                st.metric("Chunks", len(chunks))
                for c in chunks:
                    st.caption(f"{c.get('source')} p.{c.get('page')}  id={c.get('chunk_id')}")
                    st.write((c.get("text") or "")[:240] + "…")
                rows.append({"strategy": strategy, "latency_ms": elapsed, "chunks": len(chunks)})
            except Exception as e:
                st.error(str(e))
                rows.append({
                    "strategy": strategy,
                    "latency_ms": round((time.perf_counter() - t0) * 1000),
                    "chunks": 0,
                })
    if rows:
        st.divider()
        st.dataframe(rows, use_container_width=True)

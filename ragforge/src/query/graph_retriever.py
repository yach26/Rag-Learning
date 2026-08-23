"""
src/query/graph_retriever.py — Graph RAG Query Lookup
=======================================================

During retrieval, this module uses the LLM to extract entities from the
user's query. It then looks up those entities in the offline-built
entity_graph.json to find associated chunk IDs.

Finally, it fetches those exact chunks directly from ChromaDB. These
chunks are guaranteed to mention the entities in the user's query,
acting as a high-precision supplement to dense vector retrieval.
"""

import json
import logging
from typing import List, Dict, Any

from src.config import config
from src.vector_store import _get_collection
from src.llm import get_llm

logger = logging.getLogger("RAGForge.GraphRetriever")

GRAPH_FILE_PATH = config.PROJECT_ROOT / "data" / "entity_graph.json"

_EXTRACT_QUERY_ENTITIES_PROMPT = """\
Extract the named entities from the following user question.
Focus ONLY on People, Organizations, Technologies, and specific Locations.
Output a comma-separated list. If none, output exactly: NONE

Question: {query}
Entities:"""


def get_graph_chunks(query: str) -> List[Dict[str, Any]]:
    """
    Extracts entities from the query, looks them up in the entity graph,
    and returns the corresponding chunks directly from the vector store.
    """
    if not GRAPH_FILE_PATH.exists():
        logger.warning(f"Graph file {GRAPH_FILE_PATH} not found. Run python -m src.graph_builder first.")
        return []
        
    try:
        prompt = _EXTRACT_QUERY_ENTITIES_PROMPT.format(query=query.strip())
        output = get_llm().complete(prompt).strip()
        if output == "NONE":
            return []
            
        query_entities = [e.strip().lower() for e in output.split(",") if e.strip()]
        logger.info(f"Graph query extracted entities: {query_entities}")
        
        # Load the graph
        with GRAPH_FILE_PATH.open("r", encoding="utf-8") as f:
            entity_graph = json.load(f)
            
        # Find matching chunk IDs
        chunk_ids_to_fetch = set()
        for entity in query_entities:
            # We do a simple substring match to be forgiving with query entities
            # e.g., if query entity is "apollo" and graph has "apollo project"
            for graph_entity, ids in entity_graph.items():
                if entity in graph_entity or graph_entity in entity:
                    chunk_ids_to_fetch.update(ids)
                    
        if not chunk_ids_to_fetch:
            logger.info("No matching entities found in the graph.")
            return []
            
        # Fetch the chunks from Chroma
        collection = _get_collection()
        data = collection.get(
            ids=list(chunk_ids_to_fetch),
            include=["documents", "metadatas"]
        )
        
        results = []
        for i in range(len(data["ids"])):
            meta = data["metadatas"][i] or {}
            results.append({
                "id": data["ids"][i],
                "text": data["documents"][i],
                "source": meta.get("source", "Unknown"),
                "page": meta.get("page", 1),
                "retrieval_method": "graph",
                # Give graph hits a fake high score so they survive RRF if we use it,
                # though usually we just append them.
                "graph_score": 1.0, 
            })
            
        logger.info(f"Graph retrieval found {len(results)} chunks for entities.")
        return results

    except Exception as e:
        logger.warning(f"Graph retrieval failed ({e}) — skipping graph augmentation.")
        return []

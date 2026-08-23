"""
src/graph_builder.py — Offline Entity Extraction for Graph RAG
==============================================================

This script iterates over all existing document chunks in ChromaDB,
uses the LLM to extract named entities (People, Orgs, Tech, etc.),
and saves the mapping (Entity -> List of Chunk IDs) to a JSON file.

This creates a lightweight "Knowledge Graph" without needing Neo4j.
During retrieval, if a user mentions an entity, we can instantly
look up every single chunk that mentions that entity to guarantee
100% recall for that specific entity, bypassing vector similarity issues.

Usage:
    cd ragforge
    python -m src.graph_builder
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from tqdm import tqdm

from src.config import config
from src.vector_store import _get_collection
from src.llm import get_llm

# Setup logging for the script
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("RAGForge.GraphBuilder")

GRAPH_FILE_PATH = config.PROJECT_ROOT / "data" / "entity_graph.json"

_EXTRACT_ENTITIES_PROMPT = """\
Extract the most important named entities from the following text.
Focus ONLY on:
- People (e.g. John Doe, Alice)
- Organizations (e.g. Google, NASA, HR Department)
- Technologies/Products (e.g. Python, Apollo, iPhone)
- Specific Locations (e.g. New York, Mars)

Rules:
- Output a comma-separated list of entities.
- Do NOT output any other text or explanation.
- If there are no relevant entities, output exactly: NONE
- Normalize names (e.g., if you see "John" and "John Doe", just output "John Doe").

Text:
{text}

Entities:"""


def build_graph():
    collection = _get_collection()
    data = collection.get(include=["documents", "metadatas"])
    
    ids = data["ids"]
    documents = data["documents"]
    
    if not ids:
        logger.warning("No documents found in ChromaDB. Run ingest first.")
        return

    logger.info(f"Extracting entities from {len(ids)} chunks...")
    
    llm = get_llm()

    # entity -> list of chunk_ids
    entity_graph = defaultdict(list)
    
    # Load existing if available so we can skip (or just overwrite)
    if GRAPH_FILE_PATH.exists():
        with GRAPH_FILE_PATH.open("r", encoding="utf-8") as f:
            entity_graph = defaultdict(list, json.load(f))
            logger.info(f"Loaded existing graph with {len(entity_graph)} entities.")
            # For a real system we'd track which chunks we've already processed, 
            # but for this benchmark we will just overwrite/append.
            # To make it clean, we'll just rebuild from scratch here.
            entity_graph.clear()
            logger.info("Rebuilding graph from scratch...")

    for i in tqdm(range(len(ids)), desc="Building Entity Graph"):
        chunk_id = ids[i]
        text = documents[i]
        
        prompt = _EXTRACT_ENTITIES_PROMPT.format(text=text)
        
        try:
            output = llm.complete(prompt).strip()
            if output == "NONE":
                continue
                
            entities = [e.strip() for e in output.split(",") if e.strip()]
            
            for entity in entities:
                # Normalize to lowercase for case-insensitive lookup later
                norm_entity = entity.lower()
                if chunk_id not in entity_graph[norm_entity]:
                    entity_graph[norm_entity].append(chunk_id)
                    
        except Exception as e:
            logger.error(f"Failed to extract entities for chunk {chunk_id}: {e}")
            
    # Save the graph
    GRAPH_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with GRAPH_FILE_PATH.open("w", encoding="utf-8") as f:
        json.dump(dict(entity_graph), f, indent=2)
        
    logger.info(f"Graph built successfully! {len(entity_graph)} unique entities saved to {GRAPH_FILE_PATH}")


if __name__ == "__main__":
    build_graph()

from typing import Dict, List, Any
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.orm import Session
from configs.logfire_config import setup_logger
from db.database import get_db_context
from db.models import Summaries

logger = setup_logger(__name__)

# Initialize the embedding model
try:
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    logger.info("SentenceTransformer model loaded successfully")
except Exception as e:
    logger.error(f"Error loading SentenceTransformer model: {str(e)}")
    model = None

# Constants
TOP_K_DEFAULT = 5

def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for the given text using sentence-transformers.
    
    Args:
        text: The text to embed
        
    Returns:
        List[float]: The embedding vector
    """
    if not model:
        logger.error("SentenceTransformer model not loaded")
        return []
    
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        return []

def upsert_summary(summary: str, metadata: Dict[str, Any]) -> Dict:
    """
    Upsert (insert or update) a summary document to pgvector.
    
    Args:
        summary: The summary text to embed
        metadata: Associated metadata for the document including username and optionally user_id and run_id
        
    Returns:
        Dict: Result of the upsert operation
    """
    if not summary or not isinstance(summary, str):
        logger.error("Invalid summary provided for upserting")
        return {"status": "error", "message": "Invalid summary provided"}
    
    if not model:
        logger.error("SentenceTransformer model not initialized. Cannot upsert summary.")
        return {"status": "error", "message": "SentenceTransformer model not initialized"}
    
    try:
        # Generate embedding
        embedding = get_embedding(summary)
        if not embedding:
            logger.error("Failed to generate embedding for summary")
            return {"status": "error", "message": "Failed to generate embedding"}
        
        # Extract metadata
        username = metadata.get("username", "unknown")
        user_id = metadata.get("user_id")
        run_id = metadata.get("run_id")
        document_type = metadata.get("document_type", "summary")
        
        # Generate a unique document path
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d%H%M%S')
        doc_path = f"summaries/{username}/{timestamp_str}"
        
        with get_db_context() as db:
            # Check if there's already a summary for this username and delete it
            # This maintains the "latest only" behavior from the original service
            existing_summary = db.query(Summaries).filter(
                Summaries.username == username
            ).first()
            
            if existing_summary:
                logger.info(f"Deleting existing summary for {username}")
                db.delete(existing_summary)
                db.commit()
            
            # Insert new summary
            new_summary = Summaries(
                path=doc_path,
                username=username,
                user_id=user_id,
                run_id=run_id,
                document_type=document_type,
                timestamp=timestamp,
                content=summary,
                image_url=None,
                page_index=None,
                embedding=embedding
            )
            
            db.add(new_summary)
            db.commit()
            
            logger.info(f"Successfully upserted summary for {username}")
            return {
                "status": "success",
                "message": f"Document successfully added to summaries table",
                "document_id": new_summary.id
            }
    
    except Exception as e:
        logger.error(f"Error upserting summary: {str(e)}")
        return {"status": "error", "message": str(e)}

def search_matching_summaries(summary_to_search: str, top_k: int = TOP_K_DEFAULT) -> List[Dict]:
    """
    Search for summaries similar to the provided summary using pgvector.

    Args:
        summary_to_search: The summary text to search for
        top_k: Maximum number of results to return

    Returns:
        List[Dict]: Search results
    """
    if not summary_to_search or not isinstance(summary_to_search, str):
        logger.error("Invalid search query provided")
        return []

    if not model:
        logger.error("SentenceTransformer model not initialized. Cannot search summaries.")
        return []

    try:
        # Generate embedding for the search query
        query_embedding = get_embedding(summary_to_search)
        if not query_embedding:
            logger.error("Failed to generate embedding for search query")
            return []

        # Convert embedding to pgvector-compatible literal
        embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

        with get_db_context() as db:
            query = text("""
                SELECT id, path, username, user_id, run_id, document_type, timestamp, content, image_url, page_index,
                       embedding <=> (:embedding)::vector AS distance
                FROM summaries
                WHERE content IS NOT NULL
                ORDER BY embedding <=> (:embedding)::vector
                LIMIT :limit
            """)

            results = db.execute(query, {
                "embedding": embedding_str,
                "limit": top_k
            }).fetchall()

            transformed_results = []
            for row in results:
                metadata = {
                    "username": row.username,
                    "user_id": row.user_id,
                    "run_id": row.run_id,
                    "document_type": row.document_type,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                    "path": row.path
                }

                item = {
                    "id": row.id,
                    "metadata": metadata,
                    "text": row.content,
                    "distance": float(row.distance)
                }

                item["model_dump"] = lambda meta=metadata: {"metadata": meta}
                transformed_results.append(item)

            logger.info(f"Found {len(transformed_results)} matching summaries for search query")
            return transformed_results

    except Exception as e:
        logger.error(f"Error searching summaries: {str(e)}")
        return []

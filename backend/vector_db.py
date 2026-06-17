"""
Vector Database Client
Abstraction layer for ChromaDB
"""

import logging
from typing import List, Dict, Optional, Any
import uuid
import os

logger = logging.getLogger(__name__)

class VectorDBClient:
    """Unified vector database client supporting Chroma"""

    _provider = "chroma"
    _client = None
    _collection = None

    @classmethod
    def init(cls, provider: str = "chroma", api_key: str = None):
        cls._provider = "chroma"
        
        try:
            import chromadb
            # Use persistent client in the current directory
            db_path = os.path.join(os.path.dirname(__file__), "chroma_db")
            cls._client = chromadb.PersistentClient(path=db_path)
            
            # Get or create collection
            cls._collection = cls._client.get_or_create_collection(
                name="knowledge_vault",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB client initialized")

        except ImportError:
            raise RuntimeError("chromadb package not installed. Install with: pip install chromadb")
        except Exception as e:
            logger.error(f"ChromaDB initialization failed: {e}")
            raise

    @classmethod
    def health_check(cls) -> bool:
        try:
            return cls._collection is not None
        except Exception as e:
            logger.error(f"Vector DB health check failed: {e}")
            return False

    @classmethod
    def upsert(
        cls,
        link_id: str,
        user_id: str,
        vector: List[float],
        metadata: Dict[str, Any]
    ) -> str:
        try:
            vector_id = f"link_{link_id}"
            metadata["link_id"] = link_id
            metadata["user_id"] = user_id

            # ChromaDB upsert
            cls._collection.upsert(
                ids=[vector_id],
                embeddings=[vector],
                metadatas=[metadata]
            )

            logger.info(f"Upserted vector {vector_id}")
            return vector_id

        except Exception as e:
            logger.error(f"Vector upsert failed: {e}")
            raise

    @classmethod
    def search(
        cls,
        query_vector: List[float],
        user_id: str,
        top_k: int = 5,
        threshold: float = 0.5
    ) -> List[Dict]:
        try:
            results = []

            response = cls._collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where={"user_id": user_id}
            )

            if not response["ids"] or not response["ids"][0]:
                return []

            for idx, id_val in enumerate(response["ids"][0]):
                # ChromaDB distance is returned. For cosine, smaller is better (often 1-cosine)
                # But let's just return what we have
                distance = response["distances"][0][idx] if "distances" in response and response["distances"] else 0.0
                metadata = response["metadatas"][0][idx] if "metadatas" in response and response["metadatas"] else {}
                
                results.append({
                    "id": id_val,
                    "score": 1.0 - distance, # Rough estimate to match 0-1 similarity 
                    "metadata": metadata
                })

            logger.info(f"Search found {len(results)} results for user {user_id}")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise

    @classmethod
    def delete(cls, link_id: str, user_id: str) -> bool:
        try:
            vector_id = f"link_{link_id}"
            cls._collection.delete(
                ids=[vector_id],
                where={"user_id": user_id}
            )
            logger.info(f"Deleted vector {vector_id}")
            return True

        except Exception as e:
            logger.error(f"Vector deletion failed: {e}")
            return False

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        try:
            return {
                "total_vectors": cls._collection.count(),
                "provider": "chroma"
            }
        except Exception as e:
            logger.error(f"Stats retrieval failed: {e}")
            return {"error": str(e)}

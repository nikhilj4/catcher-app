"""
Vector Database Client
Abstraction layer for Pinecone and Qdrant vector databases
"""

import logging
from typing import List, Dict, Optional, Any
import uuid

logger = logging.getLogger(__name__)


class VectorDBClient:
    """Unified vector database client supporting Pinecone and Qdrant"""

    _instance = None
    _provider = None
    _client = None

    @classmethod
    def init(cls, provider: str = "pinecone", api_key: str = None):
        """
        Initialize vector database client.

        Args:
            provider: "pinecone" or "qdrant"
            api_key: API key for the provider
        """
        cls._provider = provider.lower()

        if cls._provider == "pinecone":
            cls._init_pinecone(api_key)
        elif cls._provider == "qdrant":
            cls._init_qdrant(api_key)
        else:
            raise ValueError(f"Unsupported vector DB provider: {provider}")

        logger.info(f"Vector DB client initialized ({cls._provider})")

    @classmethod
    def _init_pinecone(cls, api_key: str):
        """Initialize Pinecone client"""
        try:
            import pinecone

            pinecone.init(
                api_key=api_key,
                environment="prod-......"  # Update with your environment
            )

            # Get or create index
            index_name = "knowledge-vault"
            pinecone.create_index(
                name=index_name,
                dimension=1536,  # text-embedding-3-small
                metric="cosine",
                metadata_config={
                    "indexed": ["user_id", "platform", "category"]
                }
            )

            cls._client = pinecone.Index(index_name)
            logger.info("Pinecone client initialized")

        except ImportError:
            raise RuntimeError("pinecone package not installed. Install with: pip install pinecone-client")
        except Exception as e:
            logger.error(f"Pinecone initialization failed: {e}")
            raise

    @classmethod
    def _init_qdrant(cls, api_key: str):
        """Initialize Qdrant client"""
        try:
            from qdrant_client import QdrantClient

            cls._client = QdrantClient(
                url="http://localhost:6333",  # Qdrant server URL
                api_key=api_key
            )

            # Create collection if not exists
            try:
                cls._client.get_collection("knowledge_vault")
            except Exception:
                from qdrant_client.models import Distance, VectorParams

                cls._client.create_collection(
                    collection_name="knowledge_vault",
                    vectors_config=VectorParams(
                        size=1536,  # text-embedding-3-small
                        distance=Distance.COSINE
                    )
                )

            logger.info("Qdrant client initialized")

        except ImportError:
            raise RuntimeError("qdrant-client package not installed. Install with: pip install qdrant-client")
        except Exception as e:
            logger.error(f"Qdrant initialization failed: {e}")
            raise

    @classmethod
    def health_check(cls) -> bool:
        """Check if vector DB is healthy"""
        try:
            if cls._provider == "pinecone":
                return cls._client is not None
            elif cls._provider == "qdrant":
                cls._client.get_collections()
                return True
            return False
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
        """
        Upsert vector with metadata to vector database.

        Args:
            link_id: Link ID (unique identifier)
            user_id: User ID (for filtering)
            vector: 1536-dimensional embedding vector
            metadata: Metadata dict {title, platform, tags, category, etc}

        Returns:
            Vector ID in the database
        """
        try:
            vector_id = f"link_{link_id}"

            # Add user_id to metadata for filtering
            metadata["link_id"] = link_id
            metadata["user_id"] = user_id

            if cls._provider == "pinecone":
                cls._client.upsert(
                    vectors=[(vector_id, vector, metadata)],
                    namespace=user_id  # Namespace per user for isolation
                )
            elif cls._provider == "qdrant":
                from qdrant_client.models import PointStruct

                point = PointStruct(
                    id=hash(vector_id) % (2**31),  # Convert to positive int
                    vector=vector,
                    payload=metadata
                )
                cls._client.upsert(
                    collection_name="knowledge_vault",
                    points=[point]
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
        """
        Search vector database with semantic similarity.

        Args:
            query_vector: Query embedding vector (1536 dims)
            user_id: User ID (for filtering results)
            top_k: Number of results to return
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            List of {id, score, metadata} results
        """
        try:
            results = []

            if cls._provider == "pinecone":
                response = cls._client.query(
                    vector=query_vector,
                    top_k=top_k,
                    namespace=user_id,
                    include_metadata=True,
                    filter={"user_id": {"$eq": user_id}}
                )

                for match in response.matches:
                    if match.score >= threshold:
                        results.append({
                            "id": match.id,
                            "score": match.score,
                            "metadata": match.metadata or {}
                        })

            elif cls._provider == "qdrant":
                response = cls._client.search(
                    collection_name="knowledge_vault",
                    query_vector=query_vector,
                    query_filter={
                        "must": [
                            {
                                "key": "user_id",
                                "match": {"value": user_id}
                            }
                        ]
                    },
                    limit=top_k,
                    score_threshold=threshold
                )

                for point in response:
                    results.append({
                        "id": str(point.id),
                        "score": point.score,
                        "metadata": point.payload or {}
                    })

            logger.info(f"Search found {len(results)} results for user {user_id}")
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise

    @classmethod
    def delete(cls, link_id: str, user_id: str) -> bool:
        """Delete vector for a link"""
        try:
            vector_id = f"link_{link_id}"

            if cls._provider == "pinecone":
                cls._client.delete(
                    ids=[vector_id],
                    namespace=user_id
                )
            elif cls._provider == "qdrant":
                # Qdrant delete by payload filter
                cls._client.delete(
                    collection_name="knowledge_vault",
                    points_selector={
                        "filter": {
                            "must": [
                                {"key": "link_id", "match": {"value": link_id}},
                                {"key": "user_id", "match": {"value": user_id}}
                            ]
                        }
                    }
                )

            logger.info(f"Deleted vector {vector_id}")
            return True

        except Exception as e:
            logger.error(f"Vector deletion failed: {e}")
            return False

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """Get vector database statistics"""
        try:
            if cls._provider == "pinecone":
                index_stats = cls._client.describe_index_stats()
                return {
                    "total_vectors": index_stats.total_vector_count,
                    "dimension": index_stats.dimension,
                    "index_fullness": index_stats.index_fullness
                }
            elif cls._provider == "qdrant":
                collection_info = cls._client.get_collection("knowledge_vault")
                return {
                    "total_vectors": collection_info.points_count,
                    "dimension": 1536
                }
            return {}
        except Exception as e:
            logger.error(f"Stats retrieval failed: {e}")
            return {"error": str(e)}

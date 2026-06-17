"""
Knowledge Vault - Production-Grade FastAPI Backend
Integrates web scraping, PostgreSQL, LLM enrichment, and vector search
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session

import sys
sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, shutdown_db, get_db, DatabaseEngine, get_db_stats
from models import User, Link, SearchQuery, Embedding, AuditLog
from linkvault import detect_platform, extract, _extract_full_content
from llm_integration import (
    enrich_link_with_llm,
    generate_embeddings,
    rag_search_response
)
from vector_db import VectorDBClient
from background_tasks import background_enrichment_queue
from middleware import AuthMiddleware, RateLimitMiddleware

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# LIFESPAN MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Knowledge Vault API starting...")
    init_db(environment=os.getenv("ENVIRONMENT", "production"))

    # Health check
    if not DatabaseEngine.health_check():
        raise RuntimeError("❌ Database health check failed at startup")
    logger.info("✓ Database connected and healthy")

    # Initialize vector DB client
    VectorDBClient.init(
        provider=os.getenv("VECTOR_DB_PROVIDER", "pinecone"),
        api_key=os.getenv("PINECONE_API_KEY")
    )
    logger.info("✓ Vector DB client initialized")

    logger.info("✓ Knowledge Vault API ready")

    yield

    # Shutdown
    logger.info("🛑 Knowledge Vault API shutting down...")
    shutdown_db()
    logger.info("✓ Database connection pool closed")

# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="Knowledge Vault API",
    description="AI-powered link-saving knowledge application",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SaveLinkRequest(BaseModel):
    """Request body for /api/save-link"""
    url: HttpUrl = Field(..., description="URL to save")
    custom_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="User's custom notes (5 words or more)"
    )
    collection_id: Optional[str] = Field(None, description="Collection ID to add to")


class SaveLinkResponse(BaseModel):
    """Response for /api/save-link"""
    success: bool
    link_id: str
    status: str  # "saved" | "already_exists"
    message: str
    title: Optional[str] = None
    platform: Optional[str] = None


class SearchRequest(BaseModel):
    """Request body for /api/search"""
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(5, ge=1, le=20, description="Number of results to return")
    include_raw_results: bool = Field(False, description="Include vector search results")


class SearchResult(BaseModel):
    """Individual search result"""
    link_id: str
    title: Optional[str]
    url: str
    platform: Optional[str]
    thumbnail_url: Optional[str]
    relevance_score: float


class SearchResponse(BaseModel):
    """Response for /api/search"""
    query: str
    ai_response: str
    results: list[SearchResult]
    results_count: int
    response_generated_at: str


class LinkDetailResponse(BaseModel):
    """Full link details response"""
    id: str
    url: str
    platform: Optional[str]
    title: Optional[str]
    description: Optional[str]
    author: Optional[str]
    custom_notes: Optional[str]
    ai_summary: Optional[str]
    ai_tags: list[str]
    user_tags: list[str]
    thumbnail_url: Optional[str]
    published_date: Optional[str]
    ai_processed: bool
    created_at: str


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    database: dict
    vector_db: dict
    version: str


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def normalize_url(url: str) -> str:
    """Normalize URL for deduplication (remove query params, fragments)"""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(str(url))
    normalized = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        "",  # Remove query string
        ""   # Remove fragment
    ))
    return normalized.lower().rstrip("/")


def get_current_user_id(db: Session = Depends(get_db)) -> str:
    """Extract user ID from request context (simplified)
    In production: validate JWT token and extract user ID
    """
    # TODO: Implement JWT validation
    return "test-user-123"


# ============================================================================
# HEALTH & MONITORING ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)):
    """System health check endpoint"""
    try:
        # Database check
        db_healthy = DatabaseEngine.health_check()
        db_stats = get_db_stats()

        # Vector DB check
        vector_db_healthy = VectorDBClient.health_check()

        overall_status = "healthy" if (db_healthy and vector_db_healthy) else "degraded"

        return HealthCheckResponse(
            status=overall_status,
            database={
                "healthy": db_healthy,
                "pool": db_stats
            },
            vector_db={
                "healthy": vector_db_healthy
            },
            version="1.0.0"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Get user statistics"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        links_count = db.query(Link).filter(
            Link.user_id == user_id,
            Link.deleted_at == None
        ).count()

        ai_processed_count = db.query(Link).filter(
            Link.user_id == user_id,
            Link.ai_processed == True,
            Link.deleted_at == None
        ).count()

        return {
            "user_email": user.email,
            "total_links": links_count,
            "ai_processed": ai_processed_count,
            "storage_used_mb": user.storage_used_mb,
            "storage_quota_mb": user.storage_quota_mb,
            "subscription_tier": user.subscription_tier
        }
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CORE ENDPOINTS
# ============================================================================

@app.post("/api/save-link", response_model=SaveLinkResponse, status_code=201)
async def save_link(
    request: SaveLinkRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Save a link with fast synchronous path.

    Returns immediately after database save.
    Background worker handles full enrichment (LLM + embeddings).

    Flow:
    1. Detect platform
    2. Quick metadata extraction (Open Graph)
    3. Save to database (placeholder)
    4. Queue background enrichment
    5. Return to client
    """
    try:
        url_str = str(request.url)
        normalized_url = normalize_url(url_str)

        logger.info(f"Processing save-link request: {url_str}")

        # ===== STEP 1: Check for duplicates =====
        existing = db.query(Link).filter(
            Link.user_id == user_id,
            Link.normalized_url == normalized_url,
            Link.deleted_at == None
        ).first()

        if existing:
            logger.info(f"Link already exists: {existing.id}")
            return SaveLinkResponse(
                success=True,
                link_id=str(existing.id),
                status="already_exists",
                message="This link has already been saved",
                title=existing.title,
                platform=existing.platform
            )

        # ===== STEP 2: Detect platform =====
        platform = detect_platform(url_str)
        logger.info(f"Detected platform: {platform}")

        # ===== STEP 3: Quick metadata extraction (fast path) =====
        quick_data = {}
        try:
            # Use extract() to try platform-specific extractor first
            # If it fails, _open_graph() is fallback inside extract()
            quick_data = extract(url_str, platform)
            logger.info(f"Quick extraction successful: {quick_data.get('title', 'N/A')}")
        except Exception as e:
            logger.warning(f"Quick extraction failed: {e}")
            quick_data = {}

        # ===== STEP 4: Create placeholder link record =====
        link = Link(
            user_id=user_id,
            original_url=url_str,
            normalized_url=normalized_url,
            platform=platform,
            title=quick_data.get("title"),
            description=quick_data.get("description"),
            author=quick_data.get("author"),
            published_date=quick_data.get("published"),
            thumbnail_url=quick_data.get("thumbnail"),
            custom_notes=request.custom_notes,
            ai_processed=False  # Mark for background enrichment
        )

        db.add(link)
        db.flush()  # Get the ID without committing

        # ===== STEP 5: Log audit trail =====
        audit = AuditLog(
            user_id=user_id,
            action="link_saved",
            resource_type="link",
            resource_id=link.id,
            details={
                "url": url_str,
                "platform": platform,
                "has_notes": bool(request.custom_notes)
            }
        )
        db.add(audit)
        db.commit()

        logger.info(f"Link saved with ID: {link.id}")

        # ===== STEP 6: Queue background enrichment =====
        # This runs in background, doesn't block response
        try:
            background_enrichment_queue.enqueue(
                background_enrich_link,
                link.id,
                url_str,
                platform,
                user_id
            )
            logger.info(f"Background enrichment queued for {link.id}")
        except Exception as e:
            logger.warning(f"Failed to queue background task: {e}")
            # Not fatal - enrichment will be retried later

        # ===== STEP 7: Return immediate success =====
        return SaveLinkResponse(
            success=True,
            link_id=str(link.id),
            status="saved",
            message="Link saved successfully. Enrichment in progress...",
            title=quick_data.get("title"),
            platform=platform
        )

    except Exception as e:
        logger.error(f"Save link error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/links/{link_id}", response_model=LinkDetailResponse)
async def get_link_detail(
    link_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Get full link details with all metadata"""
    try:
        link = db.query(Link).filter(
            Link.id == link_id,
            Link.user_id == user_id,
            Link.deleted_at == None
        ).first()

        if not link:
            raise HTTPException(status_code=404, detail="Link not found")

        return LinkDetailResponse(
            id=str(link.id),
            url=link.original_url,
            platform=link.platform,
            title=link.title,
            description=link.description,
            author=link.author,
            custom_notes=link.custom_notes,
            ai_summary=link.ai_summary,
            ai_tags=link.ai_tags or [],
            user_tags=link.user_tags or [],
            thumbnail_url=link.thumbnail_url,
            published_date=link.published_date.isoformat() if link.published_date else None,
            ai_processed=link.ai_processed,
            created_at=link.created_at.isoformat()
        )
    except Exception as e:
        logger.error(f"Get link detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search", response_model=SearchResponse)
async def search_knowledge_base(
    query: str = Query(..., min_length=3, max_length=500),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """
    Semantic search + RAG endpoint.

    Flow:
    1. Vectorize query
    2. Search vector database
    3. Fetch full records from PostgreSQL
    4. Generate conversational response with GPT-4o-mini
    5. Return both results and AI synthesis
    """
    try:
        logger.info(f"Search query: {query}")

        # ===== STEP 1: Create search record =====
        search = SearchQuery(
            user_id=user_id,
            query_text=query,
            response_generated=False
        )
        db.add(search)
        db.flush()

        # ===== STEP 2: Vectorize query =====
        try:
            query_embedding = generate_embeddings(query)
            search.query_embedding_id = f"query_{search.id}"
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise HTTPException(status_code=500, detail="Search vectorization failed")

        # ===== STEP 3: Search vector database =====
        try:
            vector_results = VectorDBClient.search(
                query_vector=query_embedding,
                user_id=user_id,
                top_k=top_k
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise HTTPException(status_code=500, detail="Vector search failed")

        if not vector_results:
            logger.info("No search results found")
            search.results_count = 0
            db.commit()
            return SearchResponse(
                query=query,
                ai_response="No matching links found in your knowledge base.",
                results=[],
                results_count=0,
                response_generated_at=""
            )

        # ===== STEP 4: Fetch full link records =====
        link_ids = [r["metadata"]["link_id"] for r in vector_results]
        links = db.query(Link).filter(
            Link.id.in_(link_ids),
            Link.user_id == user_id,
            Link.deleted_at == None
        ).all()

        # Map links with relevance scores
        link_map = {str(l.id): l for l in links}
        results = []
        for vector_result in vector_results:
            link_id = vector_result["metadata"]["link_id"]
            link = link_map.get(link_id)
            if link:
                results.append(SearchResult(
                    link_id=link_id,
                    title=link.title,
                    url=link.original_url,
                    platform=link.platform,
                    thumbnail_url=link.thumbnail_url,
                    relevance_score=vector_result["score"]
                ))

        search.results_count = len(results)
        search.top_result_link_ids = link_ids[:5]

        # ===== STEP 5: Generate RAG response =====
        try:
            context_blocks = [
                {
                    "title": link.title,
                    "url": link.original_url,
                    "summary": link.ai_summary or link.description,
                    "tags": link.ai_tags,
                    "platform": link.platform
                }
                for link in links[:top_k]
            ]

            ai_response = rag_search_response(
                query=query,
                context=context_blocks
            )
            search.ai_response = ai_response
            search.response_generated = True
        except Exception as e:
            logger.error(f"RAG response generation failed: {e}")
            ai_response = f"Found {len(results)} relevant links. LLM synthesis unavailable."

        # ===== STEP 6: Commit search record =====
        db.commit()

        logger.info(f"Search completed: {len(results)} results")

        return SearchResponse(
            query=query,
            ai_response=ai_response,
            results=results,
            results_count=len(results),
            response_generated_at=""
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@app.delete("/api/links/{link_id}")
async def delete_link(
    link_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """Soft delete a link"""
    try:
        link = db.query(Link).filter(
            Link.id == link_id,
            Link.user_id == user_id,
            Link.deleted_at == None
        ).first()

        if not link:
            raise HTTPException(status_code=404, detail="Link not found")

        link.deleted_at = func.now()

        audit = AuditLog(
            user_id=user_id,
            action="link_deleted",
            resource_type="link",
            resource_id=link_id
        )
        db.add(audit)
        db.commit()

        return {"success": True, "message": "Link deleted"}
    except Exception as e:
        logger.error(f"Delete link error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# BACKGROUND TASK WORKER (Runs asynchronously)
# ============================================================================

async def background_enrich_link(
    link_id: str,
    url: str,
    platform: str,
    user_id: str
):
    """
    Background worker: Heavy lifting for link enrichment

    Tasks:
    1. Full content extraction (text, headings, paragraphs, images)
    2. LLM categorization (category hierarchy)
    3. LLM tagging (contextual tags)
    4. LLM summarization (2-sentence polish summary)
    5. Vector embedding generation
    6. Upsert to vector database
    7. Update database with enriched data
    """
    db = get_db()

    try:
        logger.info(f"Starting background enrichment for {link_id}")

        link = db.query(Link).filter(Link.id == link_id).first()
        if not link:
            logger.error(f"Link not found: {link_id}")
            return

        # ===== TASK 1: Full content extraction =====
        logger.info(f"Extracting full content for {link_id}")
        try:
            full_data = _extract_full_content(url)
            link.full_text_snippet = full_data.get("full_text")
            link.headings_json = full_data.get("headings")
            link.paragraphs_json = full_data.get("paragraphs")
            link.price = full_data.get("price")
            link.rating = full_data.get("rating")
        except Exception as e:
            logger.warning(f"Full content extraction failed: {e}")

        # ===== TASK 2: LLM enrichment (category, tags, summary) =====
        logger.info(f"Running LLM enrichment for {link_id}")
        try:
            enrichment = enrich_link_with_llm(
                title=link.title,
                description=link.description,
                full_text=link.full_text_snippet,
                url=url,
                platform=platform
            )
            link.category_hierarchy = enrichment.get("category")
            link.ai_tags = enrichment.get("tags", [])
            link.ai_summary = enrichment.get("summary")
        except Exception as e:
            logger.error(f"LLM enrichment failed: {e}")

        # ===== TASK 3: Generate embeddings =====
        logger.info(f"Generating embeddings for {link_id}")
        try:
            embedding_text = f"{link.ai_summary or link.title} {' '.join(link.ai_tags or [])}"
            embedding_vector = generate_embeddings(embedding_text)

            # ===== TASK 4: Upsert to vector database =====
            vector_db_id = VectorDBClient.upsert(
                link_id=str(link_id),
                user_id=user_id,
                vector=embedding_vector,
                metadata={
                    "title": link.title,
                    "platform": platform,
                    "tags": link.ai_tags,
                    "category": link.category_hierarchy
                }
            )

            link.embedding_id = vector_db_id
        except Exception as e:
            logger.error(f"Embedding/vector upsert failed: {e}")

        # ===== TASK 5: Mark as processed =====
        link.ai_processed = True
        db.commit()

        logger.info(f"✓ Enrichment complete for {link_id}")

    except Exception as e:
        logger.error(f"Background enrichment critical error: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    logger.error(f"HTTP Error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# ============================================================================
# ROOT ENDPOINT
# ============================================================================

@app.get("/")
async def root():
    """API info endpoint"""
    return {
        "name": "Knowledge Vault API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level="info"
    )

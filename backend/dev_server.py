"""
Knowledge Vault — Dev Server (in-memory, no DB/Pinecone/OpenAI required)
Hardcoded data + simulated API for frontend testing.
"""

import uuid
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ============================================================================
# HARDCODED SEED LINKS
# ============================================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()

PLATFORM_MAP = {
    "youtube.com": "youtube", "youtu.be": "youtube",
    "twitter.com": "twitter", "x.com": "twitter",
    "reddit.com": "reddit",
    "github.com": "github",
    "medium.com": "article",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "vimeo.com": "vimeo",
    "pinterest.com": "pinterest",
    "notion.so": "notion",
    "figma.com": "figma",
}

CAT_KEYWORDS = {
    "work":     ["work", "career", "job", "productivity", "tool", "api", "code", "dev", "engineer", "startup", "business", "meeting", "figma", "notion", "github"],
    "reading":  ["article", "blog", "read", "book", "medium", "news", "post", "essay", "writing"],
    "ideas":    ["idea", "design", "concept", "creative", "inspiration", "product", "launch", "side"],
    "personal": ["personal", "health", "life", "travel", "family", "habit", "fitness", "mind"],
    "todo":     ["todo", "task", "plan", "buy", "shop", "purchase", "checklist", "reminder"],
    "daily":    ["daily", "routine", "morning", "coffee", "youtube", "twitter", "reddit", "tiktok", "instagram"],
}

def detect_platform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().replace("www.", "")
    for domain, platform in PLATFORM_MAP.items():
        if host.endswith(domain):
            return platform
    return "generic"

def infer_category(title: str, platform: str, url: str) -> str:
    text = (title + " " + platform + " " + url).lower()
    scores = {cat: 0 for cat in CAT_KEYWORDS}
    for cat, keywords in CAT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "ideas"

SEED_LINKS = [
    {
        "id": "link-001",
        "url": "https://github.com/features/copilot",
        "platform": "github",
        "title": "GitHub Copilot — AI pair programmer",
        "description": "GitHub Copilot uses the OpenAI Codex to suggest code and functions in real-time.",
        "author": "GitHub",
        "ai_summary": "GitHub Copilot is an AI code assistant powered by OpenAI Codex that autocompletes code in real-time inside your editor. It supports dozens of languages and dramatically speeds up coding.",
        "ai_tags": ["ai", "coding", "developer-tool", "github", "openai"],
        "cat": "work",
        "fav": True,
        "pin": True,
        "thumbnail_url": None,
        "ai_processed": True,
        "created_at": now_iso(),
    },
    {
        "id": "link-002",
        "url": "https://medium.com/@dan_abramov/making-sense-of-react-hooks",
        "platform": "article",
        "title": "Making Sense of React Hooks — Dan Abramov",
        "description": "An in-depth explanation of why React Hooks were created and how they work.",
        "author": "Dan Abramov",
        "ai_summary": "Dan Abramov explains the motivation behind React Hooks, how they simplify stateful logic reuse, and why they're a better pattern than class components. Essential reading for React developers.",
        "ai_tags": ["react", "hooks", "javascript", "frontend", "programming"],
        "cat": "reading",
        "fav": False,
        "pin": False,
        "thumbnail_url": None,
        "ai_processed": True,
        "created_at": now_iso(),
    },
    {
        "id": "link-003",
        "url": "https://www.figma.com/community/file/1232806277704553012",
        "platform": "figma",
        "title": "Mobile UI Kit — 300+ Components",
        "description": "A comprehensive Figma UI kit with 300+ mobile components, auto-layout, and variables.",
        "author": "Figma Community",
        "ai_summary": "A massive Figma UI kit with over 300 production-ready mobile components built with auto-layout and design variables. Great starting point for any mobile app project.",
        "ai_tags": ["design", "figma", "ui-kit", "mobile", "components"],
        "cat": "ideas",
        "fav": True,
        "pin": False,
        "thumbnail_url": None,
        "ai_processed": True,
        "created_at": now_iso(),
    },
    {
        "id": "link-004",
        "url": "https://reddit.com/r/MachineLearning/comments/1abc123/gpt5_rumors",
        "platform": "reddit",
        "title": "GPT-5 speculation thread — r/MachineLearning",
        "description": "Community speculation on what GPT-5 capabilities will look like.",
        "author": "u/ml_enthusiast",
        "ai_summary": "A Reddit thread discussing community speculation around GPT-5's expected capabilities, training compute, and release timeline. Multiple ML researchers weigh in with predictions.",
        "ai_tags": ["ai", "gpt", "language-model", "openai", "machine-learning"],
        "cat": "daily",
        "fav": False,
        "pin": False,
        "thumbnail_url": None,
        "ai_processed": True,
        "created_at": now_iso(),
    },
    {
        "id": "link-005",
        "url": "https://notion.so/templates/personal-dashboard",
        "platform": "notion",
        "title": "Personal Life Dashboard — Notion Template",
        "description": "An all-in-one Notion dashboard for tracking goals, habits, and daily tasks.",
        "author": "Notion",
        "ai_summary": "A comprehensive Notion template that acts as a personal life OS — tracking goals, daily habits, weekly reviews, and project management in one unified workspace.",
        "ai_tags": ["productivity", "notion", "template", "goals", "habits"],
        "cat": "personal",
        "fav": False,
        "pin": False,
        "thumbnail_url": None,
        "ai_processed": True,
        "created_at": now_iso(),
    },
    {
        "id": "link-006",
        "url": "https://twitter.com/levelsio/status/1234567890",
        "platform": "twitter",
        "title": "Pieter Levels on building profitable indie products",
        "description": "A viral thread on how to ship fast and make money as an indie hacker.",
        "author": "@levelsio",
        "ai_summary": "Pieter Levels shares his proven framework for building profitable micro-SaaS products solo: ship in days, validate with real money, ignore non-paying users, and iterate relentlessly.",
        "ai_tags": ["indie-hacker", "startup", "saas", "entrepreneurship", "twitter"],
        "cat": "ideas",
        "fav": True,
        "pin": False,
        "thumbnail_url": None,
        "ai_processed": True,
        "created_at": now_iso(),
    },
]

# In-memory store
_links: list = [dict(l) for l in SEED_LINKS]
USER_ID = "test-user-123"
STATS = {
    "user_email": "nikhil@haystek.co",
    "subscription_tier": "free",
    "storage_used_mb": 2,
    "storage_quota_mb": 1000,
}

# ============================================================================
# APP
# ============================================================================

app = FastAPI(title="Knowledge Vault Dev API", version="1.0.0-dev")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# MODELS
# ============================================================================

class SaveLinkRequest(BaseModel):
    url: str
    custom_notes: Optional[str] = None
    collection_id: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/")
def root():
    return {"name": "Knowledge Vault Dev API", "version": "1.0.0-dev", "mode": "in-memory"}

@app.get("/health")
def health():
    return {"status": "healthy", "mode": "dev-in-memory", "version": "1.0.0-dev",
            "database": {"healthy": True, "pool": {}}, "vector_db": {"healthy": True}}

@app.get("/api/stats")
def get_stats():
    active = [l for l in _links if not l.get("deleted")]
    ai_done = [l for l in active if l.get("ai_processed")]
    return {
        **STATS,
        "total_links": len(active),
        "ai_processed": len(ai_done),
    }

@app.get("/api/links")
def list_links(cat: Optional[str] = None):
    active = [l for l in _links if not l.get("deleted")]
    if cat:
        active = [l for l in active if l.get("cat") == cat]
    return {"links": active, "count": len(active)}

@app.post("/api/save-link", status_code=201)
def save_link(req: SaveLinkRequest):
    # Check duplicate
    normalized = req.url.lower().rstrip("/").split("?")[0]
    for link in _links:
        if link.get("url", "").lower().rstrip("/").split("?")[0] == normalized and not link.get("deleted"):
            return {"success": True, "link_id": link["id"], "status": "already_exists",
                    "message": "This link has already been saved.", "title": link.get("title"), "platform": link.get("platform")}

    platform = detect_platform(req.url)
    # Build a realistic-looking title from URL
    path = urlparse(req.url).path.strip("/").replace("-", " ").replace("_", " ")
    host = (urlparse(req.url).hostname or req.url).replace("www.", "")
    title = path.split("/")[-1].title() if path else host
    if not title:
        title = host

    cat = infer_category(title, platform, req.url)

    link = {
        "id": f"link-{uuid.uuid4().hex[:8]}",
        "url": req.url,
        "platform": platform,
        "title": title or host,
        "description": f"Saved from {host}",
        "author": host,
        "ai_summary": f"This link was saved from {host}. AI enrichment will provide a full summary once processing completes.",
        "ai_tags": [platform, host.split(".")[0]],
        "cat": cat,
        "fav": False,
        "pin": False,
        "thumbnail_url": None,
        "custom_notes": req.custom_notes,
        "ai_processed": False,
        "deleted": False,
        "created_at": now_iso(),
    }
    _links.insert(0, link)

    return {
        "success": True,
        "link_id": link["id"],
        "status": "saved",
        "message": "Link saved. AI enrichment queued.",
        "title": link["title"],
        "platform": platform,
    }

@app.get("/api/links/{link_id}")
def get_link(link_id: str):
    for link in _links:
        if link["id"] == link_id and not link.get("deleted"):
            return link
    raise HTTPException(status_code=404, detail="Link not found")

@app.patch("/api/links/{link_id}")
def patch_link(link_id: str, body: dict):
    for link in _links:
        if link["id"] == link_id and not link.get("deleted"):
            allowed = {"fav", "pin", "custom_notes", "cat", "title"}
            for k, v in body.items():
                if k in allowed:
                    link[k] = v
            return {"success": True, "link": link}
    raise HTTPException(status_code=404, detail="Link not found")

@app.delete("/api/links/{link_id}")
def delete_link(link_id: str):
    for link in _links:
        if link["id"] == link_id and not link.get("deleted"):
            link["deleted"] = True
            return {"success": True, "message": "Link deleted"}
    raise HTTPException(status_code=404, detail="Link not found")

@app.get("/api/search")
def search(query: str = "", top_k: int = 5):
    if not query.strip():
        return {"query": query, "ai_response": "Please enter a search query.", "results": [], "results_count": 0}

    q = query.lower()
    active = [l for l in _links if not l.get("deleted")]

    scored = []
    for link in active:
        text = " ".join([
            link.get("title", ""),
            link.get("description", ""),
            link.get("ai_summary", ""),
            " ".join(link.get("ai_tags", [])),
            link.get("platform", ""),
            link.get("cat", ""),
        ]).lower()
        score = sum(1 for word in q.split() if word in text)
        if score > 0:
            scored.append((score, link))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [l for _, l in scored[:top_k]]

    if results:
        titles = ", ".join(f'"{r["title"]}"' for r in results[:3])
        ai_response = (
            f'Based on your saved links, here\'s what I found for **"{query}"**:\n\n'
            f'I found {len(results)} relevant link{"s" if len(results) != 1 else ""} including {titles}. '
            f'These were matched across titles, AI summaries, and tags in your vault.'
        )
    else:
        ai_response = f'No saved links matched **"{query}"**. Try saving some links first, then search again.'

    return {
        "query": query,
        "ai_response": ai_response,
        "results": results,
        "results_count": len(results),
        "response_generated_at": now_iso(),
    }

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("🚀 Knowledge Vault Dev Server starting on http://localhost:8001")
    print("📖 API docs: http://localhost:8001/docs")
    uvicorn.run("dev_server:app", host="0.0.0.0", port=8001, reload=True, log_level="info")

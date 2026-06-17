from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import json, os, uuid

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# In-memory storage
links_db = {}

class SaveLinkRequest(BaseModel):
    url: str
    custom_notes: str = None

@app.get("/")
async def root():
    return {"message": "Knowledge Vault API", "status": "healthy"}

@app.get("/health")
async def health():
    return {"status": "healthy", "database": {"healthy": True}, "version": "1.0.0"}

@app.post("/api/save-link")
async def save_link(request: SaveLinkRequest):
    link_id = str(uuid.uuid4())
    link_data = {
        "id": link_id,
        "url": request.url,
        "custom_notes": request.custom_notes or "",
        "platform": "generic",
        "title": request.url.split('/')[-1] or "Link",
        "ai_processed": False,
        "created_at": datetime.now().isoformat(),
        "ai_tags": [],
        "user_tags": [],
        "thumbnail_url": None
    }
    links_db[link_id] = link_data
    return {"success": True, "message": "Link saved", "link_id": link_id}

@app.get("/api/links")
async def get_links():
    return {"links": list(links_db.values()), "count": len(links_db)}

@app.get("/api/links/{link_id}")
async def get_link_detail(link_id: str):
    if link_id not in links_db:
        raise HTTPException(status_code=404, detail="Link not found")
    return links_db[link_id]

@app.get("/api/search")
async def search(query: str = ""):
    results = [l for l in links_db.values() if query.lower() in l.get("title", "").lower() or query.lower() in l.get("url", "").lower()]
    return {"query": query, "results": results[:5], "ai_response": f"Found {len(results)} links matching '{query}'", "results_count": len(results)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

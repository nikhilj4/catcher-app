"""
LLM Integration Module
Handles OpenRouter API calls for categorization, tagging, summarization, and embeddings
"""

import json
import logging
import os
from typing import Optional, List, Dict

from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client globally to be configured later
client = None

class LLMError(Exception):
    """Custom exception for LLM operations"""
    pass

CATEGORIZATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "LinkMetadata",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "category_hierarchy": {
                    "type": "string",
                    "description": "Multi-tiered category path (e.g., 'Shopping > Electronics > Smartphones')"
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5-10 contextual tags extracted from the content"
                },
                "summary": {
                    "type": "string",
                    "description": "2-sentence polished summary of the link content"
                },
                "content_type": {
                    "type": "string",
                    "enum": ["article", "product", "video", "social", "documentation", "other"],
                    "description": "Inferred content type"
                }
            },
            "required": ["category_hierarchy", "tags", "summary", "content_type"],
            "additionalProperties": False
        }
    }
}

def enrich_link_with_llm(
    title: Optional[str],
    description: Optional[str],
    full_text: Optional[str],
    url: str,
    platform: str,
    max_retries: int = 3
) -> Dict:
    global client
    if not client:
        return _fallback_enrichment(title, platform)

    try:
        content_text = ""
        if title: content_text += f"Title: {title}\n"
        if description: content_text += f"Description: {description}\n"
        if full_text: content_text += f"Content: {full_text[:1500]}\n"

        if not content_text.strip():
            return {
                "category": "Uncategorized",
                "tags": [platform],
                "summary": f"Link saved from {platform}",
                "content_type": "other"
            }

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing web content and extracting structured metadata. Identify the primary category, extract 5-10 contextual tags, write a 2-sentence summary, and infer the content type. Output MUST be valid JSON matching the schema."
                },
                {
                    "role": "user",
                    "content": f"URL: {url}\nPlatform: {platform}\n\n{content_text}"
                }
            ],
            response_format={"type": "json_object"},  # OpenRouter supports json_object (schema enforcement varies)
            temperature=0.7,
            max_tokens=500
        )

        response_text = response.choices[0].message.content
        parsed = json.loads(response_text)

        return {
            "category": parsed.get("category_hierarchy", "Uncategorized"),
            "tags": parsed.get("tags", []),
            "summary": parsed.get("summary", ""),
            "content_type": parsed.get("content_type", "other")
        }

    except Exception as e:
        logger.error(f"LLM enrichment error: {e}")
        return _fallback_enrichment(title, platform)

def _fallback_enrichment(title: Optional[str], platform: str) -> Dict:
    return {
        "category": f"Uncategorized > {platform.capitalize()}",
        "tags": [platform.lower()],
        "summary": f"Content from {platform}. {title or 'No summary available.'}",
        "content_type": "other"
    }

def generate_embeddings(text: str, model: str = "openai/text-embedding-3-small") -> List[float]:
    """
    Generate embeddings using OpenRouter (requires an OpenRouter key with embedding support, or fallback)
    """
    global client
    if not client:
        raise LLMError("Client not initialized")
    
    try:
        if not text or len(text.strip()) == 0:
            raise LLMError("Empty text")

        text = text[:32000]
        # Currently, OpenRouter routes to standard embeddings via completions api, but let's try the native embeddings endpoint
        # If it fails, ChromaDB can use its default local embedding! We'll just throw and catch in vector_db if needed.
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding

    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        raise LLMError(f"Embedding failed: {e}")

def rag_search_response(query: str, context: List[Dict], max_retries: int = 2) -> str:
    global client
    if not client:
        return _fallback_rag_response(context)

    try:
        if not context:
            return "I found no relevant links in your knowledge base for that query."

        context_str = "\n\n".join([
            f"**{item.get('title', 'Untitled')}** ({item.get('platform', 'unknown')})\nURL: {item.get('url', '#')}\nSummary: {item.get('summary', 'No summary available')}\nTags: {', '.join(item.get('tags', []))}"
            for item in context[:5]
        ])

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Answer the user's query using the provided link context. Reference specific links using markdown [Title](URL). Be concise."
                },
                {
                    "role": "user",
                    "content": f"User Query: {query}\n\nAvailable Links:\n{context_str}"
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )

        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"RAG response generation error: {e}")
        return _fallback_rag_response(context)

def _fallback_rag_response(context: List[Dict]) -> str:
    if not context: return "No relevant links found."
    links = "\n".join([f"- [{i.get('title', 'Link')}]({i.get('url', '#')})" for i in context[:5]])
    return f"Found {len(context)} relevant links:\n\n{links}"

def init_openai(api_key: str):
    global client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={"HTTP-Referer": "http://localhost:5173", "X-Title": "Knowledge Vault"}
    )
    logger.info("OpenRouter API initialized")

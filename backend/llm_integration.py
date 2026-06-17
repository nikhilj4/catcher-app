"""
LLM Integration Module
Handles OpenAI API calls for categorization, tagging, summarization, and embeddings
"""

import json
import logging
from typing import Optional, List, Dict

import openai

logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai.api_key = None  # Set from environment


class LLMError(Exception):
    """Custom exception for LLM operations"""
    pass


# ============================================================================
# CATEGORIZATION & TAGGING
# ============================================================================

CATEGORIZATION_SCHEMA = {
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
    "required": ["category_hierarchy", "tags", "summary", "content_type"]
}


def enrich_link_with_llm(
    title: Optional[str],
    description: Optional[str],
    full_text: Optional[str],
    url: str,
    platform: str,
    max_retries: int = 3
) -> Dict:
    """
    Use GPT-4o-mini to extract category, tags, and summary from link metadata.

    Args:
        title: Link title
        description: Link description
        full_text: Full page text (first 2000 chars)
        url: Original URL
        platform: Detected platform
        max_retries: Number of retries on API failure

    Returns:
        {
            "category": str,     # Multi-tiered category
            "tags": [str],       # Contextual tags
            "summary": str,      # 2-sentence summary
            "content_type": str  # article|product|video|social|documentation|other
        }
    """
    try:
        # Build rich context for LLM
        content_text = ""
        if title:
            content_text += f"Title: {title}\n"
        if description:
            content_text += f"Description: {description}\n"
        if full_text:
            content_text += f"Content: {full_text[:1500]}\n"  # First 1500 chars

        if not content_text.strip():
            logger.warning(f"No content to enrich for {url}")
            return {
                "category": "Uncategorized",
                "tags": [platform],
                "summary": f"Link saved from {platform}",
                "content_type": "other"
            }

        # Call GPT-4o-mini with JSON schema mode
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert at analyzing web content and extracting structured metadata.

For any given link content, you must:
1. Identify the primary category (hierarchical path like "Shopping > Electronics > Smartphones")
2. Extract 5-10 contextual tags that summarize key topics
3. Write a concise 2-sentence summary that captures the essence
4. Infer the content type (article, product, video, social media, documentation, etc.)

Be precise, concise, and ensure tags are lowercase and hyphenated."""
                },
                {
                    "role": "user",
                    "content": f"""Analyze this web link content:

URL: {url}
Platform: {platform}

{content_text}

Extract the category hierarchy, relevant tags, a 2-sentence summary, and content type."""
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "LinkMetadata",
                    "schema": CATEGORIZATION_SCHEMA,
                    "strict": True
                }
            },
            temperature=0.7,
            max_tokens=500
        )

        # Parse JSON response
        response_text = response.choices[0].message.content
        parsed = json.loads(response_text)

        logger.info(f"LLM enrichment successful: {parsed['category']}")

        return {
            "category": parsed.get("category_hierarchy", "Uncategorized"),
            "tags": parsed.get("tags", []),
            "summary": parsed.get("summary", ""),
            "content_type": parsed.get("content_type", "other")
        }

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        return _fallback_enrichment(title, platform)
    except openai.error.RateLimitError:
        logger.warning("OpenAI rate limit hit, using fallback")
        return _fallback_enrichment(title, platform)
    except openai.error.APIError as e:
        logger.error(f"OpenAI API error: {e}")
        return _fallback_enrichment(title, platform)
    except Exception as e:
        logger.error(f"LLM enrichment error: {e}")
        return _fallback_enrichment(title, platform)


def _fallback_enrichment(title: Optional[str], platform: str) -> Dict:
    """Fallback enrichment when LLM is unavailable"""
    return {
        "category": f"Uncategorized > {platform.capitalize()}",
        "tags": [platform.lower()],
        "summary": f"Content from {platform}. {title or 'No summary available.'}",
        "content_type": "other"
    }


# ============================================================================
# EMBEDDING GENERATION
# ============================================================================

def generate_embeddings(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    Generate vector embeddings using OpenAI's text-embedding-3-small.

    Args:
        text: Text to embed
        model: Embedding model name

    Returns:
        1536-dimensional vector (list of floats)

    Raises:
        LLMError: If embedding generation fails
    """
    try:
        if not text or len(text.strip()) == 0:
            raise LLMError("Empty text cannot be embedded")

        # Truncate text if too long (max ~8191 tokens for text-embedding-3-small)
        # Rough estimate: 1 token ≈ 4 characters
        max_chars = 32000
        if len(text) > max_chars:
            text = text[:max_chars]

        response = openai.Embedding.create(
            input=text,
            model=model
        )

        embedding = response['data'][0]['embedding']
        logger.info(f"Embedding generated: {len(embedding)} dimensions")

        return embedding

    except openai.error.RateLimitError:
        logger.warning("Embedding rate limit hit")
        raise LLMError("Rate limited. Retry later.")
    except openai.error.APIError as e:
        logger.error(f"Embedding API error: {e}")
        raise LLMError(f"Embedding failed: {e}")
    except Exception as e:
        logger.error(f"Embedding generation error: {e}")
        raise LLMError(f"Embedding failed: {e}")


# ============================================================================
# RAG SEARCH RESPONSE GENERATION
# ============================================================================

def rag_search_response(
    query: str,
    context: List[Dict],
    max_retries: int = 2
) -> str:
    """
    Generate conversational RAG response using GPT-4o-mini.

    Takes search results and generates a natural language answer that:
    - Directly answers the user's query
    - References relevant links
    - Highlights product details, pricing, offers
    - Includes source URLs as markdown links

    Args:
        query: User's natural language search query
        context: List of dicts with {title, url, summary, tags, platform}

    Returns:
        Conversational response string with markdown formatting
    """
    try:
        if not context:
            return "I found no relevant links in your knowledge base for that query."

        # Format context blocks
        context_str = "\n\n".join([
            f"**{item.get('title', 'Untitled')}** ({item.get('platform', 'unknown')})\n"
            f"URL: {item.get('url', '#')}\n"
            f"Summary: {item.get('summary', 'No summary available')}\n"
            f"Tags: {', '.join(item.get('tags', []))}"
            for item in context[:5]  # Top 5 results
        ])

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful knowledge assistant that answers user queries by synthesizing information from saved links.

Your role:
- Answer the user's question directly using context from the provided links
- Reference specific links that are relevant
- Highlight product details, pricing, and offers when present
- Format links as markdown: [Link Title](URL)
- Be conversational and helpful
- If the information is incomplete, acknowledge it
- Keep responses concise but comprehensive (2-3 paragraphs max)"""
                },
                {
                    "role": "user",
                    "content": f"""User Query: {query}

Available Links:
{context_str}

Please answer the user's query using these links. Reference specific links where appropriate."""
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )

        response_text = response.choices[0].message.content
        logger.info("RAG response generated successfully")

        return response_text

    except openai.error.RateLimitError:
        logger.warning("RAG response rate limited")
        return _fallback_rag_response(context)
    except openai.error.APIError as e:
        logger.error(f"RAG response API error: {e}")
        return _fallback_rag_response(context)
    except Exception as e:
        logger.error(f"RAG response generation error: {e}")
        return _fallback_rag_response(context)


def _fallback_rag_response(context: List[Dict]) -> str:
    """Fallback response when LLM is unavailable"""
    if not context:
        return "No relevant links found."

    links = "\n".join([
        f"- [{item.get('title', 'Link')}]({item.get('url', '#')})"
        for item in context[:5]
    ])

    return f"Found {len(context)} relevant links:\n\n{links}\n\nSee links above for more information."


# ============================================================================
# CONFIGURATION
# ============================================================================

def init_openai(api_key: str):
    """Initialize OpenAI API key"""
    global openai
    openai.api_key = api_key
    logger.info("OpenAI API initialized")

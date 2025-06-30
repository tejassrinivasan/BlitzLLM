"""Web scraping and search tool using Firecrawl."""

import asyncio
import logging
import os
import re
from typing import Any, List, Optional
import aiohttp
import json

from httpx import HTTPStatusError
from mcp.server.fastmcp import Context
from pydantic import Field

from config import FIRECRAWL_API_KEY
from utils import serialize_response

__all__ = ["webscrape"]


async def _get_context_field(field: str, ctx: Context) -> Any:
    """Get the context of the current request."""
    return getattr(getattr(getattr(ctx, "request_context", None), "lifespan_context", None), field, None)


def clean_markdown(markdown: str, base_url: Optional[str] = None) -> str:
    """Clean up markdown content similar to the mastra implementation."""
    if not markdown:
        return "No markdown available"
    
    # Extract base domain from URL if provided
    base_domain = ''
    if base_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            base_domain = parsed.hostname.lower() if parsed.hostname else ''
        except:
            pass

    cleaned = markdown
    # Remove excessive escaped backslashes
    cleaned = re.sub(r'\\{4,}', '', cleaned)
    # Remove escaped backslashes before common characters
    cleaned = re.sub(r'\\+', '', cleaned)
    # Remove base64 image placeholders
    cleaned = re.sub(r'!\[\]\(<Base64-Image-Removed>\)', '', cleaned)
    # Remove image markdown syntax
    cleaned = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', cleaned)
    # Remove HTML image tags
    cleaned = re.sub(r'<img[^>]*>', '', cleaned, flags=re.IGNORECASE)
    
    # Remove HTML tags completely
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    cleaned = re.sub(r'&[a-zA-Z]+;', '', cleaned)  # Remove HTML entities
    
    # Remove navigation elements
    cleaned = re.sub(r'Skip to main content', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Skip to navigation', '', cleaned, flags=re.IGNORECASE)
    
    # Remove common footer/legal content
    footer_patterns = [
        r'Terms of Use', r'Privacy Policy', r'Contact Us', r'Copyright: © \d{4}[^\n]*'
    ]
    for pattern in footer_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Remove ticket-related content
    cleaned = re.sub(r'Tickets?\s+(as\s+low\s+as|starting\s+at|from)\s+\$[\d.,]+', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'Buy\s+Tickets?', '', cleaned, flags=re.IGNORECASE)
    
    # Clean up excessive whitespace and newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r' {3,}', ' ', cleaned)
    
    # Split into lines and filter
    lines = []
    for line in cleaned.split('\n'):
        line = line.strip()
        if (line and 
            not re.match(r'^[-\s|]+$', line) and
            not re.match(r'^Close\s*$', line, re.IGNORECASE) and
            not re.match(r'^All Providers', line, re.IGNORECASE)):
            lines.append(line)
    
    cleaned = '\n'.join(lines).strip()
    
    # Handle duplicate links if base domain is provided
    if base_domain:
        # Remove external domain links, keep only internal ones
        def replace_link(match):
            text, url = match.groups()
            try:
                from urllib.parse import urlparse, urljoin
                full_url = urljoin(base_url, url)
                parsed = urlparse(full_url)
                if parsed.hostname and base_domain not in parsed.hostname.lower():
                    return text or ''
                return match.group(0)
            except:
                return text or ''
        
        cleaned = re.sub(r'\[([^\]]*)\]\(([^)]+)\)', replace_link, cleaned)
    
    return cleaned


async def webscrape(
    ctx: Context,
    query: str = Field(default="", description="Search query for web search"),
    url: str = Field(default="", description="Direct URL to scrape"),
    limit: int = Field(3, description="Number of search results to scrape (when using search)"),
    location: str = Field(default="", description="Location for search (e.g., 'Germany', 'United States')"),
    tbs: str = Field(default="", description="Time-based search filter (qdr:h=past hour, qdr:d=past day, etc.)"),
    formats: List[str] = Field(["markdown"], description="Output formats ('markdown', 'extract')"),
    extract_prompt: str = Field(default="", description="Prompt for AI extraction when using 'extract' format"),
    timeout: int = Field(30000, description="Timeout in milliseconds")
) -> dict[str, Any]:
    """
    Search the web and scrape content from results, or scrape a specific URL.
    
    This tool can either:
    1. Search the web and scrape multiple results (provide 'query')
    2. Scrape a specific URL (provide 'url')
    
    Webscrape Instructions:
    1. For search: Provide a search query and optionally limit, location, time filters
    2. For direct scraping: Provide a URL
    3. Choose output formats: 'markdown' for cleaned content, 'extract' for AI-powered extraction
    4. Results are cleaned and processed for better readability
    """
    if not query and not url:
        raise ValueError("Either 'query' for search or 'url' for direct scraping is required")
    
    api_key = FIRECRAWL_API_KEY
    if not api_key:
        return {
            "success": False,
            "error": "FIRECRAWL_API_KEY not configured"
        }
    
    try:
        async with aiohttp.ClientSession() as session:
            if url:
                # Direct URL scraping
                scrape_options = {"formats": formats}
                
                if "extract" in formats and extract_prompt:
                    scrape_options["extract"] = {
                        "prompt": extract_prompt or "Extract the main information, key points, and relevant data from this page."
                    }
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                data = {
                    "url": url,
                    **scrape_options
                }
                
                async with session.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=timeout/1000)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Firecrawl API error ({response.status}): {error_text}"
                        }
                    
                    result = await response.json()
                    
                    if not result.get("success"):
                        return {
                            "success": False,
                            "error": result.get("error", "Scraping failed")
                        }
                    
                    data = result.get("data", {})
                    
                    return {
                        "success": True,
                        "url": url,
                        "title": data.get("metadata", {}).get("title", ""),
                        "description": data.get("metadata", {}).get("description", ""),
                        "markdown": clean_markdown(data.get("markdown", ""), url) if "markdown" in formats else None,
                        "extract": data.get("extract") if "extract" in formats else None,
                        "metadata": data.get("metadata", {})
                    }
            
            else:
                # Search and scrape multiple results
                scrape_options = {"formats": formats}
                
                if "extract" in formats:
                    scrape_options["extract"] = {
                        "prompt": extract_prompt or "Extract the main information, key points, and relevant data from this page."
                    }
                
                request_body = {
                    "query": query,
                    "limit": limit,
                    "timeout": timeout,
                    "scrapeOptions": scrape_options
                }
                
                if location:
                    request_body["location"] = location
                if tbs:
                    request_body["tbs"] = tbs
                
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(
                    "https://api.firecrawl.dev/v1/search",
                    headers=headers,
                    json=request_body,
                    timeout=aiohttp.ClientTimeout(total=timeout/1000)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "error": f"Firecrawl API error ({response.status}): {error_text}"
                        }
                    
                    result = await response.json()
                    
                    if not result.get("success"):
                        return {
                            "success": False,
                            "error": result.get("error", "Search and scrape failed")
                        }
                    
                    # Process results
                    processed_results = []
                    for item in result.get("data", []):
                        processed_item = {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("description", ""),
                        }
                        
                        if "markdown" in formats:
                            processed_item["markdown"] = clean_markdown(
                                item.get("markdown", ""), 
                                item.get("url")
                            )
                        
                        if "extract" in formats:
                            processed_item["extract"] = item.get("extract", "No extract available")
                        
                        processed_results.append(processed_item)
                    
                    return {
                        "success": True,
                        "query": query,
                        "total_results": len(processed_results),
                        "results": processed_results
                    }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Webscrape failed: {str(e)}",
            "query": query,
            "url": url
        } 
"""
FAQ and Template Manager for GdG-Help-Bot.
Handles fetching index, markdown files, templates, images, and fuzzy searching.
"""

import os
import re
import time
import json
import logging
import aiohttp
from typing import Optional, List, Dict, Tuple, Any
from thefuzz import fuzz

import config

logger = logging.getLogger(__name__)

# In-memory index cache
_INDEX_CACHE: Optional[Dict[str, Any]] = None
_INDEX_CACHE_TIME: float = 0.0

# In-memory file content cache (path -> (content, timestamp))
_CONTENT_CACHE: Dict[str, Tuple[str, float]] = {}


async def _fetch_url_text(url: str) -> Optional[str]:
    """Fetches text content from an HTTP URL asynchronously."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.text()
                logger.warning("Failed to fetch %s: HTTP %s", url, response.status)
    except Exception as e:
        logger.warning("Error fetching %s: %s", url, e)
    return None


async def get_faq_index(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns the FAQ index dictionary.
    Caches the index in memory for config.FAQ_CACHE_TTL seconds.
    Tries GitHub first, then falls back to local file.
    """
    global _INDEX_CACHE, _INDEX_CACHE_TIME
    now = time.time()

    if not force_refresh and _INDEX_CACHE and (now - _INDEX_CACHE_TIME < config.FAQ_CACHE_TTL):
        return _INDEX_CACHE

    index_data = None

    # 1. Try fetching from GitHub
    if config.GITHUB_RAW_BASE_URL:
        remote_url = f"{config.GITHUB_RAW_BASE_URL}/faq_index.json"
        text = await _fetch_url_text(remote_url)
        if text:
            try:
                index_data = json.loads(text)
                logger.info("Loaded FAQ index from GitHub raw URL.")
            except json.JSONDecodeError as e:
                logger.error("Error decoding remote faq_index.json: %s", e)

    # 2. Fallback to local file if needed
    if index_data is None and config.USE_LOCAL_FALLBACK:
        local_path = "faq_index.json"
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
                    logger.info("Loaded FAQ index from local file.")
            except Exception as e:
                logger.error("Error loading local faq_index.json: %s", e)

    # 3. Default empty index if still not found
    if index_data is None:
        index_data = {"version": 1, "categories": [], "root_files": []}

    _INDEX_CACHE = index_data
    _INDEX_CACHE_TIME = now
    return _INDEX_CACHE


async def get_faq_by_id(faq_id: str) -> Optional[Dict[str, Any]]:
    """Finds an FAQ item by its short ID."""
    index = await get_faq_index()
    for root_file in index.get("root_files", []):
        if root_file.get("id") == faq_id:
            return root_file
    for cat in index.get("categories", []):
        for f in cat.get("files", []):
            if f.get("id") == faq_id:
                return f
    return None


async def get_category_by_id(cat_id: str) -> Optional[Dict[str, Any]]:
    """Finds a category by its short ID."""
    index = await get_faq_index()
    for cat in index.get("categories", []):
        if cat.get("id") == cat_id:
            return cat
    return None


def extract_images_and_clean_text(raw_markdown: str, base_file_path: str) -> Tuple[str, List[str]]:
    """
    Parses Markdown text, extracts image references: ![alt](path_or_url),
    resolves relative paths to full GitHub URLs or local paths,
    and removes the markdown image tags so text is clean for Telegram.
    """
    image_regex = r"!\[(.*?)\]\((.*?)\)"
    images = []

    def replace_image(match):
        alt = match.group(1)
        img_src = match.group(2).strip()

        # Check if URL is absolute
        if img_src.startswith("http://") or img_src.startswith("https://"):
            images.append(img_src)
        else:
            clean_src = img_src.lstrip("/")
            if clean_src.startswith("./"):
                clean_src = clean_src[2:]

            if not clean_src.startswith("FAQ/"):
                file_dir = os.path.dirname(base_file_path)
                combined = os.path.normpath(os.path.join(file_dir, clean_src)).replace("\\", "/")
                resolved_rel = combined
            else:
                resolved_rel = clean_src

            if config.GITHUB_RAW_BASE_URL:
                full_url = f"{config.GITHUB_RAW_BASE_URL}/{resolved_rel}"
                images.append(full_url)
            else:
                images.append(resolved_rel)

        return f"🖼 *[Immagine: {alt}]*" if alt else ""

    cleaned_text = re.sub(image_regex, replace_image, raw_markdown)
    return cleaned_text.strip(), images

async def load_faq_file(rel_path: str) -> Tuple[str, List[str]]:
    """
    Loads markdown content from GitHub or local file, and extracts images.
    Returns (cleaned_markdown, list_of_image_urls_or_paths).
    """
    global _CONTENT_CACHE
    now = time.time()

    raw_text = None
    if rel_path in _CONTENT_CACHE:
        cached_text, cache_ts = _CONTENT_CACHE[rel_path]
        if now - cache_ts < config.FAQ_CACHE_TTL:
            raw_text = cached_text

    if raw_text is None:
        # 1. Try remote
        if config.GITHUB_RAW_BASE_URL:
            remote_url = f"{config.GITHUB_RAW_BASE_URL}/{rel_path.lstrip('/')}"
            fetched = await _fetch_url_text(remote_url)
            if fetched:
                raw_text = fetched

        # 2. Try local fallback
        if raw_text is None and config.USE_LOCAL_FALLBACK:
            if os.path.exists(rel_path):
                try:
                    with open(rel_path, "r", encoding="utf-8") as f:
                        raw_text = f.read()
                except Exception as e:
                    logger.error("Failed to read local file %s: %s", rel_path, e)

        if raw_text is not None:
            _CONTENT_CACHE[rel_path] = (raw_text, now)

    if raw_text is None:
        return "⚠️ *Errore:* Impossibile caricare il contenuto di questa FAQ.", []

    return extract_images_and_clean_text(raw_text, rel_path)


async def get_template(template_name: str) -> str:
    """
    Loads a template markdown file (e.g. greeting.md, admins.md).
    Tries remote templates first, then local templates directory.
    """
    rel_path = f"templates/{template_name}"

    # Try remote
    if config.GITHUB_RAW_BASE_URL:
        remote_url = f"{config.GITHUB_RAW_BASE_URL}/{rel_path}"
        fetched = await _fetch_url_text(remote_url)
        if fetched:
            return fetched

    # Try local
    if os.path.exists(rel_path):
        try:
            with open(rel_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error("Failed to read local template %s: %s", rel_path, e)

    return f"Template {template_name} non trovato."


async def search_faqs(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Performs fuzzy search across all FAQs (title, category name, preview).
    Returns list of items sorted by relevance.
    """
    index = await get_faq_index()
    query_clean = query.strip().lower()
    if not query_clean:
        return []

    scored_items = []

    def score_entry(item: Dict[str, Any], cat_name: str = ""):
        title = item.get("title", "")
        preview = item.get("preview", "")

        title_score = fuzz.token_set_ratio(query_clean, title.lower())
        preview_score = fuzz.token_set_ratio(query_clean, preview.lower())
        cat_score = fuzz.token_set_ratio(query_clean, cat_name.lower()) if cat_name else 0

        if query_clean in title.lower():
            title_score = max(title_score, 90)

        combined_score = max(title_score, int(preview_score * 0.7), int(cat_score * 0.6))
        return combined_score

    for item in index.get("root_files", []):
        score = score_entry(item)
        if score >= 45:
            scored_items.append((score, {**item, "category_name": "Generale"}))

    for cat in index.get("categories", []):
        cat_name = cat.get("name", "")
        for item in cat.get("files", []):
            score = score_entry(item, cat_name)
            if score >= 45:
                scored_items.append((score, {**item, "category_name": cat_name}))

    scored_items.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored_items[:limit]]


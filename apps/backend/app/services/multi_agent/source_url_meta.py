"""
Классификация URL и MIME для AgentPayload.Source.

Используется ResearchAgent (после HTTP) и DiscoveryAgent (эвристика по URL).
См. docs/MULTI_AGENT_V2_CONCEPT.md — поле Source.resource_kind / mime_type.
"""

from __future__ import annotations

from typing import Tuple
from urllib.parse import urlparse

# Расширение пути → resource_kind (без ответа сервера)
_URL_EXT_KIND: tuple[tuple[str, str], ...] = (
    (".jpg", "image"),
    (".jpeg", "image"),
    (".png", "image"),
    (".gif", "image"),
    (".webp", "image"),
    (".bmp", "image"),
    (".ico", "image"),
    (".svg", "image"),
    (".mp4", "video"),
    (".webm", "video"),
    (".mov", "video"),
    (".mkv", "video"),
    (".mp3", "audio"),
    (".wav", "audio"),
    (".ogg", "audio"),
    (".m4a", "audio"),
    (".flac", "audio"),
    (".pdf", "pdf"),
    (".json", "json"),
    (".xml", "xml"),
    (".rss", "feed"),
    (".atom", "feed"),
)


def normalize_mime_header(value: str) -> str:
    """Основной MIME без параметров (charset и т.д.)."""
    if not value:
        return ""
    return value.split(";")[0].strip().lower()


def infer_resource_kind_from_url(url: str) -> Tuple[str, str]:
    """
    Эвристика по пути URL без HTTP.

    Returns:
        (mime_hint_or_empty, resource_kind)
    """
    try:
        path = urlparse(url or "").path.lower()
    except Exception:
        return "", "unknown"
    for ext, kind in _URL_EXT_KIND:
        if path.endswith(ext):
            return "", kind
    return "", "unknown"


def classify_resource_from_http(
    content_type_header: str,
    url: str,
) -> Tuple[str, str]:
    """
    Классификация по заголовку Content-Type и при необходимости по URL.

    Returns:
        (mime_normalized, resource_kind)
    """
    mime = normalize_mime_header(content_type_header or "")
    if not mime:
        return infer_resource_kind_from_url(url)

    if mime in ("text/html", "application/xhtml+xml"):
        return mime, "html_page"
    if mime.startswith("image/"):
        return mime, "image"
    if mime.startswith("video/"):
        return mime, "video"
    if mime.startswith("audio/"):
        return mime, "audio"
    if mime.startswith("text/"):
        if "xml" in mime or mime == "text/xml":
            return mime, "xml"
        return mime, "text"
    if "application/json" in mime or mime.endswith("+json"):
        return mime, "json"
    if "xml" in mime or mime == "application/xml":
        return mime, "xml"
    if mime == "application/pdf" or mime.endswith("/pdf"):
        return mime, "pdf"
    if "rss" in mime or "atom" in mime:
        return mime, "feed"
    if mime.startswith("application/vnd.ms-") or mime.startswith(
        "application/vnd.openxmlformats"
    ):
        return mime, "document"
    if mime == "application/octet-stream":
        return infer_resource_kind_from_url(url)
    if mime.startswith("application/"):
        return mime, "other"
    return mime, "other"

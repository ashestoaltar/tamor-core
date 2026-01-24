# routes/references_api.py
"""
API endpoints for scripture reference lookup and module management.

Provides access to:
- Scripture passage lookup from SWORD and Sefaria
- Translation comparison
- SWORD module download and management
- Reference detection in text
"""

from flask import Blueprint, request, jsonify

from services.references import (
    ReferenceService,
    SwordManager,
    SwordModuleError,
    SefariaNetworkError,
)

references_bp = Blueprint("references_api", __name__, url_prefix="/api/references")

# Lazily initialized service instances
_service = None
_manager = None


def get_service() -> ReferenceService:
    """Get or create ReferenceService instance."""
    global _service
    if _service is None:
        _service = ReferenceService()
    return _service


def get_manager() -> SwordManager:
    """Get or create SwordManager instance."""
    global _manager
    if _manager is None:
        _manager = SwordManager()
    return _manager


# =============================================================================
# Lookup Endpoints
# =============================================================================

@references_bp.get("/lookup")
def lookup_reference():
    """
    Look up a scripture passage.

    Query params:
        ref: Reference string (required) e.g., "Genesis 1:1-3"
        sources: Comma-separated sources (optional) e.g., "sword,sefaria"
        translations: Comma-separated translations (optional) e.g., "KJV,WEB"

    Returns:
        {
            "ref": "Genesis 1:1-3",
            "results": [
                {
                    "source": "sword",
                    "translation": "KJV",
                    "text": "In the beginning...",
                    ...
                }
            ]
        }
    """
    ref = request.args.get("ref")
    if not ref:
        return jsonify({"error": "ref parameter required"}), 400

    sources = request.args.get("sources")
    sources = sources.split(",") if sources else None

    translations = request.args.get("translations")
    translations = translations.split(",") if translations else None

    try:
        service = get_service()
        results = service.lookup(ref, sources=sources, translations=translations)
        return jsonify({
            "ref": ref,
            "results": [r.to_dict() for r in results]
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except SefariaNetworkError as e:
        return jsonify({"error": "Sefaria network error", "detail": str(e)}), 503
    except Exception as e:
        return jsonify({"error": "Lookup failed", "detail": str(e)}), 500


@references_bp.get("/compare")
def compare_translations():
    """
    Compare multiple translations of a passage.

    Query params:
        ref: Reference string (required)
        translations: Comma-separated translation codes (required) e.g., "KJV,WEB,ASV"
        include_sefaria: Include Sefaria English (optional, default false)

    Returns:
        {
            "ref": "John 3:16",
            "translations": [...]
        }
    """
    ref = request.args.get("ref")
    translations = request.args.get("translations")

    if not ref or not translations:
        return jsonify({"error": "ref and translations parameters required"}), 400

    trans_list = [t.strip() for t in translations.split(",")]
    include_sefaria = request.args.get("include_sefaria", "").lower() == "true"

    try:
        service = get_service()
        results = service.compare(ref, trans_list, include_sefaria=include_sefaria)
        return jsonify({
            "ref": ref,
            "translations": [r.to_dict() for r in results]
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Comparison failed", "detail": str(e)}), 500


@references_bp.get("/search")
def search_references():
    """
    Search for references containing keywords.

    Query params:
        q: Search query (required)
        sources: Comma-separated sources (optional, default "sefaria")
        limit: Maximum results (optional, default 20)

    Returns:
        {
            "query": "love",
            "results": [...]
        }
    """
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "q parameter required"}), 400

    sources = request.args.get("sources")
    sources = sources.split(",") if sources else None

    limit = request.args.get("limit", 20, type=int)

    try:
        service = get_service()
        results = service.search(query, sources=sources, max_results=limit)
        return jsonify({"query": query, "results": results})
    except Exception as e:
        return jsonify({"error": "Search failed", "detail": str(e)}), 500


@references_bp.get("/commentary")
def get_commentary():
    """
    Get passage with commentary from Sefaria.

    Query params:
        ref: Reference string (required)
        commentator: Specific commentator (optional) e.g., "Rashi"

    Returns:
        Reference object with commentary field
    """
    ref = request.args.get("ref")
    if not ref:
        return jsonify({"error": "ref parameter required"}), 400

    commentator = request.args.get("commentator")

    try:
        service = get_service()
        result = service.get_with_commentary(ref, commentator=commentator)
        if not result:
            return jsonify({"error": "Reference not found"}), 404
        return jsonify(result.to_dict())
    except SefariaNetworkError as e:
        return jsonify({"error": "Sefaria network error", "detail": str(e)}), 503
    except Exception as e:
        return jsonify({"error": "Commentary lookup failed", "detail": str(e)}), 500


@references_bp.get("/cross-references")
def get_cross_references():
    """
    Get cross-references for a passage.

    Query params:
        ref: Reference string (required)

    Returns:
        {
            "ref": "John 3:16",
            "cross_references": [...]
        }
    """
    ref = request.args.get("ref")
    if not ref:
        return jsonify({"error": "ref parameter required"}), 400

    try:
        service = get_service()
        cross_refs = service.get_cross_references(ref)
        return jsonify({
            "ref": ref,
            "cross_references": cross_refs
        })
    except Exception as e:
        return jsonify({"error": "Cross-reference lookup failed", "detail": str(e)}), 500


@references_bp.post("/detect")
def detect_references():
    """
    Find scripture references in text.

    Request body:
        {
            "text": "Read John 3:16 and Romans 8:28 for encouragement."
        }

    Returns:
        {
            "references": [
                {"ref": "John 3:16", "book": "John", "chapter": 3, ...},
                ...
            ]
        }
    """
    data = request.json or {}
    text = data.get("text")

    if not text:
        return jsonify({"error": "text parameter required"}), 400

    try:
        service = get_service()
        detected = service.detect_references(text)
        return jsonify({
            "references": [
                {
                    "ref": r.normalized,
                    "book": r.book,
                    "chapter": r.chapter,
                    "verse_start": r.verse_start,
                    "verse_end": r.verse_end,
                    "original": r.original,
                }
                for r in detected
            ]
        })
    except Exception as e:
        return jsonify({"error": "Detection failed", "detail": str(e)}), 500


# =============================================================================
# Translation/Module Endpoints
# =============================================================================

@references_bp.get("/translations")
def list_translations():
    """
    List available Bible translations.

    Returns:
        {
            "translations": [
                {"code": "KJV", "name": "King James Version", "installed": true, ...},
                ...
            ]
        }
    """
    try:
        service = get_service()
        return jsonify({"translations": service.get_translations()})
    except Exception as e:
        return jsonify({"error": "Failed to list translations", "detail": str(e)}), 500


@references_bp.get("/modules/available")
def list_available_modules():
    """
    List SWORD modules available for download.

    Returns:
        {
            "modules": [
                {"code": "KJV", "name": "King James Version", "installed": false, ...},
                ...
            ]
        }
    """
    try:
        manager = get_manager()
        return jsonify({"modules": manager.list_available()})
    except Exception as e:
        return jsonify({"error": "Failed to list modules", "detail": str(e)}), 500


@references_bp.get("/modules/installed")
def list_installed_modules():
    """
    List locally installed SWORD modules.

    Returns:
        {
            "modules": ["KJV", "WEB", ...]
        }
    """
    try:
        manager = get_manager()
        return jsonify({"modules": manager.list_installed()})
    except Exception as e:
        return jsonify({"error": "Failed to list installed modules", "detail": str(e)}), 500


@references_bp.post("/modules/download")
def download_module():
    """
    Download and install a SWORD module.

    Request body:
        {
            "module": "KJV"
        }

    Returns:
        {
            "success": true,
            "module": "KJV"
        }
    """
    data = request.json or {}
    module = data.get("module")

    if not module:
        return jsonify({"error": "module parameter required"}), 400

    try:
        manager = get_manager()
        manager.download_module(module)
        return jsonify({"success": True, "module": module})
    except SwordModuleError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Download failed", "detail": str(e)}), 500


@references_bp.delete("/modules/<module_name>")
def remove_module(module_name: str):
    """
    Remove an installed SWORD module.

    Path params:
        module_name: Module code to remove (e.g., "KJV")

    Returns:
        {
            "success": true,
            "module": "KJV"
        }
    """
    try:
        manager = get_manager()
        removed = manager.remove_module(module_name)
        if removed:
            return jsonify({"success": True, "module": module_name})
        else:
            return jsonify({"error": f"Module {module_name} not installed"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Book/Chapter Info Endpoints
# =============================================================================

@references_bp.get("/book/<book_name>")
def get_book_info(book_name: str):
    """
    Get information about a Bible book.

    Path params:
        book_name: Book name (e.g., "Genesis", "John")

    Query params:
        translation: SWORD translation code (optional)

    Returns:
        {
            "name": "Genesis",
            "num_chapters": 50,
            "chapter_lengths": [31, 25, ...],
            ...
        }
    """
    translation = request.args.get("translation")

    try:
        service = get_service()
        info = service.get_book_info(book_name, translation)
        if not info:
            return jsonify({"error": f"Book not found: {book_name}"}), 404
        return jsonify(info)
    except Exception as e:
        return jsonify({"error": "Failed to get book info", "detail": str(e)}), 500


# =============================================================================
# Cache Management Endpoints
# =============================================================================

@references_bp.get("/cache/stats")
def cache_stats():
    """
    Get cache statistics.

    Returns:
        {
            "sefaria": {
                "total_files": 10,
                "total_size_mb": 0.5,
                ...
            }
        }
    """
    try:
        service = get_service()
        return jsonify(service.cache_stats())
    except Exception as e:
        return jsonify({"error": "Failed to get cache stats", "detail": str(e)}), 500


@references_bp.post("/cache/clear")
def clear_cache():
    """
    Clear cached data.

    Request body:
        {
            "older_than_days": 30  (optional)
        }

    Returns:
        {
            "sefaria": 5  (number of files cleared)
        }
    """
    data = request.json or {}
    older_than_days = data.get("older_than_days")

    try:
        service = get_service()
        result = service.clear_cache(older_than_days)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": "Failed to clear cache", "detail": str(e)}), 500

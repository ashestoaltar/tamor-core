"""
Integrations API

Phase 6.4: Plugin Framework Expansion

API endpoints for external tool integrations (Zotero, etc.).
"""

from flask import Blueprint, jsonify, request

from utils.auth import ensure_user

integrations_bp = Blueprint("integrations_api", __name__, url_prefix="/api/integrations")


# ---------------------------------------------------------------------------
# Zotero Integration
# ---------------------------------------------------------------------------


@integrations_bp.get("/zotero/status")
def zotero_status():
    """Check if Zotero is available."""
    from services.integrations.zotero import check_zotero_available

    user_id, err = ensure_user()
    if err:
        return err

    # Check for custom path from plugin config
    custom_path = request.args.get("path")

    return jsonify(check_zotero_available(custom_path))


@integrations_bp.get("/zotero/collections")
def zotero_collections():
    """Get Zotero collections."""
    from services.integrations.zotero import get_zotero_reader

    user_id, err = ensure_user()
    if err:
        return err

    try:
        reader = get_zotero_reader()
        collections = reader.get_collections()
        return jsonify({"collections": collections})
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "available": False}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.get("/zotero/items")
def zotero_items():
    """Get Zotero items."""
    from services.integrations.zotero import get_zotero_reader

    user_id, err = ensure_user()
    if err:
        return err

    collection_id = request.args.get("collection_id", type=int)
    item_type = request.args.get("type")
    limit = request.args.get("limit", 100, type=int)

    try:
        reader = get_zotero_reader()
        items = reader.get_items(
            collection_id=collection_id,
            item_type=item_type,
            limit=min(limit, 500),  # Cap at 500
        )

        return jsonify({
            "items": [
                {
                    "key": item.key,
                    "type": item.item_type,
                    "title": item.title,
                    "creators": item.creators,
                    "date": item.date,
                    "abstract": item.abstract[:500] + "..." if item.abstract and len(item.abstract) > 500 else item.abstract,
                    "url": item.url,
                    "doi": item.doi,
                    "tags": item.tags,
                    "has_pdf": any(
                        a.get("content_type") == "application/pdf"
                        for a in item.attachments
                    ),
                }
                for item in items
            ],
            "count": len(items),
        })
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "available": False}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.get("/zotero/items/<key>")
def zotero_item_detail(key: str):
    """Get detailed info for a specific Zotero item."""
    from services.integrations.zotero import get_zotero_reader

    user_id, err = ensure_user()
    if err:
        return err

    try:
        reader = get_zotero_reader()
        item = reader.get_item_by_key(key)

        if not item:
            return jsonify({"error": "Item not found"}), 404

        pdf_path = reader.get_pdf_path(item)

        return jsonify({
            "key": item.key,
            "type": item.item_type,
            "title": item.title,
            "creators": item.creators,
            "date": item.date,
            "abstract": item.abstract,
            "url": item.url,
            "doi": item.doi,
            "tags": item.tags,
            "attachments": [
                {
                    "key": a["key"],
                    "content_type": a.get("content_type"),
                    "has_file": "full_path" in a,
                }
                for a in item.attachments
            ],
            "has_pdf": pdf_path is not None,
            "citation": reader.format_citation(item),
        })
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "available": False}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.get("/zotero/items/<key>/citation")
def zotero_citation(key: str):
    """Get formatted citation for an item."""
    from services.integrations.zotero import get_zotero_reader

    user_id, err = ensure_user()
    if err:
        return err

    style = request.args.get("style", "apa")

    try:
        reader = get_zotero_reader()
        item = reader.get_item_by_key(key)

        if not item:
            return jsonify({"error": "Item not found"}), 404

        return jsonify({
            "key": key,
            "citation": reader.format_citation(item, style),
            "style": style,
        })
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "available": False}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@integrations_bp.get("/zotero/search")
def zotero_search():
    """Search Zotero items."""
    from services.integrations.zotero import get_zotero_reader

    user_id, err = ensure_user()
    if err:
        return err

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' required"}), 400

    limit = request.args.get("limit", 50, type=int)

    try:
        reader = get_zotero_reader()
        items = reader.search_items(query, limit=min(limit, 100))

        return jsonify({
            "query": query,
            "items": [
                {
                    "key": item.key,
                    "type": item.item_type,
                    "title": item.title,
                    "creators": item.creators,
                    "date": item.date,
                    "tags": item.tags,
                    "has_pdf": any(
                        a.get("content_type") == "application/pdf"
                        for a in item.attachments
                    ),
                }
                for item in items
            ],
            "count": len(items),
        })
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "available": False}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

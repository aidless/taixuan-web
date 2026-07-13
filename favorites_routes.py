"""
taixuan-web v2.0 favorites routes (Flask Blueprint).
Mount: app.register_blueprint(favorites_bp, url_prefix="/api/v2/favorites")
"""
from flask import Blueprint, request, jsonify

import user_system

favorites_bp = Blueprint("favorites", __name__)


@favorites_bp.route("", methods=["POST"])
@user_system.require_auth
def add_favorite(user):
    """POST /api/v2/favorites
    Header: Authorization
    Body: {"reading_id": int, "note": str?}
    Resp: 200 {favorite_id}
          400 {error: msg}
    """
    data = request.get_json(silent=True) or {}
    reading_id = data.get("reading_id")
    if not isinstance(reading_id, int) or reading_id <= 0:
        return jsonify({"error": "reading_id must be a positive integer"}), 400
    note = (data.get("note") or "").strip() or None

    fav_id = user_system.add_favorite(user["user_id"], reading_id, note)
    if fav_id is None:
        return jsonify({"error": "reading not found or already favorited"}), 400

    # v1.3 analytics
    try:
        import analytics
        analytics.track_event(
            name="favorite",
            user_id=user["user_id"],
            liupai=None,
            payload={"reading_id": reading_id, "favorite_id": fav_id},
        )
    except Exception:
        pass

    return jsonify({"favorite_id": fav_id}), 200


@favorites_bp.route("", methods=["GET"])
@user_system.require_auth
def list_favorites(user):
    """GET /api/v2/favorites?limit=50
    Header: Authorization
    Resp: 200 [{favorite_id, reading_id, liupai, question, summary, note, created_at}, ...]
    """
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    limit = max(1, min(limit, 200))  # clamp to [1, 200]

    items = user_system.list_favorites(user["user_id"], limit)
    return jsonify({"count": len(items), "items": items}), 200


@favorites_bp.route("/<int:favorite_id>", methods=["DELETE"])
@user_system.require_auth
def remove_favorite(user, favorite_id):
    """DELETE /api/v2/favorites/<id>
    Header: Authorization
    Resp: 200 {ok: true}
          404 {error: "not found"}
    """
    ok = user_system.remove_favorite(user["user_id"], favorite_id)
    if not ok:
        return jsonify({"error": "not found"}), 404
    return jsonify({"ok": True}), 200
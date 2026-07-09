from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# Accepted image types for profile pic (includes gif)
ALLOWED_IMAGE_PREFIXES = ("data:image/png", "data:image/jpeg", "data:image/jpg", "data:image/gif", "data:image/webp")
MAX_PROFILE_PIC_SIZE = 3 * 1024 * 1024  # ~3MB as base64 text, generous for a small demo


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "User already exists"}), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"token": token, "user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404
    return jsonify(user.to_dict()), 200


@auth_bp.route("/profile-pic", methods=["PATCH"])
@jwt_required()
def update_profile_pic():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(silent=True) or {}
    image_data = data.get("image")  # base64 data URL, e.g. "data:image/gif;base64,...."

    if not image_data:
        return jsonify({"error": "No image provided"}), 400
    if not image_data.startswith(ALLOWED_IMAGE_PREFIXES):
        return jsonify({"error": "Unsupported image type. Use PNG, JPEG, GIF, or WEBP."}), 400
    if len(image_data) > MAX_PROFILE_PIC_SIZE:
        return jsonify({"error": "Image too large. Keep it under ~2MB."}), 400

    user.profile_pic = image_data
    db.session.commit()

    return jsonify({"status": "success", "user": user.to_dict()}), 200


@auth_bp.route("/profile-pic", methods=["DELETE"])
@jwt_required()
def delete_profile_pic():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404

    user.profile_pic = None
    db.session.commit()
    return jsonify({"status": "success", "user": user.to_dict()}), 200


@auth_bp.route("/account", methods=["DELETE"])
@jwt_required()
def delete_account():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(user)  # cascades to trades via relationship config
    db.session.commit()
    return jsonify({"status": "success", "message": "Account deleted"}), 200
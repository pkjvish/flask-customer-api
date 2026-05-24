"""
Flask Customer CRUD API
Routes:
  GET    /health                → health check
  GET    /api/v1/customers      → list all customers  (supports ?page=1&limit=10)
  POST   /api/v1/customers      → create customer
  GET    /api/v1/customers/<id> → get one customer
  PUT    /api/v1/customers/<id> → full update
  PATCH  /api/v1/customers/<id> → partial update
  DELETE /api/v1/customers/<id> → delete customer
"""

from flask import Flask, request, jsonify
from db import get_db, init_db, init_app
import logging
import time
import os

# ── Logging setup — JSON-style lines so CloudWatch Insights can query them ──
logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "msg": %(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("customer-api")

app = Flask(__name__)
init_app(app)


# ── Startup ──────────────────────────────────────────────────────────────────

logger.info('"app starting — reading env config"')
logger.info('"DB_HOST=%s DB_NAME=%s DB_USER=%s"',
            os.environ.get("DB_HOST", "NOT SET"),
            os.environ.get("DB_NAME", "NOT SET"),
            os.environ.get("DB_USER", "NOT SET"))

with app.app_context():
    try:
        logger.info('"attempting DB init"')
        init_db()
        logger.info('"DB init successful"')
    except Exception as e:
        logger.warning('"DB init deferred: %s"', e)


# ── Request / response logging ───────────────────────────────────────────────

@app.before_request
def log_request():
    request._start_time = time.time()
    logger.info('"incoming request" method="%s" path="%s" remote_addr="%s"',
                request.method, request.path, request.remote_addr)


@app.after_request
def log_response(response):
    duration_ms = round((time.time() - getattr(request, "_start_time", time.time())) * 1000, 2)
    logger.info('"response" method="%s" path="%s" status=%s duration_ms=%s',
                request.method, request.path, response.status_code, duration_ms)
    return response


# ── Helpers ──────────────────────────────────────────────────────────────────

def _customer_row_to_dict(row) -> dict:
    return {
        "id":         row["id"],
        "first_name": row["first_name"],
        "last_name":  row["last_name"],
        "email":      row["email"],
        "phone":      row["phone"],
        "address":    row["address"],
        "city":       row["city"],
        "country":    row["country"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _validate_required(data: dict, fields: list) -> str | None:
    """Return an error message if any required field is missing/empty."""
    for f in fields:
        if not data.get(f, "").strip():
            return f"Field '{f}' is required and cannot be empty."
    return None


# ── Health ───────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    try:
        db = get_db()
        db.execute("SELECT 1")
        db_status = "connected"
        logger.info('"health check passed — DB connected"')
    except Exception as exc:
        logger.warning('"health check — DB unavailable: %s"', exc)
        db_status = "unavailable"
    # Always return 200 — ECS health check must not fail due to DB
    return jsonify({"status": "healthy", "service": "customer-api",
                    "database": db_status}), 200


# ── List customers ───────────────────────────────────────────────────────────

@app.route("/api/v1/customers", methods=["GET"])
def list_customers():
    logger.info('"list_customers called"')
    try:
        page  = max(int(request.args.get("page",  1)), 1)
        limit = min(int(request.args.get("limit", 10)), 100)
    except ValueError:
        logger.warning('"list_customers — invalid pagination params"')
        return jsonify({"error": "page and limit must be integers"}), 400

    offset = (page - 1) * limit
    db     = get_db()

    total = db.execute("SELECT COUNT(*) AS cnt FROM customers").fetchone()["cnt"]
    rows  = db.execute(
        "SELECT * FROM customers ORDER BY id LIMIT %s OFFSET %s",
        (limit, offset)
    ).fetchall()

    return jsonify({
        "data":        [_customer_row_to_dict(r) for r in rows],
        "page":        page,
        "limit":       limit,
        "total":       total,
        "total_pages": max(1, -(-total // limit)),   # ceiling division
    }), 200


# ── Create customer ──────────────────────────────────────────────────────────

@app.route("/api/v1/customers", methods=["POST"])
def create_customer():
    logger.info('"create_customer called"')
    data = request.get_json(silent=True)
    if not data:
        logger.warning('"create_customer — missing or invalid JSON body"')
        return jsonify({"error": "Request body must be valid JSON"}), 400

    err = _validate_required(data, ["first_name", "last_name", "email"])
    if err:
        return jsonify({"error": err}), 400

    db = get_db()

    # Unique email check
    existing = db.execute(
        "SELECT id FROM customers WHERE email = %s", (data["email"],)
    ).fetchone()
    if existing:
        logger.warning('"create_customer — duplicate email: %s"', data["email"])
        return jsonify({"error": f"Email '{data['email']}' is already registered"}), 409

    cursor = db.execute(
        """INSERT INTO customers (first_name, last_name, email, phone, address, city, country)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            data["first_name"].strip(),
            data["last_name"].strip(),
            data["email"].strip().lower(),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("city", ""),
            data.get("country", ""),
        ),
    )
    db.commit()

    new_id = cursor.lastrowid
    logger.info('"create_customer — created id=%s"', new_id)
    row    = db.execute("SELECT * FROM customers WHERE id = %s", (new_id,)).fetchone()
    return jsonify(_customer_row_to_dict(row)), 201


# ── Get one customer ─────────────────────────────────────────────────────────

@app.route("/api/v1/customers/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    db  = get_db()
    row = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if not row:
        return jsonify({"error": f"Customer {customer_id} not found"}), 404
    return jsonify(_customer_row_to_dict(row)), 200


# ── Full update (PUT) ────────────────────────────────────────────────────────

@app.route("/api/v1/customers/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    err = _validate_required(data, ["first_name", "last_name", "email"])
    if err:
        return jsonify({"error": err}), 400

    db  = get_db()
    row = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if not row:
        return jsonify({"error": f"Customer {customer_id} not found"}), 404

    # Unique email check (exclude self)
    conflict = db.execute(
        "SELECT id FROM customers WHERE email = %s AND id != %s",
        (data["email"], customer_id)
    ).fetchone()
    if conflict:
        return jsonify({"error": f"Email '{data['email']}' is already registered"}), 409

    db.execute(
        """UPDATE customers
           SET first_name=%s, last_name=%s, email=%s, phone=%s,
               address=%s, city=%s, country=%s
           WHERE id=%s""",
        (
            data["first_name"].strip(),
            data["last_name"].strip(),
            data["email"].strip().lower(),
            data.get("phone", ""),
            data.get("address", ""),
            data.get("city", ""),
            data.get("country", ""),
            customer_id,
        ),
    )
    db.commit()

    updated = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    return jsonify(_customer_row_to_dict(updated)), 200


# ── Partial update (PATCH) ───────────────────────────────────────────────────

@app.route("/api/v1/customers/<int:customer_id>", methods=["PATCH"])
def patch_customer(customer_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    db  = get_db()
    row = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if not row:
        return jsonify({"error": f"Customer {customer_id} not found"}), 404

    allowed = {"first_name", "last_name", "email", "phone", "address", "city", "country"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": f"No valid fields provided. Allowed: {sorted(allowed)}"}), 400

    if "email" in updates:
        conflict = db.execute(
            "SELECT id FROM customers WHERE email = %s AND id != %s",
            (updates["email"], customer_id)
        ).fetchone()
        if conflict:
            return jsonify({"error": f"Email '{updates['email']}' is already registered"}), 409

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    db.execute(
        f"UPDATE customers SET {set_clause} WHERE id = %s",
        (*updates.values(), customer_id),
    )
    db.commit()

    updated = db.execute("SELECT * FROM customers WHERE id = %s", (customer_id,)).fetchone()
    return jsonify(_customer_row_to_dict(updated)), 200


# ── Delete customer ──────────────────────────────────────────────────────────

@app.route("/api/v1/customers/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id):
    db  = get_db()
    row = db.execute("SELECT id FROM customers WHERE id = %s", (customer_id,)).fetchone()
    if not row:
        return jsonify({"error": f"Customer {customer_id} not found"}), 404

    db.execute("DELETE FROM customers WHERE id = %s", (customer_id,))
    db.commit()
    return jsonify({"message": f"Customer {customer_id} deleted successfully"}), 200


# ── Error handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_):
    logger.warning('"404 — endpoint not found: %s %s"', request.method, request.path)
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_):
    logger.warning('"405 — method not allowed: %s %s"', request.method, request.path)
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(500)
def internal_error(exc):
    logger.error('"500 — unhandled exception: %s"', exc, exc_info=True)
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

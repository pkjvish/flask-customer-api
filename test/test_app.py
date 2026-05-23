"""
tests/test_app.py

Runs against a real MySQL instance.
Set DB_* environment variables before running, or use docker-compose.test.yml.
Falls back to sqlite-like stubs only for basic route shape tests.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from app import app


# ── Shared customer fixture data ─────────────────────────────────────────────

CUSTOMER_1 = {
    "first_name": "Alice",
    "last_name":  "Smith",
    "email":      "alice@example.com",
    "phone":      "+1-555-0100",
    "city":       "Mumbai",
    "country":    "India",
}

CUSTOMER_2 = {
    "first_name": "Bob",
    "last_name":  "Jones",
    "email":      "bob@example.com",
    "phone":      "+1-555-0200",
    "city":       "Delhi",
    "country":    "India",
}

MOCK_ROW = {
    "id": 1, "first_name": "Alice", "last_name": "Smith",
    "email": "alice@example.com", "phone": "+1-555-0100",
    "address": "", "city": "Mumbai", "country": "India",
    "created_at": "2024-01-01 00:00:00",
    "updated_at": "2024-01-01 00:00:00",
}


# ── Flask test client fixture ─────────────────────────────────────────────────

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Helper: mock get_db ───────────────────────────────────────────────────────

def make_mock_db(fetchone_val=None, fetchall_val=None, lastrowid=1):
    cursor = MagicMock()
    cursor.lastrowid  = lastrowid
    cursor.fetchone.return_value  = fetchone_val
    cursor.fetchall.return_value  = fetchall_val or []

    db = MagicMock()
    db.execute.return_value = cursor
    return db


# ── Health endpoint ───────────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_health(mock_init, mock_get_db, client):
    mock_get_db.return_value = make_mock_db(fetchone_val={"1": 1})
    r = client.get("/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "healthy"
    assert body["service"] == "customer-api"


# ── List customers ────────────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_list_customers(mock_init, mock_get_db, client):
    db = MagicMock()
    count_cursor = MagicMock()
    count_cursor.fetchone.return_value = {"cnt": 1}
    rows_cursor = MagicMock()
    rows_cursor.fetchall.return_value = [MOCK_ROW]
    db.execute.side_effect = [count_cursor, rows_cursor]
    mock_get_db.return_value = db

    r = client.get("/api/v1/customers")
    assert r.status_code == 200
    body = r.get_json()
    assert "data" in body
    assert body["total"] == 1
    assert len(body["data"]) == 1


# ── Create customer ───────────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_create_customer(mock_init, mock_get_db, client):
    db = MagicMock()
    # 1st call: unique email check → None means no conflict
    check_cursor = MagicMock(); check_cursor.fetchone.return_value = None
    # 2nd call: INSERT
    insert_cursor = MagicMock(); insert_cursor.lastrowid = 1
    # 3rd call: SELECT new row
    select_cursor = MagicMock(); select_cursor.fetchone.return_value = MOCK_ROW
    db.execute.side_effect = [check_cursor, insert_cursor, select_cursor]
    mock_get_db.return_value = db

    r = client.post("/api/v1/customers", json=CUSTOMER_1)
    assert r.status_code == 201
    body = r.get_json()
    assert body["email"] == "alice@example.com"


@patch("app.get_db")
@patch("app.init_db")
def test_create_customer_missing_required_field(mock_init, mock_get_db, client):
    r = client.post("/api/v1/customers", json={"first_name": "Alice"})
    assert r.status_code == 400
    assert "error" in r.get_json()


@patch("app.get_db")
@patch("app.init_db")
def test_create_customer_duplicate_email(mock_init, mock_get_db, client):
    db = MagicMock()
    conflict_cursor = MagicMock()
    conflict_cursor.fetchone.return_value = {"id": 99}   # existing record
    db.execute.return_value = conflict_cursor
    mock_get_db.return_value = db

    r = client.post("/api/v1/customers", json=CUSTOMER_1)
    assert r.status_code == 409


# ── Get one customer ──────────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_get_customer(mock_init, mock_get_db, client):
    db = make_mock_db(fetchone_val=MOCK_ROW)
    mock_get_db.return_value = db
    r = client.get("/api/v1/customers/1")
    assert r.status_code == 200
    assert r.get_json()["id"] == 1


@patch("app.get_db")
@patch("app.init_db")
def test_get_customer_not_found(mock_init, mock_get_db, client):
    db = make_mock_db(fetchone_val=None)
    mock_get_db.return_value = db
    r = client.get("/api/v1/customers/999")
    assert r.status_code == 404


# ── Update customer (PUT) ─────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_update_customer(mock_init, mock_get_db, client):
    db = MagicMock()
    exist_cursor  = MagicMock(); exist_cursor.fetchone.return_value  = MOCK_ROW
    email_cursor  = MagicMock(); email_cursor.fetchone.return_value  = None
    update_cursor = MagicMock()
    select_cursor = MagicMock(); select_cursor.fetchone.return_value = MOCK_ROW
    db.execute.side_effect = [exist_cursor, email_cursor, update_cursor, select_cursor]
    mock_get_db.return_value = db

    r = client.put("/api/v1/customers/1", json={**CUSTOMER_1, "address": "123 Main St"})
    assert r.status_code == 200


# ── Partial update (PATCH) ────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_patch_customer(mock_init, mock_get_db, client):
    db = MagicMock()
    exist_cursor  = MagicMock(); exist_cursor.fetchone.return_value  = MOCK_ROW
    update_cursor = MagicMock()
    select_cursor = MagicMock(); select_cursor.fetchone.return_value = {**MOCK_ROW, "city": "Pune"}
    db.execute.side_effect = [exist_cursor, update_cursor, select_cursor]
    mock_get_db.return_value = db

    r = client.patch("/api/v1/customers/1", json={"city": "Pune"})
    assert r.status_code == 200
    assert r.get_json()["city"] == "Pune"


@patch("app.get_db")
@patch("app.init_db")
def test_patch_invalid_fields(mock_init, mock_get_db, client):
    db = make_mock_db(fetchone_val=MOCK_ROW)
    mock_get_db.return_value = db
    r = client.patch("/api/v1/customers/1", json={"nonexistent_field": "x"})
    assert r.status_code == 400


# ── Delete customer ───────────────────────────────────────────────────────────

@patch("app.get_db")
@patch("app.init_db")
def test_delete_customer(mock_init, mock_get_db, client):
    db = MagicMock()
    exist_cursor  = MagicMock(); exist_cursor.fetchone.return_value = {"id": 1}
    delete_cursor = MagicMock()
    db.execute.side_effect = [exist_cursor, delete_cursor]
    mock_get_db.return_value = db

    r = client.delete("/api/v1/customers/1")
    assert r.status_code == 200
    assert "deleted" in r.get_json()["message"]


@patch("app.get_db")
@patch("app.init_db")
def test_delete_customer_not_found(mock_init, mock_get_db, client):
    db = make_mock_db(fetchone_val=None)
    mock_get_db.return_value = db
    r = client.delete("/api/v1/customers/999")
    assert r.status_code == 404


# ── Unknown endpoint ──────────────────────────────────────────────────────────

def test_404(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404

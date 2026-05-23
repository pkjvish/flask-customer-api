"""
db.py — MySQL connection management using PyMySQL.

Environment variables consumed:
  DB_HOST     MySQL host        (default: localhost)
  DB_PORT     MySQL port        (default: 3306)
  DB_NAME     Database name     (default: customerdb)
  DB_USER     MySQL user        (default: root)
  DB_PASSWORD MySQL password    (required in production)
"""

import os
import pymysql
import pymysql.cursors
from flask import g

# ── Connection settings from environment ────────────────────────────────────

DB_CONFIG = {
    "host":         os.environ.get("DB_HOST",     "localhost"),
    "port":         int(os.environ.get("DB_PORT", 3306)),
    "database":     os.environ.get("DB_NAME",     "customerdb"),
    "user":         os.environ.get("DB_USER",     "root"),
    "password":     os.environ.get("DB_PASSWORD", ""),
    "cursorclass":  pymysql.cursors.DictCursor,   # rows as dicts
    "autocommit":   False,
    "charset":      "utf8mb4",
    "connect_timeout": 10,
}


# ── Per-request connection (stored in Flask g) ───────────────────────────────

def get_db():
    """Return the request-scoped MySQL connection, creating it if needed."""
    if "db" not in g:
        g.db = pymysql.connect(**DB_CONFIG)
    return g.db


def close_db(error=None):
    """Close the MySQL connection at the end of every request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ── Schema bootstrap ─────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS customers (
    id          INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(255) NOT NULL UNIQUE,
    phone       VARCHAR(50),
    address     VARCHAR(500),
    city        VARCHAR(100),
    country     VARCHAR(100),
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                             ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email   (email),
    INDEX idx_city    (city),
    INDEX idx_country (country)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_db():
    """Create the customers table if it does not already exist."""
    db = get_db()
    with db.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_CONFIG['database']}`")
        cur.execute(f"USE `{DB_CONFIG['database']}`")
        cur.execute(DDL)
    db.commit()


# ── Register teardown on the Flask app ──────────────────────────────────────

def init_app(app):
    app.teardown_appcontext(close_db)

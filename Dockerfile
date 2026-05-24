# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Build Python wheels
#   Compiles C extensions (cryptography, pymysql) so the runtime image
#   does NOT need gcc or build tools, keeping it lean and secure.
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Production runtime (no compiler, no build tools)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: run as non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install pre-built wheels from Stage 1
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* \
    && rm -rf /wheels

# Copy only the application source files
COPY app.py db.py ./

# Port your Flask app listens on
EXPOSE 5000

# Switch to non-root
USER appuser

CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--threads=4", "app:app"]

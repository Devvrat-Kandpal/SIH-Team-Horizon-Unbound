# ==============================================================================
# PROJECT ARJUNA (SIH 26170): MULTI-STAGE DOCKERFILE
# Containerized demonstration / prototype deployment environment.
# (Not a "production aerospace container" — real-hardware and formal ECSS
#  qualification remain out of scope for this prototype; see P2-01 / docs.)
# ==============================================================================

# Stage 1: Build stage for dependency resolution
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Stage 2: Minimal, secure production runtime
FROM python:3.11-slim AS runner

LABEL org.opencontainers.image.title="Project ARJUNA"
LABEL org.opencontainers.image.description="AI-Driven Component Burn-In Telemetry & Screening for ISRO (prototype demo)"
LABEL org.opencontainers.image.version="2.1.0-demo"

WORKDIR /app

# Create non-root system user and group for security compliance
RUN groupadd -r -g 1001 arjuna && \
    useradd -r -u 1001 -g arjuna -d /app -s /sbin/nologin arjuna

# Install curl for container healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/arjuna/.local
ENV PATH=/home/arjuna/.local/bin:$PATH
# FIX: useradd set the arjuna home to /app, so Python resolved user
# site-packages at /app/.local (empty) and imports failed at runtime
# (ModuleNotFoundError: uvicorn). Pin HOME to the directory that actually
# contains the copied site-packages.
ENV HOME=/home/arjuna
# Container must bind 0.0.0.0 for published ports and the built-in healthcheck
# to work (bare `docker run` — docker-compose.yml already sets HOST explicitly).
ENV HOST=0.0.0.0
ENV PORT=8000
# Headless container: main.py skips webbrowser.open for 0.0.0.0 anyway; make it explicit.
ENV NO_BROWSER=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy project files
COPY --chown=arjuna:arjuna . /app

# Ensure proper permissions
RUN chown -R arjuna:arjuna /app

# Switch to non-root security user
USER arjuna

# Container healthcheck querying FastAPI /api/health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

# Start production server
CMD ["python", "main.py"]


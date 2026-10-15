# ==============================================================================
# Multi-Stage Production Dockerfile: Stockezee Options Microstructure Engine
# Vellore Institute of Technology (VIT), Chennai | Harsh Vardhan (22BDA0001)
# ==============================================================================

# STAGE 1: Python Quant & LLVM JIT Engine
FROM python:3.12-slim-bookworm AS quant-engine

WORKDIR /app/engine

# Install system compilation dependencies for LLVM, Arrow & C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY OPTIONS/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir wheel setuptools

# Copy core engine code & pre-compile JIT modules
COPY OPTIONS/ ./
RUN python setup.py bdist_wheel \
    && python -c "import numba, polars; print('LLVM & Polars pre-compiled successfully')"

# STAGE 2: Node.js Express Gateway & Web Client
FROM node:20-alpine AS web-gateway

WORKDIR /app/web
COPY "stock webpage - Copy/package*.json" ./
RUN npm install --omit=dev

COPY "stock webpage - Copy/" ./

# STAGE 3: Final Production Runner Container
FROM python:3.12-slim-bookworm AS production

WORKDIR /app

# Copy wheel and pre-compiled Python binaries from STAGE 1
COPY --from=quant-engine /app/engine/dist/*.whl /app/dist/
RUN pip install --no-cache-dir /app/dist/*.whl

# Copy runner configurations
COPY OPTIONS/runner.py /app/
COPY OPTIONS/config/ /app/config/

# Environment configurations
ENV PYTHONUNBUFFERED=1 \
    TOKEN_EXPIRY_THRESHOLD=3600 \
    APP_ENV=production

EXPOSE 8000 3000

CMD ["python", "runner.py"]

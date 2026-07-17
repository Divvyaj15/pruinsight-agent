# PruInsight — Docker image (Streamlit multi-agent research desk)
# Base: official Python slim image (small Linux + Python 3.11)

FROM python:3.11-slim

# Labels (optional metadata — useful when you list images later)
LABEL project="pruinsight-agent"
LABEL description="Multi-agent equity research (LangGraph + Streamlit)"

# Working directory inside the container
WORKDIR /app

# System packages:
# - curl: healthcheck
# - fonts-dejavu-core: Unicode PDF export (₹, etc.) inside Linux containers
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Streamlit listens on 8501
EXPOSE 8501

# Simple health endpoint used by Docker / Compose
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit bound to 0.0.0.0 so host browser can reach it
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]

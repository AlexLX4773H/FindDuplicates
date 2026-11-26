# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Prevent Python from writing bytecode and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (e.g., libmagic / media tools if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    p7zip-full \
    unzip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and default configuration
COPY src/ ./src/
COPY config.example.yaml ./config.yaml
COPY assets/ ./assets/

# Default scan mount points inside container
VOLUME ["/media", "/reports", "/archive"]

# Expose interactive dashboard port
EXPOSE 8765

# Default command runs Interactive Web UI Server
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["server", "--host", "0.0.0.0", "--port", "8765"]

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies for EasyOCR and other requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    whois \
    && curl -sL nxtrace.org/nt | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install python dependencies from pyproject.toml
RUN pip install --no-cache-dir .

# Create necessary directories if they don't exist
RUN mkdir -p conf_dir data

# Create default config files if they don't exist
# Note: In production, you should mount these as volumes or use environment variables
RUN touch conf_dir/config.yaml conf_dir/settings.toml

# Create a volume for persistent data
VOLUME ["/app/data", "/app/conf_dir"]

# Healthcheck to ensure the application is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD ps aux | grep python | grep main.py || exit 1

# Command to run the application
CMD ["python", "main.py"]

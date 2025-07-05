FROM python:3.11-slim

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
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

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

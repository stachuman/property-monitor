# Property Monitor - Docker Image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=main_service.py \
    FLASK_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r property && useradd -r -g property property

# Create necessary directories
RUN mkdir -p /var/lib/property_monitor/backups \
    /var/log/property_monitor \
    /app/templates \
    /app/admin_templates \
    /app/geocoding_data \
    && chown -R property:property /var/lib/property_monitor /var/log/property_monitor

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure proper permissions
RUN chown -R property:property /app

# Create default config if not exists
RUN cp -n config.json config.json.default || true

# Switch to non-root user
USER property

# Initialize database
RUN python -c "from database import DatabaseManager; DatabaseManager().init_database()"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost/api/health || exit 1

# Expose ports
EXPOSE 80 8080

# Start command
CMD ["python", "main_service.py"]

FROM python:3.12-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    gnupg \
    tor \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=marketplace.settings

# Create app directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p logs staticfiles secure_uploads temp_uploads && \
    chmod 755 logs staticfiles secure_uploads temp_uploads

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
RUN chown app:app /entrypoint.sh

# Create and set proper permissions for staticfiles directory
RUN mkdir -p /app/staticfiles && \
    chmod -R 755 /app/staticfiles && \
    chown -R app:app /app/staticfiles

USER app

# Expose port
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "300", "--worker-class", "sync", "marketplace.wsgi:application"]

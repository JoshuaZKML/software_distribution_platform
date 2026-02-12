# FILE: /Dockerfile (CREATE NEW)
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        libpq-dev \
        gettext \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p /app/static /app/media /app/logs

# Collect static files (will be done in production)
# RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
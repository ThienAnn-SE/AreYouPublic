# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

# Create non-root user
RUN groupadd -r piea && useradd -r -g piea piea

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/ ./src/

# Change ownership to non-root user
RUN chown -R piea:piea /app
USER piea

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "piea.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
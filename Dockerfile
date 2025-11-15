# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY src/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and public files
COPY src/ ./src/
COPY public/ ./public/

# Expose the application port
EXPOSE 8000

# Set environment variable for Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "src/main.py"]

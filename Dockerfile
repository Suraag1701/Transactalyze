# Use official slim Python image
FROM python:3.11-slim

# Install system dependencies including tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Optional: Confirm tesseract is installed (debug)
RUN which tesseract

# Set environment variables
ENV PATH="/usr/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the app
COPY . .

# Expose app port
EXPOSE 10000

# Run Flask app with gunicorn in production
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "main:app"]

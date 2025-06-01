# Use Python base image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Expose port for Render (Render expects web services to listen on 0.0.0.0:$PORT)
EXPOSE 10000

# Set environment variable for Flask
ENV FLASK_ENV=production

# Use Gunicorn for production server and bind to the expected port
CMD ["gunicorn", "-b", "0.0.0.0:10000", "main:app"]

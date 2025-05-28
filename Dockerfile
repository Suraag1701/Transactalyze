# Use a minimal Python image
FROM python:3.10-slim

# Set environment variables to prevent Python buffering issues
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system packages (Tesseract and dependencies)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all app files
COPY . /app

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Start your app
CMD ["python", "main.py"]

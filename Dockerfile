# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for OpenCV, QR code processing, and Flask
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libglib2.0-data \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libx11-dev \
    libzbar0 \
    libjpeg-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy project files into container
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Expose port (update if you're using something else)
EXPOSE 5000

# Run the Flask app (adjust if your app entry is different)
CMD ["python", "app.py"]

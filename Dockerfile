# Use an official Python base image
FROM python:3.10-slim

# Install required system packages
RUN apt-get update && apt-get install -y \
    libzbar0 \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 5000

# Start your Flask app
CMD ["python", "run_app.py"]

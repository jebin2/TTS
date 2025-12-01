FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Copy application files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p uploads temp_dir

# Expose port
EXPOSE 7860

# Run only the Flask app (worker starts automatically on first upload)
CMD ["python", "app.py"]
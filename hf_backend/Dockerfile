FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY . .

# Install dependencies and project
RUN pip install --no-cache-dir .

# Create necessary directories
RUN mkdir -p uploads temp_dir

# Expose port
EXPOSE 7860

# Run the FastAPI app (worker starts automatically on first upload)
CMD ["python", "run.py"]
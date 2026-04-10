FROM python:3.11-slim

# Install system dependencies (ffmpeg required by yt-dlp)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy dependency file first (better caching)
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .
WORKDIR /app/ytaudio

# Expose FastAPI port
EXPOSE 8000

# Run the app
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
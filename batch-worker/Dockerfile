# Use NVIDIA CUDA base image for GPU support
FROM nvidia/cuda:13.0.1-cudnn-runtime-ubuntu24.04

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
  python3.12 \
  python3-pip \
  git \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --break-system-packages

# Copy worker script
COPY worker.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# Run the worker
CMD ["python3", "worker.py"]

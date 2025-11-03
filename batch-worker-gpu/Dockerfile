FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Install Python and common dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  python3 python3-pip python3-venv git ca-certificates && \
  rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3 /usr/bin/python
RUN pip3 install --upgrade pip

# Install PyTorch with CUDA support (CUDA 12.1)
# Note: Ensure compatibility of torch wheel with CUDA version used by chosen base image.
RUN pip3 install --no-cache-dir --index-url https://download.pytorch.org/whl/cu121 \
  torch torchvision torchaudio

# Install faster-whisper
RUN pip3 install --no-cache-dir faster-whisper boto3

# Copy application
WORKDIR /opt/app
COPY worker.py requirements.txt ./

# Set entrypoint to run the worker as a script for Batch jobs
CMD ["python", "worker.py"]

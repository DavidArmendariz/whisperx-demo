FROM python:3.12-slim

# Install faster-whisper to download dependencies
RUN pip install --no-cache-dir faster-whisper==1.2.0

# Set cache directory for the layer
ENV HF_HOME=/opt/python/huggingface
ENV TRANSFORMERS_CACHE=/opt/python/huggingface

# Create cache directory and download the model
RUN mkdir -p /opt/python/huggingface
RUN python -c "from faster_whisper import WhisperModel; \
  WhisperModel('small', device='cpu', compute_type='int8', download_root='/opt/python/huggingface')"

# Create layer zip structure
WORKDIR /opt
CMD ["tar", "czf", "/output/layer.tar.gz", "python/"]

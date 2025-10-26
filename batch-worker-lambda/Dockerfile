FROM python:3.12-slim

# Install AWS Lambda Runtime Interface Client
RUN pip install --no-cache-dir awslambdaric

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Set cache directories BEFORE downloading model
ENV HF_HOME=/opt/huggingface
ENV TRANSFORMERS_CACHE=/opt/huggingface
ENV XDG_CACHE_HOME=/opt

# Create cache directory and download the Whisper model during build
RUN mkdir -p /opt/huggingface
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

# Copiar código
COPY worker.py /var/task/

WORKDIR /var/task

# Entry point for Lambda
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["worker.handler"]
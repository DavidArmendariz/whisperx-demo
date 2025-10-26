FROM python:3.11-slim

# Install AWS Lambda Runtime Interface Client
RUN pip install --no-cache-dir awslambdaric

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the Whisper model during build
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

# Copiar código
COPY worker.py /var/task/

WORKDIR /var/task

# Configurar cache de Hugging Face para usar /tmp
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/huggingface
ENV XDG_CACHE_HOME=/tmp

# Entry point for Lambda
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["worker.handler"]
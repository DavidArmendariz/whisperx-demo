FROM ubuntu:22.04

# Instalar Python y dependencias
RUN apt-get update && apt-get install -y \
  python3.11 \
  python3-pip \
  ffmpeg \
  && rm -rf /var/lib/apt/lists/*

# Instalar AWS Lambda Runtime Interface Client
RUN pip install awslambdaric

# Copiar requirements y instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Descargar el modelo de Whisper durante el build
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

# Copiar código
COPY worker.py /var/task/

WORKDIR /var/task

# Configurar cache de Hugging Face para usar /tmp
ENV HF_HOME=/tmp/huggingface
ENV TRANSFORMERS_CACHE=/tmp/huggingface
ENV XDG_CACHE_HOME=/tmp

# Entry point para Lambda
ENTRYPOINT ["python3", "-m", "awslambdaric"]
CMD ["worker.handler"]
FROM python:3.12-slim

# Install AWS Lambda Runtime Interface Client
RUN pip install --no-cache-dir awslambdaric

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY worker.py /var/task/

WORKDIR /var/task

# Entry point for Lambda
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["worker.handler"]
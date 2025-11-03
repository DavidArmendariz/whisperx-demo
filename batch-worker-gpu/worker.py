import logging
import os
from pathlib import Path

import boto3
from faster_whisper import WhisperModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("batch-worker-gpu")

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
MODEL_PATH = os.getenv("MODEL_PATH", "/mnt/efs/models")
MODEL_SIZE = os.getenv("MODEL_SIZE", "small")  # default to small for higher accuracy
DEVICE = os.getenv("DEVICE", "cuda")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "float16")

s3 = boto3.client("s3", region_name=AWS_REGION)

_model = None


def get_model():
    global _model
    if _model is None:
        logger.info(f"Loading model {MODEL_SIZE} on device {DEVICE}")
        model_dir = Path(MODEL_PATH) / MODEL_SIZE
        model_dir.mkdir(parents=True, exist_ok=True)
        _model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            download_root=MODEL_PATH,
        )
    else:
        logger.info("Using cached model")
    return _model


def download_audio(bucket, key, local_path):
    logger.info(f"Downloading s3://{bucket}/{key} to {local_path}")
    s3.download_file(bucket, key, local_path)
    return local_path


def upload_output(bucket, key, data):
    logger.info(f"Uploading result to s3://{bucket}/{key}")
    s3.put_object(Bucket=bucket, Key=key, Body=data)


def transcribe(audio_local_path, language="es"):
    model = get_model()
    segments, info = model.transcribe(
        audio_local_path,
        language=language,
        beam_size=1,
        best_of=1,
        word_timestamps=True,
    )
    full_text = " ".join([seg.text for seg in segments])
    return {
        "full_text": full_text,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text} for s in segments
        ],
        "language": info.language,
    }


def main():
    # Minimal batch job entrypoint. Expect environment vars: S3_INPUT_KEY, S3_OUTPUT_KEY, JOB_ID
    bucket = os.getenv("S3_BUCKET_NAME")
    s3_input_key = os.getenv("S3_INPUT_KEY")
    s3_output_key = os.getenv("S3_OUTPUT_KEY")
    local_audio = "/tmp/input_audio"
    if not bucket or not s3_input_key or not s3_output_key:
        logger.error("S3_BUCKET_NAME, S3_INPUT_KEY and S3_OUTPUT_KEY env vars required")
        return
    download_audio(bucket, s3_input_key, local_audio)
    result = transcribe(local_audio, language=os.getenv("TARGET_LANGUAGE", "es"))
    upload_output(bucket, s3_output_key, str(result).encode("utf-8"))
    logger.info("Transcription job completed")


if __name__ == "__main__":
    main()

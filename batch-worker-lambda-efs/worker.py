import json
import logging
import os
import sys
from pathlib import Path

import boto3
from faster_whisper import WhisperModel

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Model configuration - use EFS mount path
MODEL_PATH = os.getenv("MODEL_PATH", "/mnt/efs/models")
MODEL_SIZE = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"

# Initialize S3 client
s3_client = boto3.client("s3", region_name=AWS_REGION)

# Global model cache
_model_cache = None


def get_model():
    """Get or load Whisper model from EFS (cached for warm starts)"""
    global _model_cache
    if _model_cache is None:
        logger.info(f"Loading Whisper model ({MODEL_SIZE}) from EFS: {MODEL_PATH}")

        # Check if model exists on EFS
        model_dir = Path(MODEL_PATH) / MODEL_SIZE
        if not model_dir.exists():
            logger.warning(f"Model not found at {model_dir}")
            logger.info("Downloading model to EFS (first time only)...")
            model_dir.mkdir(parents=True, exist_ok=True)

        try:
            _model_cache = WhisperModel(
                MODEL_SIZE,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
                cpu_threads=4,
                download_root=MODEL_PATH,  # Download to EFS if not exists
            )
            logger.info("Model loaded and cached successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise
    else:
        logger.info("Using cached model (warm start)")
    return _model_cache


def download_audio_from_s3(bucket: str, key: str, local_path: str) -> str:
    """Download audio file from S3"""
    logger.info(f"Downloading audio from S3: s3://{bucket}/{key}")
    try:
        s3_client.download_file(bucket, key, local_path)
        logger.info(f"Audio downloaded successfully to {local_path}")
        return local_path
    except Exception as e:
        logger.error(f"Failed to download audio from S3: {str(e)}")
        raise


def upload_transcription_to_s3(bucket: str, key: str, transcription_data: dict):
    """Upload transcription results to S3"""
    logger.info(f"Uploading transcription to S3: s3://{bucket}/{key}")
    try:
        job_id = transcription_data.get("job_id", "unknown")
        language = transcription_data.get("language", "unknown")

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(transcription_data, indent=2, ensure_ascii=False),
            ContentType="application/json",
            Metadata={"job-id": str(job_id), "language": str(language)},
        )
        logger.info("Transcription uploaded successfully")
    except Exception as e:
        logger.error(f"Failed to upload transcription to S3: {str(e)}")
        raise


def transcribe_audio(audio_path: str, language: str = "es") -> dict:
    """Transcribe audio using faster-whisper from EFS model"""
    logger.info("Starting transcription with faster-whisper")
    logger.info(f"Device: {DEVICE}, Language: {language}, Compute Type: {COMPUTE_TYPE}")

    try:
        model = get_model()

        logger.info("Transcribing audio...")
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        logger.info(f"Transcription complete. Detected language: {info.language}")
        logger.info(f"Language probability: {info.language_probability:.2f}")

        formatted_segments = []
        for segment in segments:
            formatted_segment = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }

            if segment.words:
                formatted_segment["words"] = [
                    {
                        "start": word.start,
                        "end": word.end,
                        "word": word.word,
                        "probability": word.probability,
                    }
                    for word in segment.words
                ]

            formatted_segments.append(formatted_segment)

        logger.info("Transcription pipeline complete")

        return {
            "segments": formatted_segments,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        raise


def format_transcription_output(result: dict, metadata: dict) -> dict:
    """Format transcription results for output"""
    full_text = " ".join(
        [segment.get("text", "") for segment in result.get("segments", [])]
    )

    formatted_segments = []
    for segment in result.get("segments", []):
        formatted_segment = {
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": segment.get("text"),
        }

        if "words" in segment:
            formatted_segment["words"] = segment["words"]

        formatted_segments.append(formatted_segment)

    return {
        "job_id": metadata["job_id"],
        "language": metadata["language"],
        "device_used": metadata["device"],
        "full_text": full_text.strip(),
        "segments": formatted_segments,
        "metadata": {
            "total_segments": len(formatted_segments),
            "s3_input_key": metadata["s3_input_key"],
            "s3_output_key": metadata["s3_output_key"],
        },
    }


def main(
    s3_input_key: str,
    s3_output_key: str,
    target_language: str = "es",
    job_id: str = "unknown",
):
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("Starting WhisperX Transcription Job")
    logger.info(f"Job ID: {job_id}")
    logger.info(f"S3 Bucket: {S3_BUCKET_NAME}")
    logger.info(f"S3 Input Key: {s3_input_key}")
    logger.info(f"S3 Output Key: {s3_output_key}")
    logger.info(f"Target Language: {target_language}")
    logger.info(f"Device: {DEVICE}")
    logger.info(f"Model Path (EFS): {MODEL_PATH}")
    logger.info("=" * 80)

    if not all([S3_BUCKET_NAME, s3_input_key, s3_output_key]):
        logger.error("Missing required parameters")
        sys.exit(1)

    s3_bucket_name = str(S3_BUCKET_NAME)

    # Use /tmp for temporary audio file
    temp_dir = Path("/tmp/whisperx")
    temp_dir.mkdir(exist_ok=True)

    input_filename = Path(s3_input_key).name
    local_audio_path = str(temp_dir / input_filename)

    try:
        download_audio_from_s3(s3_bucket_name, s3_input_key, local_audio_path)
        transcription_result = transcribe_audio(local_audio_path, target_language)

        metadata = {
            "job_id": job_id,
            "language": target_language,
            "device": DEVICE,
            "s3_input_key": s3_input_key,
            "s3_output_key": s3_output_key,
        }

        formatted_output = format_transcription_output(transcription_result, metadata)
        upload_transcription_to_s3(s3_bucket_name, s3_output_key, formatted_output)

        logger.info("=" * 80)
        logger.info("Transcription job completed successfully")
        logger.info(f"Results uploaded to: s3://{s3_bucket_name}/{s3_output_key}")
        logger.info("=" * 80)

        try:
            os.remove(local_audio_path)
            logger.info(f"Cleaned up local file: {local_audio_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up local file: {str(e)}")

        sys.exit(0)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"Transcription job failed: {str(e)}")
        logger.error("=" * 80)
        sys.exit(1)


def handler(event, context):
    """Lambda handler - wrapper for main()"""
    try:
        if not event:
            return {"statusCode": 400, "body": "No event data provided"}

        s3_input_key = event.get("s3_input_key")
        s3_output_key = event.get("s3_output_key")
        target_language = event.get("target_language", "es")
        job_id = event.get("job_id", "unknown")

        if not s3_input_key or not s3_output_key:
            return {
                "statusCode": 400,
                "body": "Missing required parameters: s3_input_key, s3_output_key",
            }

        logger.info("Lambda invocation - parameters from event:")
        logger.info(f"s3_input_key: {s3_input_key}")
        logger.info(f"s3_output_key: {s3_output_key}")
        logger.info(f"target_language: {target_language}")
        logger.info(f"job_id: {job_id}")

        # Pre-load model to check EFS mount
        logger.info("Pre-loading model from EFS...")
        get_model()
        logger.info("Model pre-loaded successfully from EFS")

        main(s3_input_key, s3_output_key, target_language, job_id)
        return {"statusCode": 200, "body": "Success"}
    except SystemExit as e:
        if e.code == 0:
            return {"statusCode": 200, "body": "Success"}
        else:
            return {"statusCode": 500, "body": f"Failed with exit code {e.code}"}
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {"statusCode": 500, "body": str(e)}


if __name__ == "__main__":
    # For local testing only
    test_s3_input_key = "input/test/sample.mp3"
    test_s3_output_key = "output/test/transcription.json"
    test_target_language = "es"
    test_job_id = "test-job"

    main(test_s3_input_key, test_s3_output_key, test_target_language, test_job_id)

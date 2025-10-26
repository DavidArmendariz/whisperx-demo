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
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_INPUT_KEY = os.getenv("S3_INPUT_KEY")
S3_OUTPUT_KEY = os.getenv("S3_OUTPUT_KEY")
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "es")
JOB_ID = os.getenv("JOB_ID", "unknown")

# Faster-Whisper configuration
MODEL_SIZE = "small"  # small, medium, large-v2, large-v3
DEVICE = "cpu"  # Use CPU since we removed GPU support
COMPUTE_TYPE = "int8"  # int8 for CPU, float16 for GPU

# Initialize S3 client
s3_client = boto3.client("s3", region_name=AWS_REGION)


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
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(transcription_data, indent=2, ensure_ascii=False),
            ContentType="application/json",
            Metadata={"job-id": JOB_ID, "language": TARGET_LANGUAGE},
        )
        logger.info("Transcription uploaded successfully")
    except Exception as e:
        logger.error(f"Failed to upload transcription to S3: {str(e)}")
        raise


def transcribe_audio(audio_path: str, language: str = "es") -> dict:
    """
    Transcribe audio using faster-whisper

    Args:
        audio_path: Path to the audio file
        language: Target language code (default: es for Spanish)

    Returns:
        Dictionary containing transcription results
    """
    logger.info("Starting transcription with faster-whisper")
    logger.info(f"Device: {DEVICE}, Language: {language}, Compute Type: {COMPUTE_TYPE}")

    try:
        # Load model
        logger.info(f"Loading Whisper model ({MODEL_SIZE})...")
        model = WhisperModel(
            MODEL_SIZE,
            device=DEVICE,
            compute_type=COMPUTE_TYPE,
            cpu_threads=1,  # Use all 8 CPU cores
        )

        # Transcribe
        logger.info("Transcribing audio...")
        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,  # Voice activity detection
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        logger.info(f"Transcription complete. Detected language: {info.language}")
        logger.info(f"Language probability: {info.language_probability:.2f}")

        # Convert generator to list and format segments
        formatted_segments = []
        for segment in segments:
            formatted_segment = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
            }

            # Add word-level timestamps if available
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

    # Extract full text
    full_text = " ".join(
        [segment.get("text", "") for segment in result.get("segments", [])]
    )

    # Format segments
    formatted_segments = []
    for segment in result.get("segments", []):
        formatted_segment = {
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": segment.get("text"),
        }

        # Add word-level details if available
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


def main():
    """Main execution function"""
    logger.info("=" * 80)
    logger.info("Starting WhisperX Transcription Job")
    logger.info(f"Job ID: {JOB_ID}")
    logger.info(f"S3 Bucket: {S3_BUCKET_NAME}")
    logger.info(f"S3 Input Key: {S3_INPUT_KEY}")
    logger.info(f"S3 Output Key: {S3_OUTPUT_KEY}")
    logger.info(f"Target Language: {TARGET_LANGUAGE}")
    logger.info(f"Device: {DEVICE}")
    logger.info("=" * 80)

    # Validate environment variables
    if not all([S3_BUCKET_NAME, S3_INPUT_KEY, S3_OUTPUT_KEY]):
        logger.error("Missing required environment variables")
        logger.error(f"S3_BUCKET_NAME: {S3_BUCKET_NAME}")
        logger.error(f"S3_INPUT_KEY: {S3_INPUT_KEY}")
        logger.error(f"S3_OUTPUT_KEY: {S3_OUTPUT_KEY}")
        sys.exit(1)

    # Create temp directory for audio file
    temp_dir = Path("/tmp/whisperx")
    temp_dir.mkdir(exist_ok=True)

    # Extract filename from S3 key
    input_filename = Path(S3_INPUT_KEY).name
    local_audio_path = str(temp_dir / input_filename)

    try:
        # Download audio from S3
        download_audio_from_s3(S3_BUCKET_NAME, S3_INPUT_KEY, local_audio_path)

        # Transcribe audio
        transcription_result = transcribe_audio(local_audio_path, TARGET_LANGUAGE)

        # Format output
        metadata = {
            "job_id": JOB_ID,
            "language": TARGET_LANGUAGE,
            "device": DEVICE,
            "s3_input_key": S3_INPUT_KEY,
            "s3_output_key": S3_OUTPUT_KEY,
        }

        formatted_output = format_transcription_output(transcription_result, metadata)

        # Upload results to S3
        upload_transcription_to_s3(S3_BUCKET_NAME, S3_OUTPUT_KEY, formatted_output)

        logger.info("=" * 80)
        logger.info("Transcription job completed successfully")
        logger.info(f"Results uploaded to: s3://{S3_BUCKET_NAME}/{S3_OUTPUT_KEY}")
        logger.info("=" * 80)

        # Clean up local file
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


if __name__ == "__main__":
    main()

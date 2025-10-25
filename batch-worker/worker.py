import gc
import json
import logging
import os
import sys
from pathlib import Path

import boto3
import torch
import whisperx

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

# WhisperX configuration
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 32
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

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
    Transcribe audio using WhisperX

    Args:
        audio_path: Path to the audio file
        language: Target language code (default: es for Spanish)

    Returns:
        Dictionary containing transcription results
    """
    logger.info("Starting transcription with WhisperX")
    logger.info(f"Device: {DEVICE}, Language: {language}, Compute Type: {COMPUTE_TYPE}")

    try:
        # Load model
        logger.info("Loading Whisper model (small)...")
        model = whisperx.load_model(
            "small", device=DEVICE, compute_type=COMPUTE_TYPE, language=language
        )

        # Load audio
        logger.info(f"Loading audio file: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # Transcribe
        logger.info("Transcribing audio...")
        result = model.transcribe(audio, batch_size=BATCH_SIZE, language=language)

        logger.info(
            f"Initial transcription complete. Detected language: {result.get('language', 'unknown')}"
        )

        # Clean up model from memory
        del model
        gc.collect()
        torch.cuda.empty_cache() if DEVICE == "cuda" else None

        # Align whisper output
        logger.info("Aligning transcription...")
        model_a, metadata = whisperx.load_align_model(
            language_code=language, device=DEVICE
        )
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            DEVICE,
            return_char_alignments=False,
        )

        logger.info("Alignment complete")

        # Clean up alignment model
        del model_a
        gc.collect()
        torch.cuda.empty_cache() if DEVICE == "cuda" else None

        logger.info("Transcription pipeline complete")

        return result

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

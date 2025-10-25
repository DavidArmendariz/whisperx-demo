import logging
import os
import uuid
from datetime import datetime
from typing import Optional

import boto3
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="WhisperX Audio Transcription API",
    description="API for uploading audio files and triggering transcription jobs",
    version="1.0.0",
)


# Middleware to filter health check logs
@app.middleware("http")
async def filter_health_check_logs(request: Request, call_next):
    """Don't log health check requests"""
    response = await call_next(request)

    # Skip logging for health check endpoint
    if request.url.path != "/health":
        logger.info(f"{request.method} {request.url.path} - {response.status_code}")

    return response


# AWS configuration
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
BATCH_JOB_QUEUE = os.getenv("BATCH_JOB_QUEUE")
BATCH_JOB_DEFINITION = os.getenv("BATCH_JOB_DEFINITION")

# Initialize AWS clients
s3_client = boto3.client("s3", region_name=AWS_REGION)
batch_client = boto3.client("batch", region_name=AWS_REGION)


@app.get("/health")
async def health_check():
    """Health check endpoint for ALB"""
    return {"status": "healthy", "service": "whisperx-api"}


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...), language: Optional[str] = "es"
):
    """
    Upload an audio file and trigger a transcription job

    Args:
        file: Audio file to transcribe (supported formats: mp3, wav, m4a, flac, ogg)
        language: Target language for transcription (default: es - Spanish)

    Returns:
        JSON response with job details
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Validate file extension
        allowed_extensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".avi"]
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}",
            )

        # Generate unique job ID and S3 key
        job_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        s3_input_key = f"input/{timestamp}-{job_id}/{file.filename}"
        s3_output_key = f"output/{timestamp}-{job_id}/transcription.json"

        logger.info(f"Uploading file to S3: {s3_input_key}")

        # Upload file to S3
        try:
            s3_client.upload_fileobj(
                file.file,
                S3_BUCKET_NAME,
                s3_input_key,
                ExtraArgs={
                    "ContentType": file.content_type or "audio/mpeg",
                    "Metadata": {
                        "original-filename": file.filename,
                        "job-id": job_id,
                        "language": language,
                    },
                },
            )
        except Exception as e:
            logger.error(f"S3 upload failed: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to upload file: {str(e)}"
            )

        logger.info("File uploaded successfully. Submitting Batch job...")

        # Submit AWS Batch job
        try:
            batch_response = batch_client.submit_job(
                jobName=f"whisper-transcription-{job_id[:8]}",
                jobQueue=BATCH_JOB_QUEUE,
                jobDefinition=BATCH_JOB_DEFINITION,
                containerOverrides={
                    "environment": [
                        {"name": "S3_INPUT_KEY", "value": s3_input_key},
                        {"name": "S3_OUTPUT_KEY", "value": s3_output_key},
                        {"name": "TARGET_LANGUAGE", "value": language},
                        {"name": "JOB_ID", "value": job_id},
                    ]
                },
            )

            batch_job_id = batch_response["jobId"]
            logger.info(f"Batch job submitted: {batch_job_id}")

        except Exception as e:
            logger.error(f"Batch job submission failed: {str(e)}")
            # Clean up uploaded file
            try:
                s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_input_key)
            except:
                pass
            raise HTTPException(
                status_code=500, detail=f"Failed to submit job: {str(e)}"
            )

        return JSONResponse(
            status_code=202,
            content={
                "message": "Transcription job submitted successfully",
                "job_id": job_id,
                "batch_job_id": batch_job_id,
                "s3_input_key": s3_input_key,
                "s3_output_key": s3_output_key,
                "language": language,
                "status": "SUBMITTED",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """
    Get the status of a transcription job

    Args:
        job_id: The job ID returned from the /transcribe endpoint

    Returns:
        JSON response with job status
    """
    try:
        # Query Batch jobs with the job_id in the name
        response = batch_client.describe_jobs(jobs=[job_id])

        if not response.get("jobs"):
            raise HTTPException(status_code=404, detail="Job not found")

        job = response["jobs"][0]

        return {
            "job_id": job_id,
            "batch_job_id": job["jobId"],
            "status": job["status"],
            "created_at": job.get("createdAt"),
            "started_at": job.get("startedAt"),
            "stopped_at": job.get("stoppedAt"),
            "status_reason": job.get("statusReason"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get job status: {str(e)}"
        )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "WhisperX Audio Transcription API",
        "version": "1.0.0",
        "endpoints": {
            "POST /transcribe": "Upload audio file and start transcription",
            "GET /job/{job_id}": "Get transcription job status",
            "GET /health": "Health check endpoint",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

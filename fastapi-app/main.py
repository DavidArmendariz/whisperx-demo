import json
import logging
import os
import uuid
from datetime import datetime
from typing import Literal, Optional

import boto3
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models
class PreSignedUrlRequest(BaseModel):
    filename: str
    content_type: Optional[str] = None
    language: Optional[str] = "es"
    execution_method: Literal["batch", "lambda"] = "batch"


class TranscribeFromS3Request(BaseModel):
    s3_key: str
    language: Optional[str] = "es"
    execution_method: Literal["batch", "lambda"] = "batch"


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
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
BATCH_JOB_QUEUE = os.getenv("BATCH_JOB_QUEUE")
BATCH_JOB_DEFINITION = os.getenv("BATCH_JOB_DEFINITION")
LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME")

# Initialize AWS clients
s3_client = boto3.client("s3", region_name=AWS_REGION)
batch_client = boto3.client("batch", region_name=AWS_REGION)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)


@app.get("/health")
async def health_check():
    """Health check endpoint for ALB"""
    return {"status": "healthy", "service": "whisperx-api"}


@app.post("/upload-url")
async def generate_upload_url(request: PreSignedUrlRequest):
    """
    Generate a pre-signed URL for direct file upload to S3

    This allows clients to upload files directly to S3, bypassing the API server
    and significantly improving upload performance for large files.

    Args:
        request: Contains filename, content_type, language, and execution_method

    Returns:
        Pre-signed URL, job details, and instructions for subsequent transcription
    """
    try:
        # Validate file extension
        allowed_extensions = [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".avi"]
        file_extension = os.path.splitext(request.filename)[1].lower()
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}",
            )

        # Generate unique job ID and S3 key
        job_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        s3_input_key = f"input/{timestamp}-{job_id}/{request.filename}"
        s3_output_key = f"output/{timestamp}-{job_id}/transcription.json"

        # Set content type
        content_type = request.content_type or "audio/mpeg"

        logger.info(f"Generating pre-signed URL for: {s3_input_key}")

        # Generate pre-signed URL for upload (valid for 1 hour)
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": S3_BUCKET_NAME,
                "Key": s3_input_key,
                "ContentType": content_type,
                "Metadata": {
                    "original-filename": request.filename,
                    "job-id": job_id,
                    "language": request.language,
                },
            },
            ExpiresIn=3600,  # 1 hour
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Pre-signed URL generated successfully",
                "job_id": job_id,
                "upload_url": presigned_url,
                "s3_input_key": s3_input_key,
                "s3_output_key": s3_output_key,
                "language": request.language,
                "execution_method": request.execution_method,
                "upload_instructions": {
                    "method": "PUT",
                    "content_type": content_type,
                    "expires_in_seconds": 3600,
                    "next_step": f"After upload, call POST /transcribe-from-s3 with s3_key: {s3_input_key}",
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating pre-signed URL: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to generate upload URL: {str(e)}"
        )


@app.post("/transcribe-from-s3")
async def transcribe_from_s3(request: TranscribeFromS3Request):
    """
    Trigger transcription for a file already uploaded to S3

    Use this endpoint after uploading a file using the pre-signed URL
    from the /upload-url endpoint.

    Args:
        request: Contains s3_key, language, and execution_method

    Returns:
        JSON response with job details
    """
    try:
        # Extract job_id from s3_key pattern
        # Expected pattern: input/{timestamp}-{job_id}/{filename}
        path_parts = request.s3_key.split("/")
        if len(path_parts) < 3 or not path_parts[0] == "input":
            raise HTTPException(
                status_code=400,
                detail="Invalid S3 key format. Expected: input/{timestamp}-{job_id}/{filename}",
            )

        # Extract job_id from the timestamp-job_id folder name
        folder_name = path_parts[1]
        if "-" not in folder_name:
            raise HTTPException(
                status_code=400, detail="Invalid S3 key format. Cannot extract job ID."
            )

        # Get job_id (everything after the first dash in folder name)
        job_id = (
            folder_name.split("-", 1)[1] if "-" in folder_name else str(uuid.uuid4())
        )

        # Generate output key
        timestamp = (
            folder_name.split("-")[0]
            if "-" in folder_name
            else datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        )
        s3_output_key = f"output/{timestamp}-{job_id}/transcription.json"

        # Check if file exists in S3
        try:
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=request.s3_key)
        except Exception:
            logger.error(f"File not found in S3: {request.s3_key}")
            raise HTTPException(
                status_code=404, detail=f"File not found in S3: {request.s3_key}"
            )

        logger.info(f"Starting transcription for S3 object: {request.s3_key}")

        # Submit job based on execution method
        if request.execution_method == "batch":
            # Submit AWS Batch job
            try:
                batch_response = batch_client.submit_job(
                    jobName=f"whisper-transcription-{job_id[:8]}",
                    jobQueue=BATCH_JOB_QUEUE,
                    jobDefinition=BATCH_JOB_DEFINITION,
                    containerOverrides={
                        "environment": [
                            {"name": "S3_INPUT_KEY", "value": request.s3_key},
                            {"name": "S3_OUTPUT_KEY", "value": s3_output_key},
                            {"name": "TARGET_LANGUAGE", "value": request.language},
                            {"name": "JOB_ID", "value": job_id},
                        ]
                    },
                )

                execution_id = batch_response["jobId"]
                logger.info(f"Batch job submitted: {execution_id}")

            except Exception as e:
                logger.error(f"Batch job submission failed: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to submit batch job: {str(e)}"
                )

        else:  # execution_method == "lambda"
            # Invoke Lambda function
            try:
                lambda_payload = {
                    "s3_input_key": request.s3_key,
                    "s3_output_key": s3_output_key,
                    "target_language": request.language,
                    "job_id": job_id,
                }

                lambda_client.invoke(
                    FunctionName=LAMBDA_FUNCTION_NAME,
                    InvocationType="Event",  # Asynchronous invocation
                    Payload=json.dumps(lambda_payload),
                )

                execution_id = f"lambda-{job_id}"
                logger.info(f"Lambda function invoked: {execution_id}")

            except Exception as e:
                logger.error(f"Lambda invocation failed: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to invoke lambda: {str(e)}"
                )

        return JSONResponse(
            status_code=202,
            content={
                "message": "Transcription job submitted successfully",
                "job_id": job_id,
                "execution_method": request.execution_method,
                "execution_id": execution_id,
                "s3_input_key": request.s3_key,
                "s3_output_key": s3_output_key,
                "language": request.language,
                "status": "SUBMITTED",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = "es",
    execution_method: Literal["batch", "lambda"] = "batch",
):
    """
    Upload an audio file and trigger a transcription job (Legacy method)

    ⚠️  PERFORMANCE NOTE: For faster uploads, especially with large files,
    use the new two-step process:
    1. POST /upload-url to get a pre-signed URL
    2. Upload directly to S3 using the pre-signed URL
    3. POST /transcribe-from-s3 to start transcription

    This legacy endpoint uploads through the API server which can be slower.

    Args:
        file: Audio file to transcribe (supported formats: mp3, wav, m4a, flac, ogg)
        language: Target language for transcription (default: es - Spanish)
        execution_method: Choose 'batch' for AWS Batch or 'lambda' for Lambda execution (default: batch)

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

        logger.info("File uploaded successfully. Submitting job...")

        # Submit job based on execution method
        if execution_method == "batch":
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

                execution_id = batch_response["jobId"]
                logger.info(f"Batch job submitted: {execution_id}")

            except Exception as e:
                logger.error(f"Batch job submission failed: {str(e)}")
                # Clean up uploaded file
                try:
                    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_input_key)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=500, detail=f"Failed to submit batch job: {str(e)}"
                )

        else:  # execution_method == "lambda"
            # Invoke Lambda function
            try:
                lambda_payload = {
                    "s3_input_key": s3_input_key,
                    "s3_output_key": s3_output_key,
                    "target_language": language,
                    "job_id": job_id,
                }

                lambda_client.invoke(
                    FunctionName=LAMBDA_FUNCTION_NAME,
                    InvocationType="Event",  # Asynchronous invocation
                    Payload=json.dumps(lambda_payload),
                )

                execution_id = f"lambda-{job_id}"
                logger.info(f"Lambda function invoked: {execution_id}")

            except Exception as e:
                logger.error(f"Lambda invocation failed: {str(e)}")
                # Clean up uploaded file
                try:
                    s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_input_key)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=500, detail=f"Failed to invoke lambda: {str(e)}"
                )

        return JSONResponse(
            status_code=202,
            content={
                "message": "Transcription job submitted successfully",
                "job_id": job_id,
                "execution_method": execution_method,
                "execution_id": execution_id,
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
        # First try to find it as a Batch job
        try:
            response = batch_client.describe_jobs(jobs=[job_id])
            if response.get("jobs"):
                job = response["jobs"][0]
                return {
                    "job_id": job_id,
                    "execution_method": "batch",
                    "batch_job_id": job["jobId"],
                    "status": job["status"],
                    "created_at": job.get("createdAt"),
                    "started_at": job.get("startedAt"),
                    "stopped_at": job.get("stoppedAt"),
                    "status_reason": job.get("statusReason"),
                }
        except Exception:
            # If not found in Batch, might be a Lambda execution
            pass

        # For Lambda jobs, we can't easily track status without additional infrastructure
        # For now, return a generic response for Lambda jobs
        if job_id.startswith("lambda-"):
            return {
                "job_id": job_id,
                "execution_method": "lambda",
                "status": "UNKNOWN",
                "message": "Lambda job status tracking requires CloudWatch logs inspection",
            }

        # If job_id doesn't match any pattern, it's not found
        raise HTTPException(status_code=404, detail="Job not found")

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
            "POST /upload-url": "🚀 FAST: Generate pre-signed URL for direct S3 upload (recommended for large files)",
            "POST /transcribe-from-s3": "🚀 FAST: Start transcription for file already in S3",
            "POST /transcribe": "🐌 LEGACY: Upload audio file through API server and start transcription",
            "GET /job/{job_id}": "Get transcription job status",
            "GET /health": "Health check endpoint",
        },
        "recommended_workflow": {
            "step_1": "POST /upload-url with filename and options",
            "step_2": "Upload file directly to S3 using the returned pre-signed URL (PUT request)",
            "step_3": "POST /transcribe-from-s3 with the S3 key to start transcription",
            "benefits": "Faster uploads, reduced server load, better scalability",
        },
        "execution_methods": {
            "batch": "AWS Batch for long-running, cost-effective processing",
            "lambda": "AWS Lambda for fast startup, shorter processing times",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

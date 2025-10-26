# Lambda Layer - Faster-Whisper Model

This directory contains the Lambda layer that provides the pre-downloaded faster-whisper model for faster Lambda initialization.

## 🍎 Building on macOS for Linux Lambda

The layer **must** be built for the `linux/amd64` platform since AWS Lambda runs on Linux. The build script handles this automatically.

### Prerequisites

1. **Docker Desktop** installed and running
2. **Docker buildx** enabled (included by default in recent Docker Desktop versions)
3. If you have an M1/M2/M3 Mac (ARM), Docker will automatically use emulation

### Building the Layer

```bash
cd lambda-layer
./build_layer.sh
```

This will:

1. Build a Docker image for `linux/amd64` platform
2. Download the faster-whisper model inside the container
3. Extract and package as `output/whisper-model-layer.zip`

### Output

The layer will be created at:

```
lambda-layer/output/whisper-model-layer.zip
```

This file is referenced in `terraform/lambda.tf` and will be deployed as a Lambda layer.

## 📦 What's in the Layer?

```
python/
└── huggingface/
    └── faster-whisper/
        └── small/
            ├── model.bin
            ├── config.json
            └── ... (other model files)
```

When attached to a Lambda function, this content is mounted at `/opt/`, making the model available at `/opt/huggingface/`.

## 🚀 Deployment

After building the layer:

```bash
cd ../terraform
terraform apply
```

Terraform will:

1. Upload the layer zip to AWS Lambda
2. Create a new layer version
3. Attach the layer to your Lambda function

## 🔄 Updating the Layer

To update the model or change versions:

1. Modify `Dockerfile` (change model size, version, etc.)
2. Rebuild: `./build_layer.sh`
3. Redeploy: `cd ../terraform && terraform apply`

## 💡 Benefits

- **Faster deployments**: Update Lambda code without re-downloading model
- **Smaller Docker images**: Model separated from application (~500MB vs ~2-3GB)
- **Faster cold starts**: Model pre-cached in `/opt` (read-only filesystem)
- **Reusable**: Same layer for multiple Lambda functions
- **Version control**: Pin specific model versions via layer versions

## ⚠️ Important Notes

- **Layer size limit**: Lambda layers have a 250MB **unzipped** limit
- The faster-whisper small model fits within this limit (~200MB unzipped)
- If using larger models (medium, large), you may hit the limit
- Alternative for large models: Download from S3 to `/tmp` on cold start

## 🐛 Troubleshooting

### "no matching manifest for linux/arm64"

Your Docker is trying to build for ARM. Make sure the build script uses `--platform linux/amd64`.

### Layer too large

If the model is too large for Lambda layers:

- Use a smaller model (`tiny` or `small`)
- Or switch to S3-based model loading

### Model not found in Lambda

- Verify the layer is attached in `terraform/lambda.tf`
- Check environment variable `HF_HOME=/opt/huggingface`
- Review Lambda logs in CloudWatch

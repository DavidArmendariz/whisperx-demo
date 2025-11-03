# Batch Worker - GPU

This folder contains the GPU-enabled batch worker image and code for running faster-whisper on AWS Batch using GPU instances (T4/A10G).

Highlights:

- Uses CUDA-enabled base image and PyTorch with CUDA support.
- Designed to run on EC2 instances with GPUs (e.g., g4dn.xlarge, g5.xlarge).

Quick steps:

1. Build & push image

```bash
./deploy-batch-gpu.sh
```

2. Create/Update Batch job definition

- Use `terraform/batch-gpu.tf` to create a GPU compute environment and a job definition. Make sure the job definition `image` field points to the ECR image created above.

3. Submit a job

```bash
aws batch submit-job --job-name whisper-gpu-job \
  --job-queue your-gpu-queue-name \
  --job-definition your-gpu-jobdef \
  --container-overrides 'environment=[{name=S3_INPUT_KEY,value="input/path"},{name=S3_OUTPUT_KEY,value="output/path"}]' \
  --profile DavidArmendarizDW
```

Notes:

- Ensure AWS account has GPU quota for chosen instance types (you mentioned 8 GPUs approved in us-east-1).
- The EC2 AMI used by Batch should have the NVIDIA drivers available. AWS Batch EC2 instances using newer Deep Learning AMIs or the default ECS optimized AMIs may be sufficient.
- Monitor logs in CloudWatch; the `logConfiguration` in the job definition sends logs to the Batch log group.

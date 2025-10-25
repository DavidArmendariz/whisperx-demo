# Architecture Diagram

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS Cloud (us-east-1)                          │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         VPC (10.0.0.0/16)                             │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │                    Public Subnets (2 AZs)                       │ │ │
│  │  │                                                                 │ │ │
│  │  │  ┌──────────────────┐        ┌──────────────────┐              │ │ │
│  │  │  │       ALB        │        │       ALB        │              │ │ │
│  │  │  │   (us-east-1a)   │◄──────►│   (us-east-1b)   │              │ │ │
│  │  │  └────────┬─────────┘        └────────┬─────────┘              │ │ │
│  │  │           │                            │                        │ │ │
│  │  │  ┌────────┴────────┐          ┌────────┴────────┐              │ │ │
│  │  │  │  NAT Gateway    │          │  NAT Gateway    │              │ │ │
│  │  │  │   + EIP         │          │   + EIP         │              │ │ │
│  │  │  └─────────────────┘          └─────────────────┘              │ │ │
│  │  │           │                            │                        │ │ │
│  │  └───────────┼────────────────────────────┼────────────────────────┘ │ │
│  │              │                            │                          │ │
│  │              ▼                            ▼                          │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │                   Private Subnets (2 AZs)                       │ │ │
│  │  │                                                                 │ │ │
│  │  │  ┌──────────────────┐        ┌──────────────────┐              │ │ │
│  │  │  │   ECS Fargate    │        │   ECS Fargate    │              │ │ │
│  │  │  │   FastAPI Task   │        │   FastAPI Task   │              │ │ │
│  │  │  │   (512 CPU)      │        │   (512 CPU)      │              │ │ │
│  │  │  │   (1024 MB)      │        │   (1024 MB)      │              │ │ │
│  │  │  └────────┬─────────┘        └────────┬─────────┘              │ │ │
│  │  │           │                            │                        │ │ │
│  │  │           └──────────┬─────────────────┘                        │ │ │
│  │  │                      │                                          │ │ │
│  │  │                      │   Submits Jobs                           │ │ │
│  │  │                      ▼                                          │ │ │
│  │  │           ┌────────────────────┐                                │ │ │
│  │  │           │   AWS Batch Queue  │                                │ │ │
│  │  │           │   (Job Queue)      │                                │ │ │
│  │  │           └──────────┬─────────┘                                │ │ │
│  │  │                      │                                          │ │ │
│  │  │                      ▼                                          │ │ │
│  │  │  ┌──────────────────────────────────────┐                      │ │ │
│  │  │  │   AWS Batch Compute Environment      │                      │ │ │
│  │  │  │   (Auto-scaling EC2 instances)       │                      │ │ │
│  │  │  │                                      │                      │ │ │
│  │  │  │   ┌─────────────────────────┐        │                      │ │ │
│  │  │  │   │   g4dn.xlarge Instance  │        │                      │ │ │
│  │  │  │   │   - 4 vCPUs             │        │                      │ │ │
│  │  │  │   │   - 16 GB RAM           │        │                      │ │ │
│  │  │  │   │   - 1x NVIDIA T4 GPU    │        │                      │ │ │
│  │  │  │   │   - WhisperX Container  │        │                      │ │ │
│  │  │  │   └─────────────────────────┘        │                      │ │ │
│  │  │  │                                      │                      │ │ │
│  │  │  │   (Scales to 0 when idle)            │                      │ │ │
│  │  │  └──────────────────────────────────────┘                      │ │ │
│  │  │                                                                 │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │                      S3 VPC Endpoint                            │ │ │
│  │  │                  (Private S3 Access)                            │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         AWS Services (Regional)                       │ │
│  │                                                                       │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │ │
│  │  │   S3 Bucket      │  │  ECR Repository  │  │  CloudWatch Logs │   │ │
│  │  │   Audio Files    │  │   - FastAPI      │  │   - ECS Logs     │   │ │
│  │  │   Transcriptions │  │   - Batch Worker │  │   - Batch Logs   │   │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘   │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              GitHub Actions                                 │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Deploy          │  │  Deploy          │  │  Deploy          │          │
│  │  Terraform       │  │  FastAPI         │  │  Batch Worker    │          │
│  │                  │  │                  │  │                  │          │
│  │  1. Plan/Apply   │  │  1. Build Image  │  │  1. Build Image  │          │
│  │  2. Output ARNs  │  │  2. Push to ECR  │  │  2. Push to ECR  │          │
│  └────────┬─────────┘  │  3. Update ECS   │  │  3. Register Job │          │
│           │            └──────────────────┘  │     Definition   │          │
│           │                                  └──────────────────┘          │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │  OIDC Provider   │                                                       │
│  │  (No Keys!)      │                                                       │
│  └──────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │
     │ 1. Upload Audio (POST /transcribe)
     ▼
┌─────────────────────┐
│  Application Load  │
│     Balancer       │
└─────────┬───────────┘
          │
          │ 2. Route to ECS Task
          ▼
┌─────────────────────┐
│   FastAPI Service   │
│   (ECS Fargate)     │
└─────────┬───────────┘
          │
          │ 3. Upload to S3
          ▼
┌─────────────────────┐
│    S3 Bucket        │
│  /input/audio.mp3   │
└─────────────────────┘
          │
          │ 4. Submit Batch Job
          ▼
┌─────────────────────┐
│   AWS Batch Queue   │
└─────────┬───────────┘
          │
          │ 5. Schedule Job
          ▼
┌─────────────────────┐
│  Batch Compute Env  │
│  (Starts Instance)  │
└─────────┬───────────┘
          │
          │ 6. Run Container
          ▼
┌─────────────────────┐
│  g4dn.xlarge        │
│  WhisperX Worker    │
│                     │
│  7. Download Audio  │◄──┐
│  8. Transcribe      │   │
│  9. Upload Result   │───┘
└─────────┬───────────┘
          │
          │ 10. Save JSON
          ▼
┌─────────────────────┐
│    S3 Bucket        │
│ /output/result.json │
└─────────────────────┘
          │
          │ 11. User Downloads
          ▼
┌─────────────────────┐
│  Transcription      │
│  {segments, text}   │
└─────────────────────┘
```

## Network Architecture

```
Internet
   │
   │ HTTP/HTTPS
   ▼
┌─────────────────────────────────────────────────┐
│         Internet Gateway (IGW)                  │
└─────────────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────────────┐
│         Application Load Balancer               │
│         (Public Subnets)                        │
│         Security Group: Allow 80, 443           │
└─────────────────────────────────────────────────┘
   │
   │ Port 8000
   ▼
┌─────────────────────────────────────────────────┐
│         ECS Tasks (FastAPI)                     │
│         (Private Subnets)                       │
│         Security Group: Allow 8000 from ALB     │
└─────────────────────────────────────────────────┘
   │
   │ Via NAT Gateway
   ▼
┌─────────────────────────────────────────────────┐
│         NAT Gateway                             │
│         (Public Subnets)                        │
└─────────────────────────────────────────────────┘
   │
   ▼
Internet (for AWS API calls, ECR pulls, etc.)


Private Resources:
┌─────────────────────────────────────────────────┐
│    Batch Compute (g4dn.xlarge)                  │
│    (Private Subnets)                            │
│    Security Group: Outbound only                │
└─────────────────────────────────────────────────┘
         │
         │ Via S3 VPC Endpoint
         ▼
┌─────────────────────────────────────────────────┐
│           S3 Bucket                             │
│           (No public access)                    │
└─────────────────────────────────────────────────┘
```

## Security Architecture

```
┌─────────────────────────────────────────────────┐
│              GitHub Actions                     │
│                                                 │
│  Uses OIDC (No Long-Lived Credentials!)        │
└──────────────────┬──────────────────────────────┘
                   │
                   │ AssumeRoleWithWebIdentity
                   ▼
┌─────────────────────────────────────────────────┐
│         IAM OIDC Provider                       │
│         trust: token.actions.githubusercontent  │
└──────────────────┬──────────────────────────────┘
                   │
                   │ Temporary Credentials
                   ▼
┌─────────────────────────────────────────────────┐
│         IAM Role: GitHub Actions                │
│         - ECR Push/Pull                         │
│         - ECS Update Service                    │
│         - Batch Register Job Definition         │
└─────────────────────────────────────────────────┘


Runtime IAM Roles:
┌─────────────────────────────────────────────────┐
│    ECS Task Execution Role                      │
│    - ECR Pull Images                            │
│    - CloudWatch Logs Write                      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│    ECS Task Role (FastAPI)                      │
│    - S3 Put/Get Object                          │
│    - Batch Submit Job                           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│    Batch Job Role (Worker)                      │
│    - S3 Put/Get Object                          │
└─────────────────────────────────────────────────┘

All roles follow least privilege principle!
```

## Monitoring & Logging

```
┌─────────────────────────────────────────────────┐
│              Application Logs                   │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│         CloudWatch Logs                         │
│                                                 │
│  ┌──────────────────────────────────┐           │
│  │  /ecs/whisperx-demo/fastapi      │           │
│  │  - API requests                  │           │
│  │  - Batch job submissions         │           │
│  │  - Errors                        │           │
│  │  Retention: 7 days               │           │
│  └──────────────────────────────────┘           │
│                                                 │
│  ┌──────────────────────────────────┐           │
│  │  /aws/batch/whisperx-demo        │           │
│  │  - Transcription progress        │           │
│  │  - WhisperX output               │           │
│  │  - Job failures                  │           │
│  │  Retention: 7 days               │           │
│  └──────────────────────────────────┘           │
│                                                 │
└─────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│         CloudWatch Insights                     │
│         (Query and analyze logs)                │
└─────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────┐
│         ECS Container Insights                  │
│         - CPU/Memory metrics                    │
│         - Task counts                           │
│         - Network metrics                       │
└─────────────────────────────────────────────────┘
```

## Cost Breakdown

```
Monthly Fixed Costs:
┌─────────────────────────────────────────────────┐
│  Component              │  Cost/Month           │
├─────────────────────────┼───────────────────────┤
│  ECS Fargate (2 tasks)  │  ~$30                 │
│  - 0.5 vCPU x 2         │                       │
│  - 1 GB RAM x 2         │                       │
│  - 24/7 running         │                       │
├─────────────────────────┼───────────────────────┤
│  NAT Gateway (2 AZs)    │  ~$65                 │
│  - $0.045/hour x 2      │                       │
│  - Data transfer        │                       │
├─────────────────────────┼───────────────────────┤
│  Application Load       │  ~$23                 │
│  Balancer               │                       │
├─────────────────────────┼───────────────────────┤
│  S3 Storage             │  ~$1-5                │
│  - Depends on usage     │                       │
├─────────────────────────┼───────────────────────┤
│  CloudWatch Logs        │  ~$1-5                │
│  - 7 day retention      │                       │
├─────────────────────────┼───────────────────────┤
│  TOTAL BASELINE         │  ~$125/month          │
└─────────────────────────┴───────────────────────┘

Variable Costs (Pay per Use):
┌─────────────────────────────────────────────────┐
│  g4dn.xlarge            │  $0.526/hour          │
│  - Only when running    │                       │
│  - Example: 10 hrs/mo   │  ~$5.26               │
│  - Example: 100 hrs/mo  │  ~$52.60              │
└─────────────────────────┴───────────────────────┘

Total Monthly Cost Example:
  Light usage (10 job hours): ~$130/month
  Medium usage (50 job hours): ~$151/month
  Heavy usage (100 job hours): ~$178/month
```

---

## Key Features Highlighted

✅ **High Availability**: Multi-AZ deployment  
✅ **Auto-Scaling**: ECS and Batch scale automatically  
✅ **Security**: Private subnets, least privilege IAM  
✅ **Cost-Effective**: Batch scales to zero when idle  
✅ **GPU Accelerated**: g4dn.xlarge with NVIDIA T4  
✅ **Fully Automated**: GitHub Actions CI/CD  
✅ **Production Ready**: Health checks, logging, retries

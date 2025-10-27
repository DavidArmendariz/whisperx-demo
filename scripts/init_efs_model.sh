#!/bin/bash

echo "🔧 Initializing Whisper model on EFS..."
echo ""

# Get EFS file system ID from Terraform (if available)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

EFS_ID=""
AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

if [ -d "$TERRAFORM_DIR/.terraform" ]; then
    cd "$TERRAFORM_DIR"
    EFS_ID=$(terraform output -raw efs_file_system_id 2>/dev/null || echo "")
    AWS_REGION_FROM_TF=$(terraform output -raw aws_region 2>/dev/null || echo "")
    if [ -n "$AWS_REGION_FROM_TF" ]; then
        AWS_REGION="$AWS_REGION_FROM_TF"
    fi
fi

if [ -n "$EFS_ID" ]; then
    echo "📁 EFS File System ID: $EFS_ID"
    echo "🌍 AWS Region: $AWS_REGION"
    
    # Get EFS DNS name
    EFS_DNS="${EFS_ID}.efs.${AWS_REGION}.amazonaws.com"
    echo "🔗 EFS DNS: $EFS_DNS"
    echo ""
else
    echo "ℹ️  Terraform not applied yet or EFS not created."
    echo "   Run 'cd terraform && terraform apply' first to create EFS."
    echo ""
    echo "   For now, showing generic instructions..."
    echo "   Replace <EFS_ID> and <AWS_REGION> with your actual values."
    echo ""
    EFS_DNS="<EFS_ID>.efs.<AWS_REGION>.amazonaws.com"
fi

echo "================================================================================"
echo "  MANUAL STEPS TO INITIALIZE MODEL ON EFS"
echo "================================================================================"
echo ""
echo "This is a ONE-TIME setup. The model will persist on EFS for all Lambda runs."
echo ""
echo "📋 Option 1: Using EC2 Instance (Recommended)"
echo "──────────────────────────────────────────────────────────────────────────────"
echo ""
echo "1️⃣  Launch EC2 instance (Amazon Linux 2023) in the PRIVATE subnet:"
echo "   - Same VPC as Lambda"
echo "   - Attach EFS security group (allows NFS port 2049)"
echo "   - Connect via Systems Manager Session Manager (no SSH key needed)"
echo ""
echo "2️⃣  Connect to EC2 and mount EFS:"
echo ""
echo "   sudo mkdir -p /mnt/efs"
echo "   sudo mount -t nfs4 -o nfsvers=4.1 ${EFS_DNS}:/ /mnt/efs"
echo "   df -h | grep efs  # Verify mount"
echo ""
echo "3️⃣  Install Python 3.12 and faster-whisper:"
echo ""
echo "   sudo dnf install python3.12 python3-pip -y"
echo "   pip3.12 install --user faster-whisper"
echo ""
echo "4️⃣  Download the faster-whisper model to EFS (takes ~5 minutes):"
echo ""
echo "   python3.12 << 'PYTHON_EOF'"
echo "from faster_whisper import WhisperModel"
echo "import logging"
echo ""
echo "logging.basicConfig(level=logging.INFO)"
echo "print('📥 Downloading faster-whisper model to EFS...')"
echo ""
echo "model = WhisperModel("
echo "    'small',"
echo "    device='cpu',"
echo "    compute_type='int8',"
echo "    download_root='/mnt/efs/models'"
echo ")"
echo ""
echo "print('✅ Model downloaded successfully!')"
echo "PYTHON_EOF"
echo ""
echo "5️⃣  Create cache directory with proper permissions:"
echo ""
echo "   sudo mkdir -p /mnt/efs/cache"
echo "   sudo chown -R 1000:1000 /mnt/efs/models"
echo "   sudo chown -R 1000:1000 /mnt/efs/cache"
echo "   sudo chmod -R 755 /mnt/efs/models"
echo "   sudo chmod -R 777 /mnt/efs/cache"
echo ""
echo "6️⃣  Verify the model exists:"
echo ""
echo "   ls -lh /mnt/efs/models/"
echo "   du -sh /mnt/efs/models/*"
echo ""
echo "   # Should show the 'small' model directory (~900MB)"
echo ""
echo "7️⃣  Terminate the EC2 instance (no longer needed)"
echo ""
echo "──────────────────────────────────────────────────────────────────────────────"
echo ""
echo "📋 Option 2: Quick Commands (Copy-Paste to EC2)"
echo "──────────────────────────────────────────────────────────────────────────────"
echo ""
cat << 'QUICKSTART'
# Mount EFS
sudo mkdir -p /mnt/efs
sudo mount -t nfs4 -o nfsvers=4.1 EFS_DNS_HERE:/ /mnt/efs

# Install dependencies
sudo dnf install python3.12 python3-pip -y
pip3.12 install --user faster-whisper

# Download model
python3.12 << 'EOF'
from faster_whisper import WhisperModel
print("Downloading model...")
model = WhisperModel('small', device='cpu', compute_type='int8', download_root='/mnt/efs/models')
print("✓ Done!")
EOF

# Set permissions
sudo mkdir -p /mnt/efs/cache
sudo chown -R 1000:1000 /mnt/efs/models /mnt/efs/cache
sudo chmod -R 755 /mnt/efs/models
sudo chmod -R 777 /mnt/efs/cache

# Verify
ls -lh /mnt/efs/models/
du -sh /mnt/efs/models/*
QUICKSTART

echo ""
echo "Replace 'EFS_DNS_HERE' with: ${EFS_DNS}"
echo ""
echo "================================================================================"
echo ""
echo "⚠️  IMPORTANT: The model MUST be downloaded to EFS before Lambda can run!"
echo ""
echo "After initialization, the Lambda function will:"
echo "  • Mount EFS at /mnt/efs"
echo "  • Load model from /mnt/efs/models/small"
echo "  • Use /mnt/efs/cache for temporary files"
echo ""
echo "================================================================================"
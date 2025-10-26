#!/bin/bash
set -e

echo "Building Lambda Layer for faster-whisper model..."
echo "Building Docker image for linux/amd64 platform..."
docker build --platform linux/amd64 -t whisper-layer-builder .

# Create output directory
echo "Creating output directory..."
mkdir -p output

# Extract layer content
echo "Extracting layer content from Docker container..."
docker run --rm --platform linux/amd64 -v "$(pwd)/output:/output" whisper-layer-builder

# Create zip file for Lambda layer
echo "Creating zip file for Lambda layer..."
cd output
tar -xzf layer.tar.gz
zip -r whisper-model-layer.zip python/
cd ..

echo ""
echo "✅ Layer built successfully!"
echo "📦 Output: lambda-layer/output/whisper-model-layer.zip"
echo ""

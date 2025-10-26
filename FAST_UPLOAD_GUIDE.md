# Fast Upload Performance Optimization

## Problem Solved

The original upload method had a significant bottleneck:

- Files were uploaded from client → API server → S3
- The API server acted as a proxy, consuming bandwidth and memory
- Large files caused slow uploads and potential timeouts
- Server resources were wasted on file transfer operations

## Solution: Pre-signed URLs

The new approach uses AWS S3 pre-signed URLs for direct client-to-S3 uploads:

```
OLD:  Client → API Server → S3        (slow, resource-intensive)
NEW:  Client → S3 (directly)          (fast, efficient)
```

## Performance Benefits

1. **Faster Uploads**: Direct S3 uploads eliminate the API server bottleneck
2. **Reduced Server Load**: API server only handles metadata, not file content
3. **Better Scalability**: Multiple concurrent uploads don't overwhelm the server
4. **Cost Efficiency**: Less compute time and bandwidth usage on the API server
5. **Improved Reliability**: Fewer points of failure in the upload process

## 🌐 Web Browser Performance

**YES! This is especially fast from web browsers!** Here's why:

### Browser Benefits

- **Direct Upload**: Browser sends file directly to S3, no proxy server
- **Parallel Processing**: Your web app remains responsive during upload
- **Native Progress**: Built-in upload progress tracking with XMLHttpRequest
- **Better UX**: Users see immediate upload feedback
- **No Timeouts**: No risk of API gateway timeouts on large files

### Performance Comparison (Web Browser)

| Method                     | 100MB File Upload Time | Server Resources | User Experience  |
| -------------------------- | ---------------------- | ---------------- | ---------------- |
| **Legacy** (`/transcribe`) | ~2-5 minutes           | High CPU/Memory  | Slow, blocking   |
| **Pre-signed URL**         | ~30-60 seconds         | Minimal          | Fast, responsive |

### Why Browsers Benefit Most

1. **No Server Bottleneck**: File doesn't touch your API server
2. **CDN-like Performance**: S3 has global edge locations
3. **Concurrent Uploads**: Multiple users can upload simultaneously
4. **Progress Tracking**: Real-time feedback to users
5. **Mobile Friendly**: Works great on mobile browsers

## New API Endpoints

### 🚀 Fast Upload Workflow (Recommended)

1. **POST /upload-url** - Generate pre-signed URL

   ```json
   {
     "filename": "audio.mp3",
     "content_type": "audio/mpeg",
     "language": "es",
     "execution_method": "batch"
   }
   ```

2. **PUT to pre-signed URL** - Upload directly to S3

   ```bash
   curl -X PUT -H "Content-Type: audio/mpeg" --data-binary @audio.mp3 <presigned_url>
   ```

3. **POST /transcribe-from-s3** - Start transcription
   ```json
   {
     "s3_key": "input/20231026-123456-uuid/audio.mp3",
     "language": "es",
     "execution_method": "batch"
   }
   ```

### 🐌 Legacy Endpoint (Preserved for compatibility)

- **POST /transcribe** - Upload through API server (slower)

## Usage Examples

### Python Client Example

See `test_fast_upload.py` for a complete example:

```bash
python test_fast_upload.py audio.mp3 --language es --method batch
```

### JavaScript/Browser Example

````javascript
### JavaScript/Browser Example

**✅ This is FAST from web browsers!** The browser uploads directly to S3, bypassing your API server entirely.

```javascript
// Step 1: Get pre-signed URL
const uploadData = await fetch('/upload-url', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: file.name,
    content_type: file.type,
    language: 'es',
    execution_method: 'batch'
  })
}).then(r => r.json());

// Step 2: Upload directly to S3 (FAST - no server proxy!)
await fetch(uploadData.upload_url, {
  method: 'PUT',
  body: file,  // File goes directly from browser to S3
  headers: { 'Content-Type': file.type }
});

// Step 3: Start transcription
const jobData = await fetch('/transcribe-from-s3', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    s3_key: uploadData.s3_input_key,
    language: 'es',
    execution_method: 'batch'
  })
}).then(r => r.json());
````

### Browser Upload with Progress Tracking

```javascript
async function uploadWithProgress(file, onProgress) {
  // Step 1: Get pre-signed URL
  const uploadData = await fetch("/upload-url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      language: "es",
      execution_method: "batch",
    }),
  }).then((r) => r.json());

  // Step 2: Upload with progress tracking
  const xhr = new XMLHttpRequest();

  return new Promise((resolve, reject) => {
    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status === 200) {
        resolve(uploadData);
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Upload failed")));

    xhr.open("PUT", uploadData.upload_url);
    xhr.setRequestHeader("Content-Type", file.type);
    xhr.send(file);
  });
}

// Usage with progress
const file = document.getElementById("fileInput").files[0];
const uploadData = await uploadWithProgress(file, (progress) => {
  console.log(`Upload progress: ${progress.toFixed(2)}%`);
  // Update your progress bar here
});

// Step 3: Start transcription
const jobData = await fetch("/transcribe-from-s3", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    s3_key: uploadData.s3_input_key,
    language: "es",
    execution_method: "batch",
  }),
}).then((r) => r.json());
```

````

### cURL Example

```bash
# Step 1: Get pre-signed URL
UPLOAD_DATA=$(curl -X POST http://localhost:8000/upload-url \
  -H "Content-Type: application/json" \
  -d '{"filename": "audio.mp3", "content_type": "audio/mpeg", "language": "es"}')

# Extract the upload URL (you'll need jq or parse JSON manually)
UPLOAD_URL=$(echo $UPLOAD_DATA | jq -r '.upload_url')
S3_KEY=$(echo $UPLOAD_DATA | jq -r '.s3_input_key')

# Step 2: Upload to S3
curl -X PUT -H "Content-Type: audio/mpeg" --data-binary @audio.mp3 "$UPLOAD_URL"

# Step 3: Start transcription
curl -X POST http://localhost:8000/transcribe-from-s3 \
  -H "Content-Type: application/json" \
  -d "{\"s3_key\": \"$S3_KEY\", \"language\": \"es\", \"execution_method\": \"batch\"}"
````

## Security Features

- Pre-signed URLs expire after 1 hour for security
- File validation still occurs before URL generation
- S3 bucket permissions control access
- Job IDs are UUIDs to prevent enumeration attacks

## Monitoring Upload Performance

The API now includes performance-focused logging:

- Tracks pre-signed URL generation
- Monitors S3 upload completion
- Logs job submission times

This allows you to measure the actual performance improvements in your environment.

## Migration Guide

### For Existing Clients

The old `/transcribe` endpoint remains functional for backward compatibility. However, you should migrate to the new workflow for better performance:

1. Replace single `/transcribe` calls with the 3-step process
2. Update error handling for the multi-step workflow
3. Consider implementing retry logic for S3 uploads
4. Update your UI to show upload progress directly to S3

### For New Implementations

Always use the fast upload workflow unless you have specific requirements that necessitate the legacy approach.

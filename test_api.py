#!/usr/bin/env python3
"""
Test script for WhisperX Audio Transcription API
"""

import argparse
import sys
import time
from pathlib import Path

import requests


def test_health(base_url: str) -> bool:
    """Test the health endpoint"""
    print("\n🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            print(f"✅ Health check passed: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_root(base_url: str) -> bool:
    """Test the root endpoint"""
    print("\n🔍 Testing root endpoint...")
    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code == 200:
            print(f"✅ Root endpoint passed: {response.json()}")
            return True
        else:
            print(f"❌ Root endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Root endpoint error: {e}")
        return False


def test_transcription(base_url: str, audio_file: str, language: str = "es") -> dict:
    """Test audio transcription"""
    print(f"\n🔍 Testing transcription with file: {audio_file}")

    if not Path(audio_file).exists():
        print(f"❌ Audio file not found: {audio_file}")
        return None

    try:
        with open(audio_file, "rb") as f:
            files = {"file": f}
            data = {"language": language}
            response = requests.post(
                f"{base_url}/transcribe", files=files, data=data, timeout=30
            )

        if response.status_code == 202:
            result = response.json()
            print("✅ Transcription job submitted successfully!")
            print(f"   Job ID: {result.get('job_id')}")
            print(f"   Batch Job ID: {result.get('batch_job_id')}")
            print(f"   S3 Input: {result.get('s3_input_key')}")
            print(f"   S3 Output: {result.get('s3_output_key')}")
            return result
        else:
            print(f"❌ Transcription failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Transcription error: {e}")
        return None


def check_job_status(base_url: str, batch_job_id: str, max_wait: int = 600) -> bool:
    """Check job status with polling"""
    print(f"\n🔍 Checking job status (max wait: {max_wait}s)...")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{base_url}/job/{batch_job_id}", timeout=10)

            if response.status_code == 200:
                result = response.json()
                status = result.get("status")

                print(f"   Status: {status}")

                if status == "SUCCEEDED":
                    print("✅ Job completed successfully!")
                    print(f"   Started at: {result.get('started_at')}")
                    print(f"   Stopped at: {result.get('stopped_at')}")
                    return True
                elif status == "FAILED":
                    print("❌ Job failed!")
                    print(f"   Reason: {result.get('status_reason')}")
                    return False
                elif status in [
                    "SUBMITTED",
                    "PENDING",
                    "RUNNABLE",
                    "STARTING",
                    "RUNNING",
                ]:
                    print("   Job still processing... (waiting 10s)")
                    time.sleep(10)
                else:
                    print(f"❌ Unknown status: {status}")
                    return False
            else:
                print(f"❌ Failed to get job status: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error checking job status: {e}")
            return False

    print("⏰ Timeout waiting for job to complete")
    return False


def main():
    parser = argparse.ArgumentParser(description="Test WhisperX API")
    parser.add_argument(
        "--url", required=True, help="Base URL of the API (e.g., http://alb-dns-name)"
    )
    parser.add_argument("--audio", help="Path to audio file for transcription test")
    parser.add_argument("--language", default="es", help="Language code (default: es)")
    parser.add_argument(
        "--wait",
        type=int,
        default=600,
        help="Max seconds to wait for job (default: 600)",
    )
    parser.add_argument(
        "--skip-transcription", action="store_true", help="Skip transcription test"
    )

    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    print("=" * 80)
    print("WhisperX API Test Suite")
    print("=" * 80)
    print(f"Base URL: {base_url}")

    # Test 1: Health check
    if not test_health(base_url):
        print("\n❌ Health check failed. Cannot proceed.")
        sys.exit(1)

    # Test 2: Root endpoint
    if not test_root(base_url):
        print("\n⚠️  Root endpoint failed, but continuing...")

    # Test 3: Transcription (if audio file provided)
    if not args.skip_transcription:
        if not args.audio:
            print("\n⚠️  No audio file provided. Skipping transcription test.")
            print("   Use --audio <file> to test transcription")
        else:
            result = test_transcription(base_url, args.audio, args.language)

            if result:
                batch_job_id = result.get("batch_job_id")
                if batch_job_id:
                    # Test 4: Job status polling
                    job_success = check_job_status(base_url, batch_job_id, args.wait)

                    if job_success:
                        print("\n✅ All tests passed!")
                        print("\nTo download the result:")
                        print(
                            f"aws s3 cp s3://<bucket>/{result.get('s3_output_key')} result.json"
                        )
                    else:
                        print("\n❌ Job did not complete successfully")
                        sys.exit(1)
            else:
                print("\n❌ Transcription test failed")
                sys.exit(1)

    print("\n" + "=" * 80)
    print("Test suite completed!")
    print("=" * 80)


if __name__ == "__main__":
    main()

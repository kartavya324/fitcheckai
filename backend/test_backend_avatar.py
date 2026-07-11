"""
Test the end-to-end avatar generation pipeline through the FastAPI backend API.
Usage: python test_backend_avatar.py
"""
import sys
import time
import requests
from pathlib import Path

def test_pipeline():
    backend_url = "http://localhost:8001/api/v1/avatar/create"
    image_path = Path("test_person.jpg")
    
    if not image_path.exists():
        print(f"Error: test image {image_path} not found.")
        sys.exit(1)
        
    print(f"Starting end-to-end test with image: {image_path}")
    print(f"Uploading to backend: {backend_url} ...")
    
    # Prepare the file upload
    with open(image_path, "rb") as f:
        files = {"person_image": ("test_person.jpg", f, "image/jpeg")}
        try:
            r = requests.post(backend_url, files=files, timeout=60)
            r.raise_for_status()
            res = r.json()
        except requests.ConnectionError:
            print("ERROR: FastAPI backend is not running on http://localhost:8001")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Upload request failed: {e}")
            sys.exit(1)
            
    job_id = res.get("job_id")
    poll_url = f"http://localhost:8001/api/v1/avatar/status/{job_id}"
    print(f"Upload successful. Job ID: {job_id}")
    print(f"Polling job status at: {poll_url} ...")
    
    start_time = time.time()
    last_stage = None
    last_pct = -1
    
    while True:
        try:
            r = requests.get(poll_url, timeout=10)
            r.raise_for_status()
            status_data = r.json()
        except Exception as e:
            print(f"\nERROR: Polling request failed: {e}")
            time.sleep(5)
            continue
            
        status = status_data.get("status")
        progress = status_data.get("progress", 0)
        stage = status_data.get("stage", "Unknown")
        elapsed = int(time.time() - start_time)
        
        if stage != last_stage or progress != last_pct:
            print(f"[{elapsed}s] Status: {status} | Progress: {progress}% | Stage: {stage}")
            last_stage = stage
            last_pct = progress
            
        if status == "completed":
            print("\n==============================================")
            print("SUCCESS! Avatar generation completed.")
            print(f"Avatar GLB URL: {status_data.get('avatar_url')}")
            analysis = status_data.get("analysis")
            if analysis:
                print(f"Face Thumbnail URL: {analysis.get('face_thumbnail_url')}")
                print(f"Dominant Colors: {analysis.get('dominant_colors')}")
            else:
                print("No analysis metadata returned.")
            print("==============================================")
            break
        elif status == "failed":
            print("\n==============================================")
            print("FAILURE! Avatar generation failed.")
            print(f"Details: {status_data}")
            
            # Print last error log if it exists
            error_log = Path("last_error.log")
            if error_log.exists():
                print("\nlast_error.log contents:")
                print(error_log.read_text())
            print("==============================================")
            break
            
        time.sleep(5)

if __name__ == "__main__":
    test_pipeline()

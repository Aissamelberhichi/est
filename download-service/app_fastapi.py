from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import os
import tempfile
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
from typing import Optional, List
import io

# Load environment variables
load_dotenv()

app = FastAPI(title="MinIO Download Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MinIO configuration
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', '192.168.1.2')
MINIO_PORT = os.getenv('MINIO_PORT', '9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
BUCKET_NAME = "uploads"
MINIO_URL = f"http://{MINIO_ENDPOINT}:{MINIO_PORT}"

# Initialize MinIO client
minio_client = Minio(
    f"{MINIO_ENDPOINT}:{MINIO_PORT}",
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Set to True if using HTTPS
)

@app.get("/api/health")
def health_check():
    """Health check endpoint to verify the API is running"""
    return {"status": "ok", "message": "Download service is running"}

@app.get("/api/test-minio")
def test_minio_connection():
    """Test the connection to MinIO server"""
    try:
        # Check if we can access the bucket
        minio_client.bucket_exists(BUCKET_NAME)
        
        return {
            "status": "success",
            "message": "Successfully connected to MinIO server",
            "minio_url": MINIO_URL,
            "bucket": BUCKET_NAME
        }
    except S3Error as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error connecting to MinIO server: {str(e)}"
        )

@app.get("/api/download/{object_name:path}")
def download_file(object_name: str):
    """
    Download a file from MinIO
    
    - **object_name**: The name of the object to download
    """
    try:
        # Get the object's metadata to determine the content type and display name
        stat = minio_client.stat_object(BUCKET_NAME, object_name)
        metadata = stat.metadata
        
        # Get the display name from metadata or use the object name
        display_name = metadata.get('X-Amz-Meta-Display-Name', '')
        original_filename = metadata.get('X-Amz-Meta-Original-Filename', '')
        
        # If no display name, extract from object name
        if not display_name:
            display_name = object_name.split('_', 1)[1] if '_' in object_name else object_name
        
        # Make sure the display name has the correct extension
        if original_filename and '.' in original_filename:
            # Get extension from original filename
            original_ext = original_filename.split('.')[-1]
            
            # Check if display name already has an extension
            if '.' in display_name:
                display_name_parts = display_name.split('.')
                display_name_base = '.'.join(display_name_parts[:-1])
                display_name = f"{display_name_base}.{original_ext}"
            else:
                # Add extension if missing
                display_name = f"{display_name}.{original_ext}"
        
        # Create a temporary file to store the downloaded content
        temp_file_path = os.path.join(tempfile.gettempdir(), object_name)
        
        try:
            # Download the file from MinIO
            minio_client.fget_object(BUCKET_NAME, object_name, temp_file_path)
            
            # Read the file content
            with open(temp_file_path, "rb") as file:
                file_content = file.read()
            
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            
            # Create a streaming response
            response = StreamingResponse(
                io.BytesIO(file_content),
                media_type=stat.content_type or "application/octet-stream"
            )
            
            # Set Content-Disposition header for download
            response.headers["Content-Disposition"] = f'attachment; filename="{display_name}"'
            
            return response
            
        except Exception as e:
            # Clean up in case of error
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise e
    
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@app.get("/api/files")
def list_files():
    """List all files in the MinIO bucket with metadata"""
    try:
        # List all objects in the bucket
        objects = minio_client.list_objects(BUCKET_NAME, recursive=True)
        
        files = []
        for obj in objects:
            # Generate a URL for each file
            file_url = f"{MINIO_URL}/{BUCKET_NAME}/{obj.object_name}"
            
            # Get the object's metadata (stat_object returns metadata)
            try:
                stat = minio_client.stat_object(BUCKET_NAME, obj.object_name)
                metadata = stat.metadata
                
                # Extract display name and description from metadata
                display_name = metadata.get('X-Amz-Meta-Display-Name', '')
                description = metadata.get('X-Amz-Meta-Description', '')
                
                # If display name is not in metadata, use the object name
                if not display_name:
                    display_name = obj.object_name
            except Exception as e:
                print(f"Error getting metadata for {obj.object_name}: {e}")
                display_name = obj.object_name
                description = ''
            
            # Add file information to the list
            files.append({
                "name": obj.object_name,
                "display_name": display_name,
                "description": description,
                "size": obj.size,
                "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                "url": file_url
            })
        
        return {"files": files}
    
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('FLASK_PORT', 5002))
    uvicorn.run("app_fastapi:app", host="0.0.0.0", port=port, reload=True)

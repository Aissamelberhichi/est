from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import tempfile
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

app = FastAPI(title="MinIO Upload Service")

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

# Create bucket if it doesn't exist
try:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' created successfully")
    else:
        print(f"Bucket '{BUCKET_NAME}' already exists")
except S3Error as e:
    print(f"Error with MinIO: {e}")

@app.get("/api/health")
def health_check():
    """Health check endpoint to verify the API is running"""
    return {"status": "ok", "message": "Upload service is running"}

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

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    custom_filename: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """
    Upload a file to MinIO with optional custom filename and description
    
    - **file**: The file to upload
    - **custom_filename**: Optional custom name for the file
    - **description**: Optional description for the file
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    if file.filename == '':
        raise HTTPException(status_code=400, detail="No file selected")
    
    # Use custom filename if provided, otherwise use original filename
    display_name = custom_filename.strip() if custom_filename else file.filename
    
    try:
        # Generate a unique object name using UUID to avoid conflicts
        object_name = f"{uuid.uuid4().hex}_{file.filename}"
        
        # Create a temporary file path to handle the upload
        temp_file_path = os.path.join(tempfile.gettempdir(), object_name)
        
        # Prepare metadata for the file
        metadata = {
            "X-Amz-Meta-Display-Name": display_name,
            "X-Amz-Meta-Original-Filename": file.filename
        }
        
        # Add description to metadata if provided
        if description:
            metadata["X-Amz-Meta-Description"] = description
        
        try:
            # Save uploaded file to temporary location
            content = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(content)
            
            # Get file size and content type
            file_size = os.path.getsize(temp_file_path)
            content_type = file.content_type or 'application/octet-stream'
            
            # Upload the file to MinIO with metadata
            minio_client.fput_object(
                bucket_name=BUCKET_NAME,
                object_name=object_name,
                file_path=temp_file_path,
                content_type=content_type,
                metadata=metadata
            )
            
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as e:
                print(f"Warning: Could not remove temporary file: {e}")
        
        # Generate a URL for the uploaded file
        file_url = f"{MINIO_URL}/{BUCKET_NAME}/{object_name}"
        
        # Return success response
        return {
            "message": "File uploaded successfully to MinIO",
            "file_name": file.filename,
            "display_name": display_name,
            "description": description,
            "object_name": object_name,
            "url": file_url,
            "size": file_size
        }
    
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('FLASK_PORT', 5001))
    uvicorn.run("app_fastapi:app", host="0.0.0.0", port=port, reload=True)

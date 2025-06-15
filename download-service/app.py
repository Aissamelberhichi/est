from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

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

# Create a replacement for after_this_request
def after_this_request_replacement(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = app.make_response(f(*args, **kwargs))
        return response
    return decorated_function

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the API is running"""
    return jsonify({"status": "ok", "message": "Download service is running"})

@app.route('/api/test-minio', methods=['GET'])
def test_minio_connection():
    """Test the connection to MinIO server"""
    try:
        # Check if we can access the bucket
        minio_client.bucket_exists(BUCKET_NAME)
        
        return jsonify({
            "status": "success",
            "message": "Successfully connected to MinIO server",
            "minio_url": MINIO_URL,
            "bucket": BUCKET_NAME
        })
    except S3Error as e:
        return jsonify({
            "status": "error",
            "message": f"Error connecting to MinIO server: {str(e)}",
            "minio_url": MINIO_URL,
            "bucket": BUCKET_NAME
        }), 500

@app.route('/api/download/<path:object_name>', methods=['GET'])
def download_file(object_name):
    """Endpoint to download a file from MinIO"""
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
        
        # Define a function to clean up the temporary file
        def remove_temp_file(response):
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as e:
                print(f"Error removing temporary file: {e}")
            return response
        
        try:
            # Download the file from MinIO
            minio_client.fget_object(BUCKET_NAME, object_name, temp_file_path)
            
            # Send the file as an attachment with the display name
            response = send_file(
                temp_file_path,
                mimetype=stat.content_type,
                as_attachment=True,
                download_name=display_name
            )
            
            # Clean up the temporary file after sending
            return remove_temp_file(response)
            
        except Exception as e:
            # Clean up in case of error
            remove_temp_file(None)
            raise e
    
    except S3Error as e:
        return jsonify({"error": f"MinIO error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error downloading file: {str(e)}"}), 500

@app.route('/api/files', methods=['GET'])
def list_files():
    """Endpoint to list all files in the MinIO bucket with metadata"""
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
        
        return jsonify({"files": files}), 200
    
    except S3Error as e:
        return jsonify({"error": f"MinIO error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error listing files: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=True)

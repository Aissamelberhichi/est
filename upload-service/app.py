from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import tempfile
import datetime
from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import jwt

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

# Cassandra configuration
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', '192.168.1.2')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042'))
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'estdb')
CASSANDRA_USER = os.getenv('CASSANDRA_USER', 'cassandra')
CASSANDRA_PASSWORD = os.getenv('CASSANDRA_PASSWORD', 'cassandra')

# Initialize MinIO client
minio_client = Minio(
    f"{MINIO_ENDPOINT}:{MINIO_PORT}",
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False  # Set to True if using HTTPS
)

# Initialize Cassandra connection
try:
    auth_provider = PlainTextAuthProvider(username=CASSANDRA_USER, password=CASSANDRA_PASSWORD)
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT, auth_provider=auth_provider)
    session = cluster.connect(CASSANDRA_KEYSPACE)
    print(f"Connected to Cassandra cluster at {CASSANDRA_HOST}:{CASSANDRA_PORT}")
except Exception as e:
    print(f"Error connecting to Cassandra: {e}")
    session = None

# Create bucket if it doesn't exist
try:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' created successfully")
    else:
        print(f"Bucket '{BUCKET_NAME}' already exists")
except S3Error as e:
    print(f"Error with MinIO: {e}")

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the API is running"""
    return jsonify({"status": "ok", "message": "Upload service is running"})

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

def decode_token(token):
    """Decode JWT token to extract user information"""
    try:
        # Decode without verification for now - in production you should verify the token
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None

def insert_course_record(course_id, title, description, file_url, teacher_id, teacher_name):
    """Insert a new course record into Cassandra database"""
    if not session:
        print("Cannot insert course record: No Cassandra connection")
        return False
    
    try:
        # Prepare and execute the insert query
        query = """
        INSERT INTO courses (course_id, title, description, upload_date, teacher_id, teacher_name, file_url)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        # Current timestamp for upload_date
        upload_date = datetime.datetime.now()
        
        print(f"Attempting to insert course record:")
        print(f"  course_id: {course_id}")
        print(f"  title: {title}")
        print(f"  description: {description}")
        print(f"  upload_date: {upload_date}")
        print(f"  teacher_id: {teacher_id}")
        print(f"  teacher_name: {teacher_name}")
        print(f"  file_url: {file_url}")
        
        # Execute the query
        session.execute(query, (course_id, title, description, upload_date, teacher_id, teacher_name, file_url))
        print(f"Course record inserted successfully: {title}")
        return True
    except Exception as e:
        print(f"Error inserting course record: {e}")
        # Print more detailed error information
        import traceback
        traceback.print_exc()
        return False

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Endpoint to upload a file to MinIO with custom filename and description"""
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    # Get custom filename and description if provided
    custom_filename = request.form.get('custom_filename', '').strip()
    description = request.form.get('description', '').strip()
    
    # Use custom filename if provided, otherwise use original filename
    display_name = custom_filename if custom_filename else file.filename
    
    # Extract user info from token if available
    teacher_id = None
    teacher_name = "Unknown Teacher"
    
    auth_header = request.headers.get('Authorization')
    print(f"Authorization header: {auth_header}")
    
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        print(f"Token found: {token[:20]}...")  # Print first 20 chars for debugging
        user_info = decode_token(token)
        if user_info:
            # Extract user ID and name from token
            teacher_id = user_info.get('sub')  # Subject claim is usually the user ID
            teacher_name = user_info.get('preferred_username') or user_info.get('name') or "Unknown Teacher"
            print(f"Extracted teacher info - ID: {teacher_id}, Name: {teacher_name}")
        else:
            print("Failed to decode token or extract user info")
    else:
        print("No valid Authorization header found")
    
    try:
        # Generate a unique object name using UUID to avoid conflicts
        object_name = f"{uuid.uuid4().hex}_{file.filename}"
        
        # Create a temporary file path to handle the upload
        temp_file_path = os.path.join(tempfile.gettempdir(), object_name)
        
        # Prepare metadata for the file
        metadata = {
            "display-name": display_name,
            "original-filename": file.filename
        }
        
        # Add description to metadata if provided
        if description:
            metadata["description"] = description
        
        try:
            # Save file to temporary location
            file.save(temp_file_path)
            print(f"File saved to temporary location: {temp_file_path}")
            
            # Get file size and content type
            file_size = os.path.getsize(temp_file_path)
            content_type = file.content_type or 'application/octet-stream'
            
            # Upload the file to MinIO with metadata
            print(f"Uploading file to MinIO: {object_name}")
            minio_client.fput_object(
                bucket_name=BUCKET_NAME,
                object_name=object_name,
                file_path=temp_file_path,
                content_type=content_type,
                metadata=metadata
            )
            print(f"File uploaded successfully to MinIO: {object_name}")
            
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    print(f"Temporary file removed: {temp_file_path}")
            except Exception as e:
                print(f"Warning: Could not remove temporary file: {e}")
        
        # Generate a URL for the uploaded file
        file_url = f"{MINIO_URL}/{BUCKET_NAME}/{object_name}"
        
        # Generate a unique course ID
        course_id = uuid.uuid4()
        
        # Insert course record in Cassandra
        cassandra_success = False
        if session:
            try:
                # Convert teacher_id to UUID if available
                teacher_uuid = None
                if teacher_id:
                    try:
                        teacher_uuid = uuid.UUID(teacher_id)
                    except ValueError:
                        print(f"Invalid UUID format for teacher_id: {teacher_id}")
                        teacher_uuid = uuid.uuid4()
                else:
                    teacher_uuid = uuid.uuid4()
                    
                print(f"Using teacher UUID: {teacher_uuid}")
                
                cassandra_success = insert_course_record(
                    course_id=course_id,
                    title=display_name,
                    description=description,
                    file_url=file_url,
                    teacher_id=teacher_uuid,
                    teacher_name=teacher_name
                )
                
                if cassandra_success:
                    print("Successfully inserted course record in Cassandra")
                else:
                    print("Failed to insert course record in Cassandra")
            except Exception as e:
                print(f"Exception during Cassandra record creation: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("Skipping Cassandra record creation: No database session available")
        
        # Return success response
        return jsonify({
            "message": "File uploaded successfully to MinIO",
            "file_name": file.filename,
            "display_name": display_name,
            "description": description,
            "object_name": object_name,
            "url": file_url,
            "size": file_size,
            "course_id": str(course_id),
            "cassandra_record_created": cassandra_success
        }), 200
    
    except S3Error as e:
        return jsonify({"error": f"MinIO error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error uploading file: {str(e)}"}), 500

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
    port = int(os.getenv('FLASK_PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)

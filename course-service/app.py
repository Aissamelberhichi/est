from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import datetime
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import jwt
import requests

# Load environment variables
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Cassandra configuration
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'cassandra')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042'))
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'estdb')
CASSANDRA_USER = os.getenv('CASSANDRA_USER', 'cassandra')
CASSANDRA_PASSWORD = os.getenv('CASSANDRA_PASSWORD', 'cassandra')

# Service URLs
MINIO_URL = os.getenv('MINIO_URL', 'http://minio-server:9000')
UPLOAD_SERVICE_URL = os.getenv('UPLOAD_SERVICE_URL', 'http://upload-service:5001/api')
DOWNLOAD_SERVICE_URL = os.getenv('DOWNLOAD_SERVICE_URL', 'http://download-service:5002/api')
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://user-service:5003/api')

# Initialize Cassandra connection
try:
    auth_provider = PlainTextAuthProvider(username=CASSANDRA_USER, password=CASSANDRA_PASSWORD)
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT, auth_provider=auth_provider)
    session = cluster.connect(CASSANDRA_KEYSPACE)
    print(f"Connected to Cassandra cluster at {CASSANDRA_HOST}:{CASSANDRA_PORT}")
    
    # Create courses table if it doesn't exist
    session.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            course_id UUID PRIMARY KEY,
            title TEXT,
            description TEXT,
            upload_date TIMESTAMP,
            teacher_id UUID,
            teacher_name TEXT, 
            file_url TEXT
        )
    """)
    print("Courses table created/verified")
    
    # Create enrollments table for student-course relationships
    session.execute("""
        CREATE TABLE IF NOT EXISTS enrollments (
            enrollment_id UUID PRIMARY KEY,
            student_id UUID,
            course_id UUID,
            enrollment_date TIMESTAMP,
            status TEXT
        )
    """)
    print("Enrollments table created/verified")
    
except Exception as e:
    print(f"Error connecting to Cassandra: {e}")
    session = None

def decode_token(token):
    """Decode JWT token to extract user information"""
    try:
        # Decode without verification for now - in production you should verify the token
        decoded = jwt.decode(token, options={"verify_signature": False})
        return decoded
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None

def get_user_from_token(token):
    """Get user information from token"""
    try:
        # Call user service to get user info
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{USER_SERVICE_URL}/users/me", headers=headers)
        if response.status_code == 200:
            return response.json().get('user')
        return None
    except Exception as e:
        print(f"Error getting user from token: {e}")
        
        # Fallback to local token decoding if user service is unavailable
        user_info = decode_token(token)
        if not user_info:
            return None
            
        return {
            'user_id': user_info.get('sub'),
            'username': user_info.get('preferred_username'),
            'role': 'teacher'  # Default assumption
        }

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the API is running"""
    return jsonify({"status": "ok", "message": "Course service is running"})

@app.route('/api/courses', methods=['GET'])
def list_courses():
    """List all courses with optional filtering"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user:
        return jsonify({"error": "Invalid token or user not found"}), 401
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        # Different queries based on user role
        if current_user['role'] == 'admin':
            # Admins see all courses
            rows = session.execute("SELECT * FROM courses")
        elif current_user['role'] == 'teacher':
            # Teachers see their own courses
            teacher_id = uuid.UUID(current_user['user_id'])
            rows = session.execute(f"SELECT * FROM courses WHERE teacher_id = {teacher_id} ALLOW FILTERING")
        else:
            # Students see all courses (could be filtered by enrollment in a real app)
            rows = session.execute("SELECT * FROM courses")
        
        courses = []
        for row in rows:
            courses.append({
                'course_id': str(row.course_id),
                'title': row.title,
                'description': row.description,
                'upload_date': row.upload_date.isoformat() if row.upload_date else None,
                'teacher_id': str(row.teacher_id) if row.teacher_id else None,
                'teacher_name': row.teacher_name,
                'file_url': row.file_url
            })
        return jsonify({"courses": courses}), 200
    except Exception as e:
        print(f"Error listing courses: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error fetching courses: {str(e)}"}), 500

@app.route('/api/courses/<course_id>', methods=['GET'])
def get_course(course_id):
    """Get a specific course by ID"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user:
        return jsonify({"error": "Invalid token or user not found"}), 401
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        # Convert string to UUID
        course_uuid = uuid.UUID(course_id)
        
        # Get course from database
        rows = session.execute(f"SELECT * FROM courses WHERE course_id = {course_uuid}")
        if not rows:
            return jsonify({"error": "Course not found"}), 404
            
        row = rows[0]
        course = {
            'course_id': str(row.course_id),
            'title': row.title,
            'description': row.description,
            'upload_date': row.upload_date.isoformat() if row.upload_date else None,
            'teacher_id': str(row.teacher_id) if row.teacher_id else None,
            'teacher_name': row.teacher_name,
            'file_url': row.file_url
        }
        
        # Check if user is authorized to view this course
        if current_user['role'] == 'teacher' and str(row.teacher_id) != current_user['user_id']:
            # Teachers can only view their own courses
            return jsonify({"error": "Unauthorized to view this course"}), 403
            
        return jsonify({"course": course}), 200
    except Exception as e:
        print(f"Error getting course: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error fetching course: {str(e)}"}), 500

@app.route('/api/courses/<course_id>', methods=['DELETE'])
def delete_course(course_id):
    """Delete a course (teacher or admin only)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user:
        return jsonify({"error": "Invalid token or user not found"}), 401
        
    if current_user['role'] not in ['admin', 'teacher']:
        return jsonify({"error": "Unauthorized. Only teachers or admins can delete courses"}), 403
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        # Convert string to UUID
        course_uuid = uuid.UUID(course_id)
        
        # Get course from database to check ownership
        rows = session.execute(f"SELECT * FROM courses WHERE course_id = {course_uuid}")
        if not rows:
            return jsonify({"error": "Course not found"}), 404
            
        row = rows[0]
        
        # Check if user is authorized to delete this course
        if current_user['role'] == 'teacher' and str(row.teacher_id) != current_user['user_id']:
            # Teachers can only delete their own courses
            return jsonify({"error": "Unauthorized to delete this course"}), 403
            
        # Delete course from database
        session.execute(f"DELETE FROM courses WHERE course_id = {course_uuid}")
        
        # TODO: Delete file from MinIO (would require integration with the upload service)
        
        return jsonify({"message": "Course deleted successfully"}), 200
    except Exception as e:
        print(f"Error deleting course: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error deleting course: {str(e)}"}), 500

@app.route('/api/courses/<course_id>', methods=['PUT'])
def update_course(course_id):
    """Update course information (teacher or admin only)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user:
        return jsonify({"error": "Invalid token or user not found"}), 401
        
    if current_user['role'] not in ['admin', 'teacher']:
        return jsonify({"error": "Unauthorized. Only teachers or admins can update courses"}), 403
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        # Get request data
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Convert string to UUID
        course_uuid = uuid.UUID(course_id)
        
        # Get course from database to check ownership
        rows = session.execute(f"SELECT * FROM courses WHERE course_id = {course_uuid}")
        if not rows:
            return jsonify({"error": "Course not found"}), 404
            
        row = rows[0]
        
        # Check if user is authorized to update this course
        if current_user['role'] == 'teacher' and str(row.teacher_id) != current_user['user_id']:
            # Teachers can only update their own courses
            return jsonify({"error": "Unauthorized to update this course"}), 403
            
        # Update fields that were provided
        title = data.get('title', row.title)
        description = data.get('description', row.description)
        
        # Update course in database
        session.execute(
            """
            UPDATE courses 
            SET title = %s, description = %s
            WHERE course_id = %s
            """,
            (title, description, course_uuid)
        )
        
        return jsonify({
            "message": "Course updated successfully",
            "course": {
                "course_id": course_id,
                "title": title,
                "description": description
            }
        }), 200
    except Exception as e:
        print(f"Error updating course: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error updating course: {str(e)}"}), 500

@app.route('/api/enrollments', methods=['POST'])
def enroll_in_course():
    """Enroll a student in a course"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user:
        return jsonify({"error": "Invalid token or user not found"}), 401
    
    # Only students can enroll in courses
    if current_user['role'] != 'student':
        return jsonify({"error": "Only students can enroll in courses"}), 403
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        # Get request data
        data = request.json
        if not data or 'course_id' not in data:
            return jsonify({"error": "Course ID is required"}), 400
            
        course_id = data['course_id']
        
        # Convert string to UUID
        course_uuid = uuid.UUID(course_id)
        student_uuid = uuid.UUID(current_user['user_id'])
        
        # Check if course exists
        rows = session.execute(f"SELECT * FROM courses WHERE course_id = {course_uuid}")
        if not rows:
            return jsonify({"error": "Course not found"}), 404
            
        # Check if student is already enrolled
        rows = session.execute(
            """
            SELECT * FROM enrollments 
            WHERE student_id = %s AND course_id = %s
            ALLOW FILTERING
            """,
            (student_uuid, course_uuid)
        )
        
        if rows:
            return jsonify({"error": "Student is already enrolled in this course"}), 400
            
        # Create enrollment
        enrollment_id = uuid.uuid4()
        enrollment_date = datetime.datetime.now()
        status = 'active'
        
        session.execute(
            """
            INSERT INTO enrollments (enrollment_id, student_id, course_id, enrollment_date, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (enrollment_id, student_uuid, course_uuid, enrollment_date, status)
        )
        
        return jsonify({
            "message": "Enrollment successful",
            "enrollment": {
                "enrollment_id": str(enrollment_id),
                "student_id": str(student_uuid),
                "course_id": course_id,
                "enrollment_date": enrollment_date.isoformat(),
                "status": status
            }
        }), 201
    except Exception as e:
        print(f"Error enrolling in course: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error enrolling in course: {str(e)}"}), 500

@app.route('/api/enrollments/student', methods=['GET'])
def get_student_enrollments():
    """Get all courses a student is enrolled in"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user:
        return jsonify({"error": "Invalid token or user not found"}), 401
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        student_uuid = uuid.UUID(current_user['user_id'])
        
        # Get all enrollments for this student
        rows = session.execute(
            """
            SELECT * FROM enrollments 
            WHERE student_id = %s
            ALLOW FILTERING
            """,
            (student_uuid,)
        )
        
        enrollments = []
        for row in rows:
            # Get course details for each enrollment
            course_rows = session.execute(f"SELECT * FROM courses WHERE course_id = {row.course_id}")
            if course_rows:
                course = course_rows[0]
                enrollments.append({
                    'enrollment_id': str(row.enrollment_id),
                    'enrollment_date': row.enrollment_date.isoformat() if row.enrollment_date else None,
                    'status': row.status,
                    'course': {
                        'course_id': str(course.course_id),
                        'title': course.title,
                        'description': course.description,
                        'teacher_name': course.teacher_name
                    }
                })
        
        return jsonify({"enrollments": enrollments}), 200
    except Exception as e:
        print(f"Error getting enrollments: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Error getting enrollments: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5004))
    app.run(host='0.0.0.0', port=port, debug=True)

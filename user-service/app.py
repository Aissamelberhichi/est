from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
import datetime
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
import jwt

# Load environment variables
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Cassandra configuration
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'cassandra')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042'))
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'estdb')
CASSANDRA_USER = os.getenv('CASSANDRA_USER', 'cassandra')
CASSANDRA_PASSWORD = os.getenv('CASSANDRA_PASSWORD', 'cassandra')

# Keycloak configuration
KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080/')
REALM = os.getenv('KEYCLOAK_REALM', 'master')
CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'ent-frontend')

# Initialize Cassandra connection
try:
    auth_provider = PlainTextAuthProvider(username=CASSANDRA_USER, password=CASSANDRA_PASSWORD)
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT, auth_provider=auth_provider)
    session = cluster.connect(CASSANDRA_KEYSPACE)
    print(f"Connected to Cassandra cluster at {CASSANDRA_HOST}:{CASSANDRA_PORT}")
    
    # Create users table if it doesn't exist
    session.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id UUID PRIMARY KEY,
            username TEXT,
            email TEXT,
            full_name TEXT,
            role TEXT,
            created_at TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    print("Users table created/verified")
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
    """Extract user information from token and ensure user exists in database"""
    user_info = decode_token(token)
    if not user_info:
        return None
        
    try:
        # Extract basic user info
        user_id = user_info.get('sub')
        username = user_info.get('preferred_username')
        email = user_info.get('email')
        full_name = user_info.get('name', '')
        
        # Extract roles - this depends on your Keycloak configuration
        realm_access = user_info.get('realm_access', {})
        roles = realm_access.get('roles', [])
        
        # Determine role for our system
        role = 'student'  # Default role
        if 'admin' in roles:
            role = 'admin'
        elif 'teacher' in roles:
            role = 'teacher'
            
        # Check if user exists in our database
        if session:
            rows = session.execute(f"SELECT * FROM users WHERE user_id = {uuid.UUID(user_id)}")
            if not rows:
                # User doesn't exist, create new record
                session.execute(
                    """
                    INSERT INTO users (user_id, username, email, full_name, role, created_at, last_login)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (uuid.UUID(user_id), username, email, full_name, role, datetime.datetime.now(), datetime.datetime.now())
                )
            else:
                # Update last login
                session.execute(
                    """
                    UPDATE users SET last_login = %s WHERE user_id = %s
                    """,
                    (datetime.datetime.now(), uuid.UUID(user_id))
                )
                
        return {
            'user_id': user_id,
            'username': username,
            'email': email,
            'full_name': full_name,
            'role': role
        }
    except Exception as e:
        print(f"Error processing user from token: {e}")
        import traceback
        traceback.print_exc()
        return None

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the API is running"""
    return jsonify({"status": "ok", "message": "User service is running"})

@app.route('/api/users/me', methods=['GET'])
def get_current_user():
    """Get current user profile from token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    user = get_user_from_token(token)
    
    if not user:
        return jsonify({"error": "Invalid token or user not found"}), 401
        
    return jsonify({"user": user}), 200

@app.route('/api/users', methods=['GET'])
def list_users():
    """List all users (admin only)"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user or current_user['role'] != 'admin':
        return jsonify({"error": "Unauthorized. Admin access required"}), 403
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        rows = session.execute("SELECT * FROM users")
        users = []
        for row in rows:
            users.append({
                'user_id': str(row.user_id),
                'username': row.username,
                'email': row.email,
                'full_name': row.full_name,
                'role': row.role,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'last_login': row.last_login.isoformat() if row.last_login else None
            })
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": f"Error fetching users: {str(e)}"}), 500

@app.route('/api/users/role/<role>', methods=['GET'])
def list_users_by_role(role):
    """List users by role (admin or teacher only)"""
    if role not in ['admin', 'teacher', 'student']:
        return jsonify({"error": "Invalid role specified"}), 400
        
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "No valid authorization token provided"}), 401
        
    token = auth_header.split(' ')[1]
    current_user = get_user_from_token(token)
    
    if not current_user or current_user['role'] not in ['admin', 'teacher']:
        return jsonify({"error": "Unauthorized. Admin or teacher access required"}), 403
    
    if not session:
        return jsonify({"error": "Database connection not available"}), 500
    
    try:
        # Use ALLOW FILTERING for role-based queries (not ideal for production with large datasets)
        rows = session.execute(f"SELECT * FROM users WHERE role = '{role}' ALLOW FILTERING")
        users = []
        for row in rows:
            users.append({
                'user_id': str(row.user_id),
                'username': row.username,
                'email': row.email,
                'full_name': row.full_name,
                'role': row.role
            })
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": f"Error fetching users: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=True)

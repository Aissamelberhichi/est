#!/usr/bin/env python3
"""
Script to initialize Cassandra database with the required schema
"""
import time
import os
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider

# Cassandra configuration
CASSANDRA_HOST = os.getenv('CASSANDRA_HOST', 'cassandra')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042'))
CASSANDRA_USER = os.getenv('CASSANDRA_USER', 'cassandra')
CASSANDRA_PASSWORD = os.getenv('CASSANDRA_PASSWORD', 'cassandra')

# Maximum number of connection attempts
MAX_ATTEMPTS = 10
WAIT_SECONDS = 10

def connect_to_cassandra():
    """Attempt to connect to Cassandra with retries"""
    print("Attempting to connect to Cassandra...")
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Setup auth provider
            auth_provider = PlainTextAuthProvider(
                username=CASSANDRA_USER,
                password=CASSANDRA_PASSWORD
            )
            
            # Connect to cluster
            cluster = Cluster(
                [CASSANDRA_HOST],
                port=CASSANDRA_PORT,
                auth_provider=auth_provider
            )
            
            # Get session
            session = cluster.connect()
            print(f"Successfully connected to Cassandra on attempt {attempt}")
            return cluster, session
        except Exception as e:
            print(f"Connection attempt {attempt} failed: {e}")
            if attempt < MAX_ATTEMPTS:
                print(f"Waiting {WAIT_SECONDS} seconds before next attempt...")
                time.sleep(WAIT_SECONDS)
            else:
                print("Maximum connection attempts reached. Exiting.")
                raise

def create_schema(session):
    """Create keyspace and tables"""
    print("Creating keyspace and tables...")
    
    # Create keyspace
    session.execute("""
        CREATE KEYSPACE IF NOT EXISTS estdb 
        WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1}
    """)
    
    # Use keyspace
    session.execute("USE estdb")
    
    # Create courses table
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
    
    print("Schema created successfully")

def main():
    """Main function"""
    try:
        # Connect to Cassandra
        cluster, session = connect_to_cassandra()
        
        # Create schema
        create_schema(session)
        
        # Close connection
        cluster.shutdown()
        print("Initialization completed successfully")
    except Exception as e:
        print(f"Initialization failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()

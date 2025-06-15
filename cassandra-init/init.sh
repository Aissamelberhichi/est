#!/bin/bash

# Remove set -e to prevent script from exiting on first error

echo "Waiting for Cassandra to be ready..."
# Increase timeout and add more verbose output
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  if cqlsh cassandra 9042 -u cassandra -p cassandra -e "describe keyspaces" > /dev/null 2>&1; then
    echo "Cassandra is up - executing CQL"
    break
  fi
  ATTEMPT=$((ATTEMPT+1))
  echo "Cassandra is unavailable - sleeping (attempt $ATTEMPT/$MAX_ATTEMPTS)"
  sleep 10
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
  echo "Failed to connect to Cassandra after $MAX_ATTEMPTS attempts"
  exit 1
fi

# Create keyspace
cqlsh cassandra 9042 -u cassandra -p cassandra -e "
CREATE KEYSPACE IF NOT EXISTS estdb 
WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};
"

# Create tables
cqlsh cassandra 9042 -u cassandra -p cassandra -e "
USE estdb;

CREATE TABLE IF NOT EXISTS courses (
    course_id UUID PRIMARY KEY,
    title TEXT,
    description TEXT,
    upload_date TIMESTAMP,
    teacher_id UUID,
    teacher_name TEXT, 
    file_url TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY,
    username TEXT,
    email TEXT,
    full_name TEXT,
    role TEXT,
    created_at TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id UUID PRIMARY KEY,
    student_id UUID,
    course_id UUID,
    enrollment_date TIMESTAMP,
    status TEXT
);
"

echo "Database initialization completed successfully"

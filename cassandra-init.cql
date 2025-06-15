-- Create keyspace if it doesn't exist
CREATE KEYSPACE IF NOT EXISTS estdb WITH REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1};

-- Use the keyspace
USE estdb;

-- Create courses table
CREATE TABLE IF NOT EXISTS estdb.courses (
    course_id UUID PRIMARY KEY,
    title TEXT,
    description TEXT,
    upload_date TIMESTAMP,
    teacher_id UUID,
    teacher_name TEXT, 
    file_url TEXT
);

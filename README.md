# MinIO File Upload Application

This application allows you to upload and manage files using MinIO as the storage backend. It consists of a React.js frontend and a Python Flask backend.

## Project Structure

```
minio/
├── backend/               # Python Flask backend
│   ├── venv/              # Python virtual environment
│   ├── .env               # Environment variables
│   ├── app.py             # Main Flask application
│   └── requirements.txt   # Python dependencies
└── frontend/              # React.js frontend
    ├── public/            # Static files
    ├── src/               # React source code
    ├── package.json       # NPM dependencies
    └── ...                # Other React files
```

## Prerequisites

- Node.js and npm (for the frontend)
- Python 3.8+ (for the backend)
- MinIO server running (in your case on 192.168.245.130:9000)

## Setup and Running

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Activate the virtual environment:
   - On Windows:
     ```
     .\venv\Scripts\activate
     ```
   - On Linux/Mac:
     ```
     source venv/bin/activate
     ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the Flask application:
   ```
   python app.py
   ```
   The backend will run on http://localhost:5000

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Run the React application:
   ```
   npm start
   ```
   The frontend will run on http://localhost:3000

## Usage

1. Open the frontend application in your browser at http://localhost:3000
2. Use the file upload form to select and upload files to MinIO
3. View the list of uploaded files in the table below
4. Click the "View" button to access the file directly from MinIO

## Configuration

The backend connects to your MinIO server using the configuration in the `.env` file. You can modify these settings if needed:

```
MINIO_ENDPOINT=192.168.245.130
MINIO_PORT=9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=False
FLASK_PORT=5000
```

## Troubleshooting

- If you can't connect to MinIO, make sure your MinIO server is running and accessible
- If the frontend can't connect to the backend, check that the Flask server is running
- Check the browser console and server logs for any error messages

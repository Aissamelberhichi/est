import React, { useState, useEffect } from 'react';
import axios from 'axios';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import { useKeycloak } from './KeycloakProvider';
import CourseList from './components/CourseList';
import UserProfile from './components/UserProfile';

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [fileList, setFileList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [customFileName, setCustomFileName] = useState('');
  const [fileDescription, setFileDescription] = useState('');
  const [activeTab, setActiveTab] = useState('files');
  const [userRole, setUserRole] = useState(null);

  const { keycloak } = useKeycloak();

  // Microservices API URLs
  const UPLOAD_API_URL = 'http://192.168.245.130:5001/api';
  const DOWNLOAD_API_URL = 'http://192.168.245.130:5002/api';
  const USER_API_URL = 'http://192.168.245.130:5003/api';
  const COURSE_API_URL = 'http://192.168.245.130:5004/api';

  // Fetch the list of files and user role on component mount and when keycloak changes
  useEffect(() => {
    if (keycloak?.authenticated) {
      fetchFiles();
      fetchUserRole();
    }
  }, [keycloak?.authenticated]);
  
  // Fetch user role from the user service
  const fetchUserRole = async () => {
    try {
      const response = await axios.get(`${USER_API_URL}/users/me`, {
        headers: { Authorization: `Bearer ${keycloak?.token}` }
      });
      
      if (response.data && response.data.user) {
        setUserRole(response.data.user.role);
      }
    } catch (err) {
      console.error('Error fetching user role:', err);
    }
  };

  // Refresh token periodically
  useEffect(() => {
    if (!keycloak) return;
    const interval = setInterval(() => {
      keycloak.updateToken(60).catch(err => console.error('Token refresh failed', err));
    }, 30000);
    return () => clearInterval(interval);
  }, [keycloak]);

  // Function to fetch files from the backend
  const fetchFiles = async () => {
    try {
      setLoading(true);
      // Get files list from the download service
      const response = await axios.get(`${DOWNLOAD_API_URL}/files`, {
        headers: { Authorization: `Bearer ${keycloak?.token}` }
      });
      setFileList(response.data.files || []);
      setError('');
    } catch (err) {
      console.error('Error fetching files:', err);
      setError('Failed to fetch files. Please check if the backend server is running.');
    } finally {
      setLoading(false);
    }
  };

  // Handle file selection
  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setUploadStatus('');
  };

  // Handle file upload
  const handleUpload = async () => {
    if (!selectedFile) {
      setUploadStatus('Please select a file first');
      return;
    }

    try {
      setLoading(true);
      const formData = new FormData();
      formData.append('file', selectedFile);
      
      // Add custom file name if provided
      if (customFileName.trim()) {
        formData.append('custom_filename', customFileName.trim());
      }
      
      // Add description if provided
      if (fileDescription.trim()) {
        formData.append('description', fileDescription.trim());
      }

      await axios.post(`${UPLOAD_API_URL}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          Authorization: `Bearer ${keycloak?.token}`
        }
      });

      setUploadStatus(`File "${selectedFile.name}" uploaded successfully!`);
      setSelectedFile(null);
      setCustomFileName(''); // Reset custom file name
      setFileDescription(''); // Reset description
      
      // Refresh the file list after upload
      fetchFiles();
    } catch (err) {
      console.error('Error uploading file:', err);
      setUploadStatus(`Error uploading file: ${err.response?.data?.error || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Format file size for display
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="container-fluid mt-3">
      <div className="row mb-4">
        <div className="col-12">
          <nav className="navbar navbar-expand-lg navbar-dark bg-primary rounded">
            <div className="container-fluid">
              <a className="navbar-brand" href="#">ENT Platform</a>
              <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span className="navbar-toggler-icon"></span>
              </button>
              <div className="collapse navbar-collapse" id="navbarNav">
                <ul className="navbar-nav me-auto">
                  <li className="nav-item">
                    <a 
                      className={`nav-link ${activeTab === 'files' ? 'active' : ''}`}
                      href="#"
                      onClick={() => setActiveTab('files')}
                    >
                      Files
                    </a>
                  </li>
                  <li className="nav-item">
                    <a 
                      className={`nav-link ${activeTab === 'courses' ? 'active' : ''}`}
                      href="#"
                      onClick={() => setActiveTab('courses')}
                    >
                      Courses
                    </a>
                  </li>
                  <li className="nav-item">
                    <a 
                      className={`nav-link ${activeTab === 'upload' ? 'active' : ''}`}
                      href="#"
                      onClick={() => setActiveTab('upload')}
                    >
                      Upload Course
                    </a>
                  </li>
                </ul>
                <ul className="navbar-nav">
                  <li className="nav-item">
                    <a 
                      className={`nav-link ${activeTab === 'profile' ? 'active' : ''}`}
                      href="#"
                      onClick={() => setActiveTab('profile')}
                    >
                      Profile
                    </a>
                  </li>
                  <li className="nav-item">
                    <a 
                      className="nav-link"
                      href="#"
                      onClick={() => keycloak.logout()}
                    >
                      Logout
                    </a>
                  </li>
                </ul>
              </div>
            </div>
          </nav>
        </div>
      </div>
      
      {activeTab === 'profile' && <UserProfile />}
      {activeTab === 'courses' && <CourseList />}
      
      {activeTab === 'files' && (
        <div className="row">
          <div className="col-12 text-center mb-4">
            <h2>File Management</h2>
            <p className="text-muted">View and download files from the platform</p>
          </div>
        </div>
      )}
      
      {activeTab === 'upload' && (
        <div className="row">
          <div className="col-12 text-center mb-4">
            <h2>Upload Course Materials</h2>
            <p className="text-muted">Add new course materials to the platform</p>
          </div>
        </div>
      )}

      {activeTab === 'upload' && (
        <div className="row justify-content-center">
          <div className="col-md-8">
            <div className="card">
              <div className="card-body">
                <h5 className="card-title">Upload a Course File</h5>
                
                <div className="mb-3">
                  <label className="form-label">Select File</label>
                  <input 
                    type="file" 
                    className="form-control" 
                    onChange={handleFileChange} 
                  />
                </div>
                
                <div className="mb-3">
                  <label className="form-label">Course Title</label>
                  <input 
                    type="text" 
                    className="form-control" 
                    placeholder="Enter a title for your course"
                    value={customFileName}
                    onChange={(e) => setCustomFileName(e.target.value)}
                    required
                  />
                </div>
                
                <div className="mb-3">
                  <label className="form-label">Course Description</label>
                  <textarea 
                    className="form-control" 
                    placeholder="Enter a description for your course"
                    value={fileDescription}
                    onChange={(e) => setFileDescription(e.target.value)}
                    rows="3"
                    required
                  ></textarea>
                </div>
                
                <button 
                  className="btn btn-primary" 
                  onClick={handleUpload}
                  disabled={!selectedFile || loading || !customFileName.trim() || !fileDescription.trim()}
                >
                  {loading ? 'Uploading...' : 'Upload Course'}
                </button>
                
                {uploadStatus && (
                  <div className={`alert mt-3 ${uploadStatus.includes('Error') ? 'alert-danger' : 'alert-success'}`}>
                    {uploadStatus}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'files' && (
        <div className="row mt-4">
          <div className="col-12">
            <div className="card">
              <div className="card-header bg-primary text-white">
                <h5 className="mb-0">Files in Storage</h5>
              </div>
              <div className="card-body">
                {error && <div className="alert alert-danger">{error}</div>}
                
                {loading && (
                  <div className="text-center">
                    <div className="spinner-border text-primary" role="status">
                      <span className="visually-hidden">Loading...</span>
                    </div>
                    <p className="mt-2">Loading files...</p>
                  </div>
                )}
                
                {!loading && fileList.length === 0 && (
                  <p className="text-center text-muted">No files found. Upload your first file!</p>
                )}
                
                {fileList.length > 0 && (
                  <div className="table-responsive">
                    <table className="table table-striped">
                      <thead>
                        <tr>
                          <th>File Name</th>
                          <th>Description</th>
                          <th>Size</th>
                          <th>Last Modified</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {fileList.map((file) => (
                          <tr key={file.name}>
                            <td>{file.display_name || file.name}</td>
                            <td>{file.description || 'No description'}</td>
                            <td>{formatFileSize(file.size)}</td>
                            <td>{new Date(file.last_modified).toLocaleString()}</td>
                            <td>
                              <div className="btn-group">
                                <a 
                                  href={file.url} 
                                  className="btn btn-sm btn-primary me-1"
                                  target="_blank" 
                                  rel="noopener noreferrer"
                                >
                                  View
                                </a>
                                <a 
                                  href={file.url} 
                                  className="btn btn-sm btn-outline-success" 
                                  download
                                >
                                  Download
                                </a>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                
                <button 
                  className="btn btn-outline-secondary mt-2" 
                  onClick={fetchFiles}
                  disabled={loading}
                >
                  Refresh List
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <footer className="mt-5 text-center text-muted">
        <p>Espace Numérique de Travail (ENT) - École Supérieure de Technologie</p>
      </footer>
    </div>
  );
}

export default App;

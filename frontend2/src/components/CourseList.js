import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useKeycloak } from '../KeycloakProvider';

const CourseList = () => {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { keycloak } = useKeycloak();

  // Course service API URL
  // Try different URLs based on environment
  const COURSE_API_URL = window.location.hostname === 'localhost' 
    ? 'http://localhost:5004/api'
    : 'http://192.168.245.130:5004/api';  // Using the VM IP from your memory

  useEffect(() => {
    if (keycloak?.authenticated) {
      fetchCourses();
    }
  }, [keycloak?.authenticated]);

  const fetchCourses = async () => {
    try {
      setLoading(true);
      console.log('Fetching courses from:', `${COURSE_API_URL}/courses`);
      console.log('Using token:', keycloak?.token ? 'Token exists' : 'No token');
      
      const response = await axios.get(`${COURSE_API_URL}/courses`, {
        headers: { Authorization: `Bearer ${keycloak?.token}` }
      });
      
      console.log('Course API response:', response.data);
      setCourses(response.data.courses || []);
      setError('');
    } catch (err) {
      console.error('Error fetching courses:', err);
      console.error('Error details:', err.response?.data || 'No response data');
      setError('Failed to fetch courses. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  // Format date for display
  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  return (
    <div className="container mt-4">
      <div className="card">
        <div className="card-header bg-primary text-white">
          <h5 className="mb-0">Available Courses</h5>
        </div>
        <div className="card-body">
          {error && <div className="alert alert-danger">{error}</div>}
          
          {loading ? (
            <div className="text-center">
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
              <p className="mt-2">Loading courses...</p>
            </div>
          ) : courses.length === 0 ? (
            <div className="alert alert-info">No courses available.</div>
          ) : (
            <div className="table-responsive">
              <table className="table table-striped table-hover">
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Description</th>
                    <th>Teacher</th>
                    <th>Upload Date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {courses.map(course => (
                    <tr key={course.course_id}>
                      <td>{course.title}</td>
                      <td>{course.description}</td>
                      <td>{course.teacher_name}</td>
                      <td>{formatDate(course.upload_date)}</td>
                      <td>
                        <a 
                          href={course.file_url} 
                          className="btn btn-sm btn-primary me-2"
                          target="_blank" 
                          rel="noopener noreferrer"
                        >
                          Download
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CourseList;

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useKeycloak } from '../KeycloakProvider';

const UserProfile = () => {
  const [userProfile, setUserProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { keycloak } = useKeycloak();

  // User service API URL
  const USER_API_URL = 'http://192.168.1.2:5003/api';

  useEffect(() => {
    if (keycloak?.authenticated) {
      fetchUserProfile();
    }
  }, [keycloak?.authenticated]);

  const fetchUserProfile = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${USER_API_URL}/users/me`, {
        headers: { Authorization: `Bearer ${keycloak?.token}` }
      });
      setUserProfile(response.data.user || null);
      setError('');
    } catch (err) {
      console.error('Error fetching user profile:', err);
      setError('Failed to fetch user profile. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="container mt-4">
        <div className="card">
          <div className="card-body text-center">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <p className="mt-2">Loading user profile...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mt-4">
        <div className="alert alert-danger">{error}</div>
      </div>
    );
  }

  if (!userProfile) {
    return (
      <div className="container mt-4">
        <div className="alert alert-warning">User profile not found.</div>
      </div>
    );
  }

  return (
    <div className="container mt-4">
      <div className="card">
        <div className="card-header bg-primary text-white">
          <h5 className="mb-0">User Profile</h5>
        </div>
        <div className="card-body">
          <div className="row">
            <div className="col-md-4 text-center mb-3">
              <div className="avatar-placeholder bg-light rounded-circle mx-auto d-flex align-items-center justify-content-center" style={{ width: '150px', height: '150px' }}>
                <span className="display-4 text-muted">{userProfile.full_name ? userProfile.full_name.charAt(0).toUpperCase() : '?'}</span>
              </div>
            </div>
            <div className="col-md-8">
              <table className="table">
                <tbody>
                  <tr>
                    <th>Full Name:</th>
                    <td>{userProfile.full_name || 'Not provided'}</td>
                  </tr>
                  <tr>
                    <th>Username:</th>
                    <td>{userProfile.username}</td>
                  </tr>
                  <tr>
                    <th>Email:</th>
                    <td>{userProfile.email || 'Not provided'}</td>
                  </tr>
                  <tr>
                    <th>Role:</th>
                    <td>
                      <span className={`badge ${
                        userProfile.role === 'admin' ? 'bg-danger' : 
                        userProfile.role === 'teacher' ? 'bg-success' : 
                        'bg-info'
                      }`}>
                        {userProfile.role.charAt(0).toUpperCase() + userProfile.role.slice(1)}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserProfile;

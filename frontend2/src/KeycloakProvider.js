import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);
export const useKeycloak = () => useContext(AuthContext);

// Configuration Keycloak
// Use the direct IP address without relying on hostname detection
const KEYCLOAK_URL = 'http://192.168.245.130:8080/';
const REALM = 'master';
const CLIENT_ID = 'ent-frontend';

export default function KeycloakProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Vérifier l'existence d'un token au chargement initial
  useEffect(() => {
    const storedToken = localStorage.getItem('token');
    const storedRefreshToken = localStorage.getItem('refresh_token');
    
    if (storedToken) {
      setToken(storedToken);
      setIsAuthenticated(true);
      
      // Vérifier la validité du token et le rafraîchir si nécessaire
      const checkTokenValidity = async () => {
        try {
          // Décodage simple du JWT pour vérifier l'expiration
          const tokenData = JSON.parse(atob(storedToken.split('.')[1]));
          const expiryTime = tokenData.exp * 1000; // Convertir en millisecondes
          const currentTime = new Date().getTime();
          
          // Si le token expire dans moins de 5 minutes, essayer de le rafraîchir
          if (expiryTime - currentTime < 300000) {
            const success = await refreshToken(storedRefreshToken);
            if (!success) {
              logout();
            }
          }
        } catch (err) {
          console.error('Error checking token validity:', err);
          logout(); // Token invalide, déconnexion
        }
      };
      
      checkTokenValidity();
    }
  }, []);
  
  // Fonction pour rafraîchir le token
  const refreshToken = async (refreshTokenValue) => {
    try {
      if (!refreshTokenValue) return false;
      
      const response = await axios.post(
        `${KEYCLOAK_URL}realms/${REALM}/protocol/openid-connect/token`,
        new URLSearchParams({
          'client_id': CLIENT_ID,
          'grant_type': 'refresh_token',
          'refresh_token': refreshTokenValue
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }
      );

      const { access_token, refresh_token } = response.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      setToken(access_token);
      return true;
    } catch (err) {
      console.error('Token refresh failed:', err);
      return false;
    }
  };

  // Fonction de login utilisant Direct Grant Flow
  const login = async () => {
    setLoading(true);
    setError('');
    
    try {
      console.log('Attempting login to Keycloak at:', `${KEYCLOAK_URL}realms/${REALM}/protocol/openid-connect/token`);
      console.log('Using client ID:', CLIENT_ID);
      console.log('Username:', username);
      
      const response = await axios.post(
        `${KEYCLOAK_URL}realms/${REALM}/protocol/openid-connect/token`,
        new URLSearchParams({
          'client_id': CLIENT_ID,
          'grant_type': 'password',
          'username': username,
          'password': password
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }
      );

      console.log('Login successful, received token');
      const { access_token, refresh_token } = response.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      setToken(access_token);
      setIsAuthenticated(true);
    } catch (err) {
      console.error('Login error:', err);
      console.error('Error details:', err.response?.data || 'No response data');
      setError('Échec de connexion. Vérifiez vos identifiants.');
    } finally {
      setLoading(false);
    }
  };

  // Fonction de déconnexion
  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    setToken(null);
    setIsAuthenticated(false);
  };

  // Simuler l'objet keycloak pour compatibilité
  const keycloak = {
    token,
    refreshToken: localStorage.getItem('refresh_token'),
    authenticated: isAuthenticated,
    login,
    logout,
    updateToken: async (minValidity) => {
      // Utiliser la fonction refreshToken définie plus haut
      try {
        const refreshTokenValue = localStorage.getItem('refresh_token');
        if (!refreshTokenValue) return false;
        
        const response = await axios.post(
          `${KEYCLOAK_URL}realms/${REALM}/protocol/openid-connect/token`,
          new URLSearchParams({
            'client_id': CLIENT_ID,
            'grant_type': 'refresh_token',
            'refresh_token': refreshTokenValue
          }),
          {
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            }
          }
        );

        const { access_token, refresh_token } = response.data;
        localStorage.setItem('token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        setToken(access_token);
        return true;
      } catch (err) {
        console.error('Token refresh failed:', err);
        logout(); // Déconnexion en cas d'échec
        return false;
      }
    }
  };

  // Formulaire de connexion si non authentifié
  if (!isAuthenticated) {
    return (
      <div className="container mt-5">
        <div className="row justify-content-center">
          <div className="col-md-6">
            <div className="card">
              <div className="card-header bg-primary text-white">
                <h4 className="mb-0">Connexion</h4>
              </div>
              <div className="card-body">
                {error && <div className="alert alert-danger">{error}</div>}
                <form onSubmit={(e) => { e.preventDefault(); login(); }}>
                  <div className="mb-3">
                    <label htmlFor="username" className="form-label">Nom d'utilisateur</label>
                    <input 
                      type="text" 
                      className="form-control" 
                      id="username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                    />
                  </div>
                  <div className="mb-3">
                    <label htmlFor="password" className="form-label">Mot de passe</label>
                    <input 
                      type="password" 
                      className="form-control" 
                      id="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                  <button 
                    type="submit" 
                    className="btn btn-primary w-100"
                    disabled={loading}
                  >
                    {loading ? 'Connexion en cours...' : 'Se connecter'}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <AuthContext.Provider value={{ keycloak }}>
      {children}
    </AuthContext.Provider>
  );
}

// src/context/UserContext.jsx
import React, { createContext, useContext, useState, useEffect } from "react";

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // 1. Add loading state

  // Define your API URL here just like in AuthModal
  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  useEffect(() => {
    const checkSession = async () => {
      // We look for the token you saved in AuthModal
      const token = localStorage.getItem("auth_token");
      
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        // 2. The Re-authentication Logic
        // We try to hit the same /auth/me endpoint you used in login
        const res = await fetch(`${API_URL}/auth/me`, {
          headers: { 
            "Authorization": `Bearer ${token}` 
          },
        });

        if (res.ok) {
          // 3. Success: Token is still alive!
          const userData = await res.json();
          // We update the user state with the fresh data from the server
          setUser({ ...userData, token: token }); 
        } else {
          localStorage.removeItem("user");
          // 4. Failure: Token is expired or invalid
          console.warn("Session expired. Logging out.");
          logout(); 
        }
      } catch (error) {
        console.error("Network error during auth check", error);
        // Optional: decide if network error means logout, usually safer to keep user logged out
        logout();
      } finally {
        setLoading(false);
      }
    };

    checkSession();
  }, []);

  const login = (userData) => {
    // Save the user object state
    setUser(userData);
    
    // AuthModal handles saving the tokens to localStorage, 
    // but to be safe/consistent we can ensure 'user' is saved if you use it elsewhere
    localStorage.setItem("user", JSON.stringify(userData));
  };

  const logout = () => {
    // Clear all auth items
    localStorage.removeItem("user");
    localStorage.removeItem("auth_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
  };

  // 5. Block rendering until we know if the user is logged in
  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', marginTop: '50px' }}>Loading session...</div>;
  }

  return (
    <UserContext.Provider value={{ user, login, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export const useUser = () => useContext(UserContext);
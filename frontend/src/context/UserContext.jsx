// src/context/UserContext.jsx
import React, { createContext, useContext, useState, useEffect } from "react";

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);

  // 1. Initialize: Check local storage on mount to restore user session
  useEffect(() => {
    const savedUser = localStorage.getItem("user");
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch (error) {
        console.error("Failed to parse user data", error);
        localStorage.removeItem("user");
      }
    }
  }, []);

  const login = (userData) => {
    // 2. Simple Login: Update state and save to storage
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
  };

  const logout = () => {
    // 3. Simple Logout: Clear state and storage
    setUser(null);
    localStorage.removeItem("user");
    // (Optional) Clean up leftover tokens if you want to be thorough
    localStorage.removeItem("auth_token"); 
    localStorage.removeItem("refresh_token");
  };

  return (
    <UserContext.Provider value={{ user, login, logout }}>
      {children}
    </UserContext.Provider>
  );
}

export const useUser = () => useContext(UserContext);
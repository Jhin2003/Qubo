// src/context/UserContext.jsx
import React, { createContext, useContext, useState, useEffect } from "react";

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);

  // Optional: load user from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem("auth_token");
    if (token) {
      // If you want, you can decode JWT to get user info
      setUser({ token }); // simple version
    }
  }, []);

  const login = (userData) => {
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");

    setUser(null);
  };

  return (
    <UserContext.Provider value={{ user, login, logout }}>
      {children}
    </UserContext.Provider>
  );
}

// Custom hook for easy access
export const useUser = () => useContext(UserContext);

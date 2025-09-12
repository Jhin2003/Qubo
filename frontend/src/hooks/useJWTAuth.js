import { useState, useEffect } from "react";

export const useJWTAuth = () => {
  const [token, setToken] = useState(localStorage.getItem("auth_token"));
 

  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token");
    if (storedToken) {
      setToken(storedToken);
    }
  }, []);

  // Function to handle user logout
  const logOut = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("refresh_token"); // If refresh_token exists
    setToken(null); // Clear the token in state
    // Optionally redirect to login screen

  };

  return { token, logOut };
};

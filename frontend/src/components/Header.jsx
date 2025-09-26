import React, { useEffect, useState } from "react";
import AuthModal from "./modals/AuthModal";
import { useFetch } from "../hooks/fetchWithAuth"; // Import useFetch hook
import "./Header.scss";

export default function Header() {
  const [open, setOpen] = useState(false); // Modal open state
  const [user, setUser] = useState(null); // User data state
  const [token, setToken] = useState(localStorage.getItem("auth_token")); // Auth token state
  const [loading, setLoading] = useState(true); // Loading state
  const { fetchWithAuth } = useFetch(); // Initialize the fetchWithAuth function
  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  const fetchUser = async () => {
    if (token) {
      try {
        const response = await fetchWithAuth(`${API_URL}/auth/me`);
        if (response.ok) {
          const data = await response.json();
          setUser(data);
        } else {
          setUser(null); // Handle case where no user is found
        }
      } catch (error) {
        console.log("Error fetching user data", error);
        setUser(null); // In case of error, clear user data
      }
    } else {
      setUser(null); // If no token, no user data
    }
    setLoading(false); // Stop loading once user data is fetched (or if no token)
  };

  useEffect(() => {
    fetchUser();
  }, []); // Trigger fetch when token changes

  // Handle logout
  const handleLogout = () => {
    // Remove token and reset user state
    localStorage.removeItem("auth_token");
    setToken(null); // Ensure the token state is cleared
    setUser(null); // Clear user data
    setOpen(true); // Open the login modal after logout
  };

  return (
    <header className="header">
      <h1 className="brand-name">Qubo</h1>

      {loading ? (
        // Show a loading indicator until the user data is fetched
        <div>Loading...</div>
      ) : user ? (
        // If the user is logged in, show their email and a logout button
        <div className="user-info">
          <span className="username">{user.username}</span>
          <button className="logout-button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      ) : (
        // If not logged in, show the login button
        <button className="login-button" onClick={() => setOpen(true)}>
          Login / Sign Up
        </button>
      )}

      <AuthModal
        isOpen={open}
        onClose={() => setOpen(false)} // Close modal on cancel
        onSuccess={() => {
          // After successful login, fetch user info again
          const token = localStorage.getItem("auth_token");
          setToken(token); // This will trigger useEffect to re-fetch user data
        }}
      />
    </header>
  );
}

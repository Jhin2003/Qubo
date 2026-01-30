// src/components/Header.jsx
import React, { useState, useRef, useEffect } from "react";
import "./Header.scss";
import { useUser } from "../context/UserContext";
import AuthModal from "./modals/AuthModal";
import logo from '../assets/Group 10.svg';
import { FaUserCircle } from "react-icons/fa";
import { FaRegUserCircle } from "react-icons/fa"

export default function Header() {
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false); // State for dropdown
  const { user, logout } = useUser();
  const menuRef = useRef(null); // Ref to detect clicks outside

  const handleLogout = () => {
    logout();
    setMenuOpen(false);
  };

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuRef]);

  // Helper to get initials
  const getInitials = (name) => {
    return name ? name.charAt(0).toUpperCase() : "U";
  };

  return (
    <header className="header">
      <h1 className="brand-name">
        <img src={logo} alt="Qubo" width="60" height="40" />
      </h1>

      {user ? (
        <div className="user-menu-container" ref={menuRef}>
       
          <div 
            className="profile-trigger" 
            onClick={() => setMenuOpen(!menuOpen)}
          >
          
                 <FaRegUserCircle className="profile-logo" />
         
          </div>

          {/* The Dropdown Menu */}
          {menuOpen && (
            <div className="dropdown-menu">
              <div className="dropdown-header">
                <span className="user-name">{user?.username || "User"}</span>
                <span className="user-email">{user?.email}</span>
              </div>
              <div className="dropdown-divider"></div>
              <button className="dropdown-item logout" onClick={handleLogout}>
                Logout
              </button>
            </div>
          )}
        </div>
      ) : (
        <button className="login-button" onClick={() => setAuthModalOpen(true)}>
          Sign in
        </button>
      )}

      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={() => setAuthModalOpen(false)}
      />
    </header>
  );
}
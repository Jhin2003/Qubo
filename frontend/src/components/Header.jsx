// src/components/Header.jsx
import React, { useState } from "react";
import "./Header.scss";
import { useUser } from "../context/UserContext";
import AuthModal from "./modals/AuthModal"; // keep if you want a popup

export default function Header() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useUser(); // ✅ call the hook

  const handleLogout = () => {
    logout();
  };

  return (
    <header className="header">
      <h1 className="brand-name">Qubo</h1>

      {/* ✅ wrap conditional in braces */}
      {user ? (
        <div className="user-info">
          <span className="username">{user?.username || user?.email}</span>
          <button className="logout-button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      ) : (
        <button className="login-button" onClick={() => setOpen(true)}>
          Login / Sign Up
        </button>
      )}

      {/* Optional modal login */}
      <AuthModal
        isOpen={open}
        onClose={() => setOpen(false)}
        onSuccess={() => setOpen(false)} // context should hydrate user
      />
    </header>
  );
}

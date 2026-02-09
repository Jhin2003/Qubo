// src/components/AuthModal.jsx
import React, { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import "./AuthModal.scss"; // reuse your styles

import { useUser } from "../../context/UserContext";

export default function AuthModal({ isOpen, onClose, onSuccess }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [username, setUsername] = useState(""); // use email consistently with backend
  const [email, setEmail] = useState(""); // use email consistently with backend
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState(""); // for signup
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useRef(null);

  // Inside AuthModal component
  // Inside AuthModal component
  const { login } = useUser();

  const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

  // Close on ESC
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  // Focus first input
  useEffect(() => {
    if (isOpen && dialogRef.current)
      dialogRef.current.querySelector("input")?.focus();
  }, [isOpen, mode]);

  const handleBackdropClick = (e) => {
    if (e.target.getAttribute("data-backdrop") === "true") onClose();
  };

  const switchMode = () => {
    setMode((m) => (m === "login" ? "signup" : "login"));
    setError("");
    setPassword("");
    setConfirm("");
  };

 
const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      // --- SIGNUP FLOW ---
      if (mode === "signup") {
        if (password !== confirm) throw new Error("Passwords do not match.");
        
        const res = await fetch(`${API_URL}/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, email, password }),
        });
        
        if (!res.ok) throw new Error((await res.text()) || "Sign up failed.");
        
        // Optional: Automatically switch to login mode after success
        // setMode('login'); 
        // setError("Account created! Please log in.");
        
        onClose(); 
        return;
      }

      // --- LOGIN FLOW (Updated) ---
      // 1. Change endpoint to "/login"
      const res = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password }),
      });

      if (!res.ok) {
        throw new Error((await res.text()) || "Invalid credentials.");
      }

      // 2. The data is now the User object, not a token
      const user = await res.json();



      // 5. Update Context
      login(user); 
      onClose();

    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };
  

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div
      className="modal-backdrop"
      data-backdrop="true"
      onMouseDown={handleBackdropClick}
      aria-hidden="false"
    >
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        ref={dialogRef}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button
          className="modal__close"
          aria-label="Close dialog"
          onClick={onClose}
        >
          ×
        </button>

        <h2 id="auth_logo" className="modal__title">
          Qubo
        </h2>

        <h2 id="auth_title" className="modal__title">
          {mode === "login" ? "Login" : "Create an account"}
        </h2>

        <form className="modal__form" onSubmit={handleSubmit}>
          <label className="modal__label">
            Username
            <input
              type="text"
              autoComplete="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="modal__input"
              disabled={submitting}
            />
          </label>

          <label className="modal__label">
            Email
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="modal__input"
              disabled={submitting}
            />
          </label>

          <label className="modal__label">
            Password
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="modal__input"
              disabled={submitting}
              minLength={8}
            />
          </label>

          {mode === "signup" && (
            <label className="modal__label">
              Confirm Password
              <input
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                className="modal__input"
                disabled={submitting}
                minLength={8}
              />
            </label>
          )}

          {error ? <p className="modal__error">{error}</p> : null}

          <button className="modal__submit" type="submit" disabled={submitting}>
            {submitting
              ? mode === "login"
                ? "Logging in..."
                : "Creating account..."
              : mode === "login"
              ? "Login"
              : "Sign Up"}
          </button>
        </form>

        <p className="modal__hint" style={{ marginTop: 10, fontSize: ".9rem" }}>
          {mode === "login" ? (
            <>
              Don’t have an account?{" "}
              <button type="button" onClick={switchMode} className="linklike">
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={switchMode} className="linklike">
                Log in
              </button>
            </>
          )}
        </p>
      </div>
    </div>,
    document.body
  );
}

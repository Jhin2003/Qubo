// src/components/AuthModal.jsx
import React, { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import "./AuthModal.scss"; // reuse your styles

export default function AuthModal({ isOpen, onClose, onSuccess }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");    // use email consistently with backend
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState(""); // for signup
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useRef(null);

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
    if (isOpen && dialogRef.current) dialogRef.current.querySelector("input")?.focus();
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
      if (mode === "signup") {
        if (password !== confirm) throw new Error("Passwords do not match.");
        // Register
        const res = await fetch(`${API_URL}/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!res.ok) throw new Error((await res.text()) || "Sign up failed.");
        // Optional: auto-login after signup
        const loginRes = await fetch(`${API_URL}/token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        if (!loginRes.ok) throw new Error("Account created, but auto-login failed.");
        const data = await loginRes.json();
        localStorage.setItem("auth_token", data.access_token);
        if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
        onSuccess?.({ mode, ...data });
        onClose();
        return;
      }

      // Login
      const res = await fetch(`${API_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error((await res.text()) || "Invalid credentials.");
      const data = await res.json();
      localStorage.setItem("auth_token", data.access_token);
      if (data.refresh_token) localStorage.setItem("refresh_token", data.refresh_token);
      onSuccess?.({ mode, ...data });
      onClose();
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="modal-backdrop" data-backdrop="true" onMouseDown={handleBackdropClick} aria-hidden="false">
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        ref={dialogRef}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button className="modal__close" aria-label="Close dialog" onClick={onClose}>×</button>

        <h2 id="auth-title" className="modal__title">
          {mode === "login" ? "Login" : "Create an account"}
        </h2>

        <form className="modal__form" onSubmit={handleSubmit}>
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
              autoComplete={mode === "login" ? "current-password" : "new-password"}
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
            {submitting ? (mode === "login" ? "Logging in..." : "Creating account...") : (mode === "login" ? "Login" : "Sign Up")}
          </button>
        </form>

        <p className="modal__hint" style={{ marginTop: 10, fontSize: ".9rem" }}>
          {mode === "login" ? (
            <>Don’t have an account?{" "}
              <button type="button" onClick={switchMode} className="linklike">Sign up</button>
            </>
          ) : (
            <>Already have an account?{" "}
              <button type="button" onClick={switchMode} className="linklike">Log in</button>
            </>
          )}
        </p>
      </div>
    </div>,
    document.body
  );
}

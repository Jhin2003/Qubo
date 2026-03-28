// src/components/AuthModal.jsx
import React, { useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { createClient } from "@supabase/supabase-js";
import "./AuthModal.scss"; 


// 1. Initialize Supabase OUTSIDE the component
const supabaseUrl = "https://otdgrrdockkotvknavbs.supabase.co";
const supabaseAnonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im90ZGdycmRvY2trb3R2a25hdmJzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIxNzEyNjYsImV4cCI6MjA4Nzc0NzI2Nn0.WOSyyUYaRR-cLSDR4ugAmsksOsxV9l_5O6PsJ3bQHZ4";
export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// src/config.js


export default function AuthModal({ isOpen, onClose, onSuccess }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [username, setUsername] = useState(""); 
  const [email, setEmail] = useState(""); 
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState(""); // for signup
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const dialogRef = useRef(null);

 

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
      if (mode === "signup") {
        if (password !== confirm) throw new Error("Passwords do not match.");
        
        // 2. Supabase Sign Up
        const { data, error: signUpError } = await supabase.auth.signUp({
          email,
          password,
          options: {
            data: {
              username, // Store username in Supabase user metadata
            },
          },
        });

        if (signUpError) throw signUpError;

        // If email confirmation is enabled in Supabase, session will be null here.
        if (data.session) {
          onClose();
        } else {
          // Handle the case where email verification is required
          alert("Account created! Please check your email to verify your account.");
          switchMode(); // Switch to login so they can log in after verifying
        }
        return;
      }

      // 3. Supabase Login
      const { data, error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (signInError) throw signInError;

      // Optional: Call onSuccess if provided
      if (onSuccess) onSuccess();

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
          
          {/* Only show Username field during Signup */}
          {mode === "signup" && (
            <label className="modal__label">
              Username
              <input
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="modal__input"
                disabled={submitting}
              />
            </label>
          )}

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
              minLength={6} // Supabase default min length is usually 6
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
                minLength={6}
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
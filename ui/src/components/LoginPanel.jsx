// src/components/LoginPanel.jsx
import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";

export default function LoginPanel() {
  const { login, register, authError, loading, user } = useAuth();
  const [mode, setMode] = useState("login"); // 'login' or 'register'
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (loading) {
    return (
      <div className="login-panel">
        <div className="login-card">
          <p>Checking session…</p>
        </div>
      </div>
    );
  }

  if (user) {
    // If user already logged in, nothing to show here (parent decides layout).
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password, displayName);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-panel">
      <div className="login-card">
        <h2>{mode === "login" ? "Login to Tamor" : "Register"}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <label>Username</label>
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          {mode === "register" && (
            <div className="form-row">
              <label>Display name</label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="What should Tamor call you?"
              />
            </div>
          )}

          <div className="form-row">
            <label>Password</label>
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {authError && <p className="error-text">{authError}</p>}

          <button type="submit" disabled={submitting}>
            {submitting
              ? "Please wait…"
              : mode === "login"
              ? "Login"
              : "Create account"}
          </button>
        </form>

        <div className="login-toggle">
          {mode === "login" ? (
            <p>
              Need an account?{" "}
              <button type="button" onClick={() => setMode("register")}>
                Register
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{" "}
              <button type="button" onClick={() => setMode("login")}>
                Login
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

import React, { createContext, useContext, useEffect, useState } from "react";
import { apiFetch } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);          // current user
  const [users, setUsers] = useState([]);          // all users (for dropdown)
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // ---------------------------------------------------------------------------
  // Load current user AND load user list
  // ---------------------------------------------------------------------------
  useEffect(() => {
    let isMounted = true;

    (async () => {
      try {
        // 1. Load /me
        const data = await apiFetch("/me");
        if (!isMounted) return;

        // Support both {id...} and { user: { ... } }
        const u = data?.user || data;

        if (u && u.id) {
          setUser({
            id: u.id,
            username: u.username,
            display_name: u.display_name,
          });
        } else {
          setUser(null);
        }

        // 2. Load /users list
        try {
          const resp = await apiFetch("/users");
          if (!isMounted) return;

          const list = resp.users || resp;
          if (Array.isArray(list)) {
            setUsers(list);
          } else {
            setUsers([]);
          }
        } catch (err) {
          console.error("Failed to load users:", err);
          if (isMounted) setUsers([]);
        }
      } catch (err) {
        console.error("Error loading /me:", err);
        if (isMounted) setUser(null);
      } finally {
        if (isMounted) setLoading(false);
      }
    })();

    return () => (isMounted = false);
  }, []);

  // ---------------------------------------------------------------------------
  // Login logic (password ignored — home trusted setup)
  // ---------------------------------------------------------------------------
  const login = async (username, password = "") => {
    try {
      const data = await apiFetch("/login", {
        method: "POST",
        body: { username, password },
      });

      const u = data?.user || data;

      setUser({
        id: u.id,
        username: u.username,
        display_name: u.display_name,
      });

      return true;
    } catch (err) {
      console.error("Login failed:", err);
      setAuthError("Login failed");
      return false;
    }
  };

  // ---------------------------------------------------------------------------
  // Register new user
  // ---------------------------------------------------------------------------
  const register = async (username, password, displayName) => {
    setAuthError(null);
    try {
      const data = await apiFetch("/register", {
        method: "POST",
        body: { username, password, display_name: displayName },
      });

      const u = data?.user || data;

      setUser({
        id: u.id,
        username: u.username,
        display_name: u.display_name,
      });

      return true;
    } catch (err) {
      console.error("Register error:", err);
      setAuthError("Registration failed");
      return false;
    }
  };

  // ---------------------------------------------------------------------------
  // Logout
  // ---------------------------------------------------------------------------
  const logout = async () => {
    try {
      await apiFetch("/logout", { method: "POST" });
    } catch (err) {
      console.error("Logout error:", err);
    }
    setUser(null);
  };

  // Values provided to the whole app
  const value = {
    user,
    users,
    loading,
    authError,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext);
}


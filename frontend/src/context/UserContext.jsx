// src/context/UserContext.jsx
import React, { createContext, useContext, useState, useEffect } from "react";
// It is best practice to export your supabase client from a dedicated file (e.g., src/lib/supabase.js) 
// to avoid circular dependencies, but you can import it from wherever you initialized it.
import { supabase } from "../components/modals/AuthModal"; 

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // Optional: helpful to prevent UI flashing

  useEffect(() => {
    // 1. Check for an active session when the app loads
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    // 2. Listen for any auth changes (login, logout, token refresh)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        setUser(session?.user ?? null);
      }
    );

    // Cleanup the listener when the component unmounts
    return () => subscription.unsubscribe();
  }, []);

  // 3. Logout now talks directly to Supabase
  const logout = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) console.error("Error logging out:", error.message);
    // user state automatically goes to null because of onAuthStateChange
  };

  return (
    <UserContext.Provider value={{ user, logout, loading }}>
      {!loading && children} 
    </UserContext.Provider>
  );
}

export const useUser = () => useContext(UserContext);
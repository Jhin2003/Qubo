// src/hooks/fetchWithAuth.js (or wherever this is located)
import { useUser } from "../context/UserContext";
import { supabase } from "../components/modals/AuthModal"; // Make sure this path points to where you export 'supabase'

export const useFetch = () => {
  // We grab logout from your new UserContext so the UI updates if a 401 happens
  const { logout } = useUser(); 

  const fetchWithAuth = async (url, options = {}) => {
    // 1. Ask Supabase for the current session right before the request
    // This ensures you ALWAYS have the freshest token, even if it just auto-refreshed in the background!
    const { data: { session } } = await supabase.auth.getSession();

    // Default headers object
    const headers = {
      ...options.headers,
    };

    // 2. If token is available, add the Authorization header
    if (session?.access_token) {
      headers["Authorization"] = `Bearer ${session.access_token}`;
    }

    try {
      const response = await fetch(url, { ...options, headers });

      // 3. If the backend says the token is invalid/expired, log them out
      if (response.status === 401) {
        console.warn("Token rejected by backend. Logging out...");
        logout(); 
        return null;
      }

      return response;
    } catch (error) {
      console.error("Request failed:", error);
      return null;
    }
  };

  return { fetchWithAuth };
};
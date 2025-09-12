import { useJWTAuth } from "./useJWTAuth";

export const useFetch = () => {
  const { token, logOut } = useJWTAuth(); // We no longer need refreshAuthToken

  const fetchWithAuth = async (url, options = {}) => {
    const headers = {
      ...options.headers,
      "Authorization": `Bearer ${token}`,
    };

    try {
      const response = await fetch(url, { ...options, headers });

      // If token is expired or invalid, log the user out
      if (response.status === 401) {
        logOut();
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

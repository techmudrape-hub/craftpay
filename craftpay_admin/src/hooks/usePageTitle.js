import { useEffect } from 'react';

/**
 * Custom hook to set page title dynamically
 * @param {string} title - The page title (e.g., "Dashboard", "Login")
 * @param {string} suffix - Optional suffix (defaults to "OrchPay Admin")
 */
export const usePageTitle = (title, suffix = 'CraftPay Admin') => {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = title ? `${title} - ${suffix}` : suffix;

    // Cleanup: restore previous title when component unmounts
    return () => {
      document.title = previousTitle;
    };
  }, [title, suffix]);
};

export default usePageTitle;

import React from 'react';
import { Toaster } from 'react-hot-toast';

// This component doesn't render anything visible on its own,
// it just sets up the global toast container with your custom styles.
const ToastConfig = () => {
  return (
    <Toaster
      position="top-right"
      reverseOrder={false}
      gutter={10}
      toastOptions={{
        // Default duration
        duration: 4000,
        
        // Base styles for the glass effect
        style: {
          background: 'rgba(28, 31, 36, 0.85)', // Matches your --panel variable
          color: '#e9ecf1', // Matches your text color
          border: '1px solid rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          borderRadius: '12px',
          fontSize: '14px',
          fontWeight: '500',
          padding: '12px 16px',
        },

        // Customizing the SUCCESS state
        success: {
          duration: 3000,
          iconTheme: {
            primary: '#5BB5AE', // Your Brand Teal
            secondary: '#fff',
          },
          style: {
            borderLeft: '4px solid #5BB5AE', // Accent bar on the left
          },
        },

        // Customizing the ERROR state
        error: {
          duration: 5000,
          iconTheme: {
            primary: '#ef4444', // Red
            secondary: '#fff',
          },
          style: {
            borderLeft: '4px solid #ef4444',
          },
        },

        // Customizing the LOADING state
        loading: {
          style: {
            borderLeft: '4px solid #ced4da',
          },
        },
      }}
    />
  );
};

export default ToastConfig;
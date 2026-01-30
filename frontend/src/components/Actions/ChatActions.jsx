// src/components/ChatActions/ChatActions.jsx
import React, { useState, useRef, useEffect } from "react";
// 1. Import the icons
import { FiPlus, FiZap, FiCrosshair, FiMessageSquare, FiSend, FiSquare } from "react-icons/fi";
import "./ChatActions.scss";

export default function ChatActions({ 
  loading, 
 
  onCancel, 
  onSend, 
  onNewChat, 
  mode, 
  setMode 
}) {
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="chat-actions" ref={menuRef}>
      {/* THE MENU POPUP */}
      {showMenu && (
        <div className="actions-menu">
          <button className="menu-item" onClick={() => {
            onNewChat(); 
            setShowMenu(false);
          }}>
            {/* Wrapped in span to keep your existing SCSS alignment */}
            <span><FiMessageSquare /></span> 
            New Chat
          </button>
          
          <div className="menu-divider" />
          
          <button 
            className={`menu-item ${mode === 'fast' ? 'active' : ''}`} 
            onClick={() => { setMode("fast"); setShowMenu(false); }}
          >
            <span><FiZap /></span> 
            Fast Mode
          </button>
          
          <button 
            className={`menu-item ${mode === 'precise' ? 'active' : ''}`} 
            onClick={() => { setMode("precise"); setShowMenu(false); }}
          >
            <span><FiCrosshair /></span> 
            Precise Mode
          </button>
        </div>
      )}

      {/* THE TRIGGER BUTTON (+) */}
      <button 
        className={`action-trigger-btn ${showMenu ? 'open' : ''}`}
        onClick={() => setShowMenu(!showMenu)}
        title="Chat Options"
      >
        <FiPlus size={20} />
      </button>

      {/* THE SEND/STOP BUTTON */}
      {/* I restored the input check so the Send button appears when typing */}
      { loading && (
        <button
          onClick={loading ? onCancel : onSend}
          className={loading ? "stop-btn" : "send-btn"}
        >
          {loading ? (
            // Stop Icon (filled square)
            <FiSquare fill="currentColor" size={14} /> 
          ) : (
            // Send Icon
            <FiSend size={18} /> 
          )}
        </button>
      )}
    </div>
  );
}
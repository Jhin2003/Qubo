import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom"; // Use useNavigate for navigation
import Header from "./Header";
import "./chatbot.scss";

export default function Chatbot() {
  const [messages, setMessages] = useState([]); // Chat messages state
  const [input, setInput] = useState(""); // User input state
  const [loading, setLoading] = useState(false); // Loading state

  const navigate = useNavigate(); // Initialize useNavigate hook for navigation

  // Persist messages in localStorage
  useEffect(() => {
    const savedMessages = JSON.parse(localStorage.getItem("chatMessages"));
    if (savedMessages) {
      console.log("Loaded messages from localStorage:", savedMessages);
      setMessages(savedMessages); // Load saved messages from localStorage
    } else {
      console.log("No saved messages in localStorage");
    }
  }, []); // Only run once when the component mounts

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      console.log("Saving messages to localStorage:", messages);
      localStorage.setItem("chatMessages", JSON.stringify(messages)); // Save messages to localStorage
    }
  }, [messages]); // Save to localStorage every time messages are updated

  // Handle sending message
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    setLoading(true);
    setMessages((prev) => [...prev, { sender: "user", text: input }]);

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([
          ...messages.map((msg) => ({ sender: msg.sender, text: msg.text })),
          { sender: "user", text: input },
        ]),
      });

      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: data.response, sources: data.sources },
      ]);
      setInput("");
    } catch (error) {
      console.error("Error communicating with the backend:", error);
    } finally {
      setLoading(false);
    }
  };

  // Handle click on a source to navigate to the PDF viewer
  const handleSourceClick = (fileName, page) => {
    navigate(`/view-pdf?file=${fileName}&page=${page}`);
  };

  return (
    <div className="chat-container">
      <Header />

      <div className="chat-box">
        {messages.map((msg, idx) => (
          <div key={idx} className={msg.sender === "user" ? "message user" : "message bot"}>
            <div>{msg.text}</div>
            {msg.sender === "bot" && msg.sources && msg.sources.length > 0 && (
              <div className="sources">
                <strong>Sources:</strong>
                <ul>
                  {msg.sources.map(([src, page], i) => (
                    <li key={i}>
                      <button onClick={() => handleSourceClick(src, page)} className="source-link">
                        {src} (p. {page})
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}

        {/* Thinking bubble while waiting */}
        {loading && (
          <div className="message bot thinking" aria-live="polite" aria-label="Assistant is thinking">
            <div className="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
      </div>

      {/* Chat input */}
      <div className="chat-input">
        <div className="input-wrapper">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
          />
          {input.trim() && (
            <button onClick={handleSend} disabled={loading}>
              {loading ? (
                <svg viewBox="0 0 24 24" width="18" height="18" className="btn-spinner">
                  <circle cx="12" cy="12" r="10" stroke="white" strokeWidth="3" fill="none" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="white" viewBox="0 0 24 24">
                  <path d="M2 21l21-9L2 3v7l15 2-15 2v7z" />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ...existing imports
import React, { useEffect, useState } from "react";
import "./chatbot.scss";

export default function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

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

  return (
    <div className="chat-container">
      <h1 className="brand-name">Qubo</h1>

      <div className="chat-box">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={msg.sender === "user" ? "message user" : "message bot"}
          >
            <div>{msg.text}</div>
            {msg.sender === "bot" && msg.sources && msg.sources.length > 0 && (
              <div className="sources">
                <strong>Sources:</strong>
                <ul>
                  {msg.sources.map(([src, page], i) => (
                    <li key={i}>
                      {src} (p. {page})
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}

        {/* 👇 Thinking bubble while waiting */}
        {loading && (
          <div
            className="message bot thinking"
            aria-live="polite"
            aria-label="Assistant is thinking"
          >
            <div className="typing-dots" aria-hidden="true">
              <span></span><span></span><span></span>
            </div>
            <div className="typing-shimmer" aria-hidden="true">
              <div className="shimmer-line"></div>
              <div className="shimmer-line short"></div>
            </div>
          </div>
        )}
      </div>

      <div className="chat-input">
        <div className="input-wrapper">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            // optional: prevent typing during loading
            // disabled={loading}
          />
          {input.trim() && (
            <button onClick={handleSend} disabled={loading}>
              {loading ? (
                // optional tiny spinner in the button
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

import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "./Header";
import "./chatbot.scss";

export default function Chatbot() {
  // ✅ Initialize from localStorage immediately (no mount flicker)
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem("chatMessages");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // ✅ Always persist messages (even if empty) so stale data isn’t reloaded
  useEffect(() => {
    localStorage.setItem("chatMessages", JSON.stringify(messages));
  }, [messages]);

  // 👉 (Optional) auto-scroll to the latest message
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Handle sending message
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    // Build next state first so we use the same array for UI + network
    const userMsg = { sender: "user", text: input };
    const nextMessages = [...messages, userMsg];

    setLoading(true);
    setMessages(nextMessages);
    setInput("");

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // ✅ Send the same messages we just put in state
        body: JSON.stringify(
          nextMessages.map(({ sender, text }) => ({ sender, text }))
        ),
      });

      const data = await response.json();

      const botMsg = {
        sender: "bot",
        text: data?.response ?? "(No response)",
        sources: data?.sources ?? [],
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (error) {
      console.error("Error communicating with the backend:", error);
      setMessages((prev) => [
        ...prev,
        {
          sender: "bot",
          text: "Sorry, I couldn’t reach the server.",
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Handle click on a source to navigate to the PDF viewer
  const handleSourceClick = (fileName, page) => {
    navigate(`/view-pdf?file=${encodeURIComponent(fileName)}&page=${page}`);
  };

  return (
    <div className="chat-container">
      <Header />

      <div className={`chat-box ${messages.length > 0 ? "has-messages" : "empty"}`}>
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={msg.sender === "user" ? "message user" : "message bot"}
          >
            <div>{msg.text}</div>

            {msg.sender === "bot" && msg.sources?.length > 0 && (
              <div className="sources">
                <strong>Sources:</strong>
                <ul>
                  {msg.sources.map(([src, page], i) => (
                    <li key={i}>
                      <button
                        onClick={() => handleSourceClick(src, page)}
                        className="source-link"
                      >
                        {src} (p. {page})
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
       
        {loading && (
          <div
            className="message bot thinking"
            aria-live="polite"
            aria-label="Assistant is thinking"
          >
            <div className="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}

        {/* anchor for auto-scroll */}
        <div ref={endRef} />
      </div>

      {/* Chat input */}
       {messages.length === 0 && (
          <div className="no-messages">
            <p> Hello</p>
          </div>
        )}

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
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  className="btn-spinner"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="white"
                    strokeWidth="3"
                    fill="none"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="18"
                  height="18"
                  fill="white"
                  viewBox="0 0 24 24"
                >
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

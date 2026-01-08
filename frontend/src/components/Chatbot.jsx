import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "./Header";
import "./chatbot.scss";
import { useSource } from "../context/SourceContext";
import { useUser } from "../context/UserContext";

export default function Chatbot() {
  const { user } = useUser();

  const textareaRef = useRef(null);
  const MAX_HEIGHT = 140; // px (≈ 6–7 lines depending on line-height)
  const MIN_HEIGHT = 48; // px
  const { source, clearSource } = useSource();

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  // ✅ Initialize from localStorage immediately (no mount flicker)
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem("chatMessages");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto"; // reset
    const next = Math.min(el.scrollHeight, MAX_HEIGHT);
    el.style.height = `${Math.max(next, MIN_HEIGHT)}px`;
    el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [input]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

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
    const userMsg = { sender: "user", text: input, source };
    const nextMessages = [...messages, userMsg];

    setLoading(true);
    setMessages(nextMessages);
    setInput("");

    try {
      // Build payload once; include `source` ONLY if it exists

      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // ✅ Send the same messages we just put in state
        body: JSON.stringify(
          nextMessages.map(({ sender, text, source }) => ({
            sender,
            text,
            source,
          }))
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
    setInput("");
    const el = textareaRef.current;
    if (el) {
      el.style.height = `${MIN_HEIGHT}px`;
      el.style.overflowY = "hidden";
    }
  };

  // Handle click on a source to navigate to the PDF viewer
  const handleSourceClick = (fileName, page) => {
    navigate(`/view-pdf?file=${encodeURIComponent(fileName)}&page=${page}`);
  };

  return (
    <div className="chat-container">
      <Header />

      <div
        className={`chat-box ${messages.length > 0 ? "has-messages" : "empty"}`}
      >
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
          <p className="greeting-message">
            Hello{user?.username && ` ${user.username}.`} I'm Qubo
          </p>
        </div>
      )}

      <div className="chat-input">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Qubo"
            rows={1}
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

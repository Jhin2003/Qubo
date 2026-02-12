import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import Header from "./Header";
import "./chatbot.scss";
import { useSource } from "../context/SourceContext";
import { useUser } from "../context/UserContext";
import ChatActions from "./Actions/ChatActions";

export default function Chatbot() {
  const { user } = useUser();
  const textareaRef = useRef(null);
  const MAX_HEIGHT = 140;
  const MIN_HEIGHT = 48;
  const { source } = useSource(); // removed clearSource if unused

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  // --- 1. NEW: Ref to hold the AbortController ---
  const abortControllerRef = useRef(null);

  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem("chatMessages");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [mode, setMode] = useState("precise");

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
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

  useEffect(() => {
    localStorage.setItem("chatMessages", JSON.stringify(messages));
  }, [messages]);

  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const renderMessageText = (text) => {
    if (!text) return null;
    let cleanedText = text.replace(/\*\*/g, ""); 

    // 2. Replace asterisks used as bullets with a real bullet point
    // This regex looks for a "*" or "-" at the start of a line followed by a space
    cleanedText = cleanedText.replace(/(^|\n)[\*|-] /g, "$1• ");

    const parts = cleanedText.split(/(\[.*?\])/g);
    return parts.map((part, index) => {
      if (part.startsWith("[") && part.endsWith("]")) {
        const content = part.slice(1, -1);
        const [fileNameRaw, pageRaw] = content.split(",");
        if (fileNameRaw && pageRaw) {
          const cleanFileName = fileNameRaw.trim();
          const cleanPage = pageRaw.trim();
          const displayContent = content.replace(/\.pdf/gi, "");
          return (
            <span
              key={index}
              className="citation-pill"
              title={`View ${cleanFileName} on page ${cleanPage}`}
              onClick={() => handleSourceClick(cleanFileName, cleanPage)}
            >
              [{displayContent}]
            </span>
          );
        }
      }
      return part;
    });
  };

  const handleNewChat = () => {
    // 1. Clear the React state so the UI updates immediately
    setMessages([]);

    // 2. Remove the specific key from local storage
    localStorage.removeItem("chatMessages");

    // 3. Optional: Close the menu if you want
    // (This happens automatically if you pass setShowMenu to ChatActions,
    // but usually clearing the chat is enough feedback)
  };

  // --- 2. NEW: Cancel Handler ---
  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort(); // Cancel the fetch request
      abortControllerRef.current = null;
    }
    setLoading(false); // Stop UI loading state
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMsg = { sender: "user", text: input, source };
    const nextMessages = [...messages, userMsg];

    setLoading(true);
    setMessages(nextMessages);
    setInput("");

    // Create new AbortController for this specific request
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // Attach the signal to the fetch call
        signal: controller.signal,
        body: JSON.stringify(
          nextMessages.map(({ sender, text, source }) => ({
            sender,
            text,
            source,
            mode: mode,
          })),
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
      // Check if the error was caused by us cancelling
      if (error.name === "AbortError") {
        console.log("Request cancelled by user");
        setMessages((prev) => prev.slice(0, -1));
        setInput(userMsg.text);
        // Optional: You could add a small "Cancelled" message to the chat
      } else {
        console.error("Error communicating with the backend:", error);
        setMessages((prev) => [
          ...prev,
          {
            sender: "bot",
            text: "Sorry, I couldn’t reach the server.",
            sources: [],
          },
        ]);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }

    const el = textareaRef.current;
    if (el) {
      el.style.height = `${MIN_HEIGHT}px`;
      el.style.overflowY = "hidden";
    }
  };

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
            <div className="message-content">{renderMessageText(msg.text)}</div>

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
          <div className="message bot thinking" aria-live="polite">
            <div className="typing-dots">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {messages.length === 0 && (
        <div className="no-messages">
          <p className="greeting-message">
            Hello, {user?.username ? `${user.username}, ` : ""}I'm Qubo
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
            // Disable input while loading so they can't type new stuff while waiting
            disabled={loading}
          />

          {/* --- 3. NEW: Button Logic (Show Cancel if loading, Send if typing) --- */}
          {(input.trim() || loading) && (
            <button
              // Toggle functionality based on loading state
              onClick={loading ? handleCancel : handleSend}
              className={loading ? "stop-btn" : "send-btn"}
              title={loading ? "Stop generating" : "Send message"}
            >
              {loading ? (
                // STOP ICON (Square)
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="white"
                >
                  <rect x="6" y="6" width="12" height="12" rx="2" ry="2" />
                </svg>
              ) : (
                // SEND ICON (Arrow)
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
        <ChatActions
          onNewChat={handleNewChat}
          mode={mode} // Pass current state
          setMode={setMode}
        />
      </div>
    </div>
  );
}

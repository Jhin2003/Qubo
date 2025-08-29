import { useState } from "react";
import './chatbot.scss';

export default function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const handleSend = async () => {
    if (!input.trim()) return;

    // Update the state with the user message
    setMessages((prev) => [
      ...prev,
      { sender: "user", text: input }
    ]);

    // Send the message to the backend (FastAPI)
    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify([
          ...messages.map(msg => ({ sender: msg.sender, text: msg.text })),
          { sender: "user", text: input }
        ])
      });

      const data = await response.json();
      // Update the state with the bot's response
      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: data.response }
      ]);

      setInput(""); // Clear input field
    } catch (error) {
      console.error("Error communicating with the backend:", error);
    }
  };

  return (
    <div className="chat-container">
      <h1>Chatbot</h1>
      <div className="chat-box">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={msg.sender === "user" ? "message user" : "message bot"}
          >
            {msg.text}
          </div>
        ))}
      </div>
      <div className="chat-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
        />
        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
}

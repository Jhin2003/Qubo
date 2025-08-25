import { useState } from "react";
import './chatbot.css';
export default function Chatbot() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages([...messages, { sender: "user", text: input }]);
    
    // Simulate bot response
    setMessages(prev => [
      ...prev,
      { sender: "user", text: input },
      { sender: "bot", text: "This is a simulated bot response." }
    ]);

    setInput(""); // Clear input
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

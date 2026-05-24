import { useState, useRef, useEffect } from "react";
import Message from "./Message";
import { sendMessage } from "./api";

const SUGGESTIONS = [
  "My order ORD-1001 is late, can I get a refund?",
  "Where is order ORD-1004?",
  "Do you have the wireless headphones in stock?",
  "Order ORD-1007 never arrived",
  "What are the specs on the running shoes?",
];

export default function App() {
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const bottomRef                 = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(text) {
    const userText = text ?? input;
    if (!userText.trim() || loading) return;
    setInput("");

    const newMessages = [...messages, { role: "user", content: userText }];
    setMessages(newMessages);
    setLoading(true);

    try {
      const result = await sendMessage(
        newMessages.map(({ role, content }) => ({ role, content }))
      );
      setMessages([
        ...newMessages,
        { role: "assistant", content: result.response, toolsUsed: result.tools_used },
      ]);
    } catch (e) {
      setMessages([
        ...newMessages,
        { role: "assistant", content: "Something went wrong. Please try again.", toolsUsed: [] },
      ]);
    }

    setLoading(false);
  }

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100vh",
      maxWidth: "720px",
      margin: "0 auto",
      fontFamily: "system-ui, sans-serif",
    }}>

      {/* Header */}
      <div style={{
        padding: "16px 24px",
        borderBottom: "1px solid #e5e5e5",
        display: "flex",
        alignItems: "center",
        gap: "10px",
      }}>
        <div style={{
          width: "32px", height: "32px", borderRadius: "50%",
          background: "#4466cc", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "14px", fontWeight: 700,
        }}>A</div>
        <div>
          <div style={{ fontWeight: 600, fontSize: "15px" }}>Aria</div>
          <div style={{ fontSize: "12px", color: "#888" }}>ShopFlow Support Agent</div>
        </div>
        <div style={{
          marginLeft: "auto", fontSize: "12px",
          color: "#22aa66", fontWeight: 500,
        }}>● online</div>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "#999", marginTop: "60px" }}>
            <div style={{ fontSize: "32px", marginBottom: "12px" }}>🛍</div>
            <div style={{ fontSize: "15px", marginBottom: "24px" }}>
              Hi! I'm Aria, ShopFlow's support agent.<br />
              Ask me about orders, refunds, or products.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", alignItems: "center" }}>
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  style={{
                    background: "#f5f5f5", border: "1px solid #e0e0e0",
                    borderRadius: "20px", padding: "8px 16px",
                    fontSize: "13px", color: "#444", cursor: "pointer",
                    maxWidth: "400px", width: "100%",
                  }}
                >{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <Message key={i} role={m.role} content={m.content} toolsUsed={m.toolsUsed} />
        ))}

        {loading && (
          <div style={{ color: "#999", fontSize: "13px", padding: "4px 0" }}>
            Aria is typing...
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        padding: "16px 24px",
        borderTop: "1px solid #e5e5e5",
        display: "flex",
        gap: "10px",
      }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
          placeholder="Ask about an order or product..."
          disabled={loading}
          style={{
            flex: 1, padding: "10px 16px",
            borderRadius: "24px", border: "1px solid #ddd",
            fontSize: "14px", outline: "none",
          }}
        />
        <button
          onClick={() => submit()}
          disabled={!input.trim() || loading}
          style={{
            padding: "10px 20px", borderRadius: "24px",
            background: "#4466cc", color: "#fff",
            border: "none", fontSize: "14px",
            cursor: input.trim() && !loading ? "pointer" : "not-allowed",
            opacity: input.trim() && !loading ? 1 : 0.5,
          }}
        >Send</button>
      </div>
    </div>
  );
}
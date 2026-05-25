import { useState, useRef, useEffect } from "react";
import Message from "./Message";
import AgentActivity from "./AgentActivity";
import { streamMessage } from "./api";

const API_URL = import.meta.env.VITE_API_URL || "";

const SUGGESTIONS = [
  "My order ORD-1001 is late, can I get a refund?",
  "Order ORD-1007 never arrived",
  "What's your return policy for damaged items?",
  "Do you have the wireless headphones in stock?",
  "Someone used my account to place ORD-1009 without permission",
];

export default function App() {
  const [messages, setMessages]   = useState([]);
  const [activity, setActivity]   = useState([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetMsg, setResetMsg]   = useState("");
  const bottomRef                 = useRef(null);
  const inputRef                  = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function resetDemo() {
    setResetting(true);
    setResetMsg("");
    try {
      await fetch(`${API_URL}/reset`, { method: "POST" });
      setMessages([]);
      setActivity([]);
      setResetMsg("reset done");
      setTimeout(() => setResetMsg(""), 2000);
    } catch {
      setResetMsg("reset failed");
      setTimeout(() => setResetMsg(""), 2000);
    }
    setResetting(false);
  }

  async function submit(text) {
    const userText = (text ?? input).trim();
    if (!userText || loading) return;

    setInput("");
    setActivity([]);

    const newMessages = [...messages, { role: "user", content: userText }];
    setMessages(newMessages);
    setLoading(true);

    const apiMessages = newMessages.map(({ role, content }) => ({ role, content }));

    try {
      for await (const event of streamMessage(apiMessages)) {
        if (event.type === "tool_start") {
          setActivity(prev => [...prev, {
            id: event.id, tool: event.tool,
            input: event.input, status: "running", result: null,
          }]);
        } else if (event.type === "tool_result") {
          setActivity(prev => prev.map(a =>
            a.id === event.id
              ? { ...a, result: event.result, status: event.result?.error ? "error" : "done" }
              : a
          ));
        } else if (event.type === "response") {
          setMessages(prev => [...prev, { role: "assistant", content: event.text }]);
          setLoading(false);
        } else if (event.type === "error") {
          setMessages(prev => [...prev, { role: "assistant", content: "Something went wrong. Please try again." }]);
          setLoading(false);
        }
      }
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "Connection error. Please try again." }]);
      setLoading(false);
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>

      <style>{`
        .body-inner {
          display: flex;
          flex-direction: row;
          flex: 1;
          overflow: hidden;
        }
        .chat-panel {
          flex: 0 0 60%;
          display: flex;
          flex-direction: column;
          border-right: 1px solid #1a1d2e;
          overflow: hidden;
        }
        .console-panel {
          flex: 0 0 40%;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        @media (max-width: 768px) {
          .body-inner { flex-direction: column; overflow-y: auto; }
          .chat-panel {
            flex: 0 0 auto;
            min-height: 50vh;
            border-right: none;
            border-bottom: 1px solid #1a1d2e;
          }
          .console-panel {
            flex: 0 0 auto;
            min-height: 40vh;
          }
        }
      `}</style>

      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "12px 20px",
        borderBottom: "1px solid #1a1d2e",
        background: "#0b0d1a", flexShrink: 0,
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: "50%",
          background: "linear-gradient(135deg, #4338ca, #7c6df5)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 13, fontWeight: 700, color: "#fff",
        }}>S</div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#e2e6f0" }}>Sage</div>
          <div style={{ fontSize: 11, color: "#4a5380" }}>ShopFlow Support Agent</div>
        </div>

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <button
            onClick={resetDemo}
            disabled={resetting || loading}
            style={{
              background: "transparent",
              border: "1px solid #252a45",
              borderRadius: 6,
              padding: "4px 12px",
              fontSize: 11,
              fontFamily: "'JetBrains Mono', monospace",
              color: resetMsg === "reset done" ? "#3ecf8e" : resetMsg === "reset failed" ? "#f87171" : "#4a5380",
              cursor: resetting || loading ? "not-allowed" : "pointer",
              transition: "all 0.2s",
            }}
            onMouseEnter={e => { if (!resetting && !loading) e.target.style.borderColor = "#7c6df5"; }}
            onMouseLeave={e => { e.target.style.borderColor = "#252a45"; }}
          >
            {resetting ? "resetting..." : resetMsg || "reset demo"}
          </button>

          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            fontSize: 11, color: "#3ecf8e",
          }}>
            <div style={{
              width: 6, height: 6, borderRadius: "50%", background: "#3ecf8e",
              animation: "pulse 2s ease-in-out infinite",
            }} />
            online
          </div>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        <div className="body-inner">

          {/* Chat panel */}
          <div className="chat-panel">
            <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

              {isEmpty && (
                <div style={{
                  display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center",
                  paddingTop: 24, gap: 16,
                }}>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 28, marginBottom: 8 }}>🛍</div>
                    <div style={{ fontSize: 15, color: "#6b7ab5", lineHeight: 1.7 }}>
                      Hi, I'm Sage.<br />How can I help you today?
                    </div>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, width: "100%", maxWidth: 360 }}>
                    {SUGGESTIONS.map(s => (
                      <button key={s} onClick={() => submit(s)} style={{
                        background: "#13162b", border: "1px solid #252a45",
                        borderRadius: 8, padding: "9px 14px",
                        fontSize: 12, color: "#8892c4", cursor: "pointer",
                        textAlign: "left", transition: "border-color 0.15s, color 0.15s",
                        fontFamily: "inherit",
                      }}
                      onMouseEnter={e => { e.target.style.borderColor = "#7c6df5"; e.target.style.color = "#e2e6f0"; }}
                      onMouseLeave={e => { e.target.style.borderColor = "#252a45"; e.target.style.color = "#8892c4"; }}
                      >{s}</button>
                    ))}
                  </div>
                </div>
              )}

              {messages.map((m, i) => (
                <Message key={i} role={m.role} content={m.content} />
              ))}

              {loading && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: "50%",
                    background: "#1c2040", border: "1px solid #252a45",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 600, color: "#7c6df5",
                  }}>S</div>
                  <div style={{ display: "flex", gap: 4 }}>
                    {[0, 1, 2].map(i => (
                      <div key={i} style={{
                        width: 5, height: 5, borderRadius: "50%",
                        background: "#4a5380",
                        animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                      }} />
                    ))}
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div style={{
              padding: "14px 20px",
              borderTop: "1px solid #1a1d2e",
              display: "flex", gap: 8, flexShrink: 0,
            }}>
              <input
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && submit()}
                placeholder="Ask about an order or product..."
                disabled={loading}
                style={{
                  flex: 1, padding: "10px 14px",
                  background: "#13162b", border: "1px solid #252a45",
                  borderRadius: 8, fontSize: 13, color: "#e2e6f0",
                  outline: "none", fontFamily: "inherit",
                  transition: "border-color 0.15s",
                }}
                onFocus={e => e.target.style.borderColor = "#7c6df5"}
                onBlur={e => e.target.style.borderColor = "#252a45"}
              />
              <button
                onClick={() => submit()}
                disabled={!input.trim() || loading}
                style={{
                  padding: "10px 18px",
                  background: input.trim() && !loading ? "#4338ca" : "#13162b",
                  border: "1px solid",
                  borderColor: input.trim() && !loading ? "#4338ca" : "#252a45",
                  borderRadius: 8, fontSize: 13, fontWeight: 500,
                  color: input.trim() && !loading ? "#fff" : "#4a5580",
                  cursor: input.trim() && !loading ? "pointer" : "not-allowed",
                  transition: "all 0.15s", fontFamily: "inherit",
                }}
              >Send</button>
            </div>
          </div>

          {/* Console panel */}
          <div className="console-panel">
            <AgentActivity activity={activity} loading={loading} />
          </div>

        </div>
      </div>
    </div>
  );
}
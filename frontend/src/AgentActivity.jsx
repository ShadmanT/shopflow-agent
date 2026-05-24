const TOOL_META = {
  check_order_status:   { label: "check_order_status",   color: "#7c6df5" },
  process_refund:       { label: "process_refund",        color: "#3ecf8e" },
  check_inventory:      { label: "check_inventory",       color: "#f59e0b" },
  get_product_info:     { label: "get_product_info",      color: "#60a5fa" },
  escalate_to_human:    { label: "escalate_to_human",     color: "#f87171" },
  search_knowledge_base:{ label: "search_knowledge_base", color: "#a78bfa" },
};

function Spinner() {
  return (
    <div style={{
      width: 12, height: 12, border: "2px solid #252a45",
      borderTopColor: "#7c6df5", borderRadius: "50%",
      animation: "spin 0.7s linear infinite", flexShrink: 0,
    }} />
  );
}

function ToolCard({ item }) {
  const meta = TOOL_META[item.tool] ?? { label: item.tool, color: "#7c6df5" };
  const isDone  = item.status === "done";
  const isError = item.status === "error";

  return (
    <div style={{
      background: "#13162b",
      border: `1px solid ${isDone ? meta.color + "55" : "#252a45"}`,
      borderLeft: `3px solid ${isError ? "#f87171" : isDone ? meta.color : "#252a45"}`,
      borderRadius: "6px",
      padding: "12px 14px",
      animation: "slideUp 0.2s ease",
      transition: "border-color 0.3s",
    }}>
      {/* Tool name + status */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        {item.status === "running" && <Spinner />}
        {isDone  && <span style={{ color: "#3ecf8e", fontSize: 13 }}>✓</span>}
        {isError && <span style={{ color: "#f87171", fontSize: 13 }}>✗</span>}
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 12, fontWeight: 500,
          color: meta.color,
        }}>{meta.label}</span>
      </div>

      {/* Input */}
      <div style={{ marginBottom: item.result ? 8 : 0 }}>
        <div style={{
          fontSize: 10, color: "#4a5380", fontFamily: "'JetBrains Mono', monospace",
          letterSpacing: "0.06em", marginBottom: 4,
        }}>INPUT</div>
        <pre style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11, color: "#8892c4", lineHeight: 1.5,
          background: "#0b0d1a", borderRadius: 4, padding: "6px 8px",
          overflow: "auto", maxHeight: 80, whiteSpace: "pre-wrap", wordBreak: "break-all",
        }}>{JSON.stringify(item.input, null, 2)}</pre>
      </div>

      {/* Result */}
      {item.result && (
        <div style={{ animation: "slideUp 0.2s ease" }}>
          <div style={{
            fontSize: 10, color: "#4a5380", fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: "0.06em", marginBottom: 4,
          }}>OUTPUT</div>
          <pre style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: isError ? "#f87171" : "#3ecf8e",
            lineHeight: 1.5,
            background: "#0b0d1a", borderRadius: 4, padding: "6px 8px",
            overflow: "auto", maxHeight: 120, whiteSpace: "pre-wrap", wordBreak: "break-all",
          }}>{JSON.stringify(item.result, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default function AgentActivity({ activity, loading }) {
  const isEmpty = activity.length === 0;

  return (
    <div style={{
      flex: "0 0 40%",
      display: "flex",
      flexDirection: "column",
      background: "#0b0d1a",
      overflow: "hidden",
    }}>
      {/* Console header */}
      <div style={{
        padding: "14px 18px",
        borderBottom: "1px solid #1a1d2e",
        display: "flex", alignItems: "center", gap: 8,
        flexShrink: 0,
      }}>
        <div style={{
          width: 7, height: 7, borderRadius: "50%",
          background: loading ? "#7c6df5" : "#252a45",
          animation: loading ? "pulse 1.2s ease-in-out infinite" : "none",
          transition: "background 0.3s",
        }} />
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11, fontWeight: 500,
          color: "#4a5380", letterSpacing: "0.1em", textTransform: "uppercase",
        }}>Agent console</span>
        {loading && (
          <span style={{
            marginLeft: "auto", fontSize: 10,
            color: "#7c6df5", fontFamily: "'JetBrains Mono', monospace",
            animation: "blink 1s step-end infinite",
          }}>executing_</span>
        )}
      </div>

      {/* Events */}
      <div style={{
        flex: 1, overflowY: "auto",
        padding: isEmpty ? "0" : "14px",
        display: "flex", flexDirection: "column", gap: 8,
      }}>
        {isEmpty && (
          <div style={{
            flex: 1, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            color: "#252a45", gap: 10,
          }}>
            <div style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11, textAlign: "center", lineHeight: 1.8,
            }}>
              {"// tool calls will appear\n// here in real time"}
            </div>
          </div>
        )}
        {activity.map((item) => (
          <ToolCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  );
}
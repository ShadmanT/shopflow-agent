import ToolBadge from "./ToolBadge";

export default function Message({ role, content, toolsUsed }) {
  const isUser = role === "user";

  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "16px",
    }}>
      <div style={{ maxWidth: "70%" }}>
        {/* Tool badges — only on agent messages */}
        {!isUser && toolsUsed?.length > 0 && (
          <div style={{ marginBottom: "6px" }}>
            {toolsUsed.map((t) => <ToolBadge key={t} tool={t} />)}
          </div>
        )}

        <div style={{
          padding: "12px 16px",
          borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
          background: isUser ? "#4466cc" : "#f1f1f1",
          color: isUser ? "#fff" : "#111",
          fontSize: "14px",
          lineHeight: "1.6",
          whiteSpace: "pre-wrap",
        }}>
          {content}
        </div>
      </div>
    </div>
  );
}
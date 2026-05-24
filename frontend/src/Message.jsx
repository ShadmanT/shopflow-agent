export default function Message({ role, content }) {
  const isUser = role === "user";

  return (
    <div style={{
      display: "flex",
      justifyContent: isUser ? "flex-end" : "flex-start",
      marginBottom: "14px",
      animation: "slideUp 0.2s ease",
    }}>
      {!isUser && (
        <div style={{
          width: 28, height: 28, borderRadius: "50%",
          background: "#1c2040", border: "1px solid #252a45",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 11, fontWeight: 600, color: "#7c6df5",
          marginRight: 8, flexShrink: 0, marginTop: 2,
        }}>A</div>
      )}

      <div style={{
        maxWidth: "75%",
        padding: "10px 14px",
        borderRadius: isUser
          ? "16px 16px 4px 16px"
          : "16px 16px 16px 4px",
        background: isUser ? "#3730a3" : "#13162b",
        border: isUser ? "none" : "1px solid #1c2040",
        fontSize: 14,
        lineHeight: 1.65,
        color: isUser ? "#e8eaf6" : "#c8cce8",
        whiteSpace: "pre-wrap",
      }}>
        {content}
      </div>
    </div>
  );
}
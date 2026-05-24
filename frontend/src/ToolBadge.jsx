const TOOL_LABELS = {
  check_order_status: "checked order",
  process_refund:     "processed refund",
  check_inventory:    "checked inventory",
  get_product_info:   "looked up product",
  escalate_to_human:  "escalated to human",
};

export default function ToolBadge({ tool }) {
  return (
    <span style={{
      fontSize: "11px",
      padding: "2px 8px",
      borderRadius: "10px",
      background: "#f0f4ff",
      color: "#4466cc",
      fontFamily: "monospace",
      marginRight: "6px",
    }}>
      ⚙ {TOOL_LABELS[tool] ?? tool}
    </span>
  );
}
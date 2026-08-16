import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";

/**
 * Alert — thông báo lỗi/thành công (§8: lỗi nói rõ nguyên nhân + hướng xử lý).
 */
const KINDS = {
  error: { cls: "border-danger/30 bg-danger/5 text-danger", Icon: CircleAlert },
  success: { cls: "border-success/30 bg-success/5 text-success", Icon: CircleCheck },
  info: { cls: "border-primary/30 bg-primary-soft text-primary", Icon: Info },
  warn: { cls: "border-warning/40 bg-warning/5 text-warning", Icon: TriangleAlert },
};

export function Alert({ kind = "error", children, onClose }) {
  const { cls, Icon } = KINDS[kind] ?? KINDS.error;
  return (
    <div
      className={`flex items-start gap-2.5 border rounded-lg px-4 py-3 text-sm mb-4 ${cls}`}
      role={kind === "error" ? "alert" : undefined}
    >
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="whitespace-pre-line flex-1">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          className="shrink-0 opacity-60 hover:opacity-100 cursor-pointer"
          aria-label="Đóng thông báo"
        >
          <X size={14} />
        </button>
      )}
    </div>
  );
}

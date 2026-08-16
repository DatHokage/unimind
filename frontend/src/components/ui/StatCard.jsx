/**
 * Ô số liệu tổng quan (dashboard). Số dùng tabular-nums (§2.2).
 */
const TONE_CLS = {
  neutral: "text-primary",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
};

export function StatCard({ label, value, tone = "neutral" }) {
  const valueCls = TONE_CLS[tone] ?? TONE_CLS.neutral;
  return (
    <div className="bg-surface border border-border rounded-lg shadow-sm px-4 py-3.5">
      <div className="text-sm text-secondary">{label}</div>
      <div className={`text-2xl font-semibold mt-1 num ${valueCls}`}>{value}</div>
    </div>
  );
}

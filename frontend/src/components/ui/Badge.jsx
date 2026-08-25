/**
 * Badge trạng thái — frontend.md §2.1 (màu theo ngữ nghĩa) & §2.3 (bo 6px).
 * soft = nền nhạt chữ đậm (badge trong bảng); solid = nền đậm chữ trắng.
 */
const SOFT = {
  neutral: "bg-app text-secondary",
  info: "bg-primary-soft text-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
};

const SOLID = {
  neutral: "bg-secondary text-white",
  info: "bg-primary text-white",
  success: "bg-success text-white",
  warning: "bg-warning text-white",
  danger: "bg-danger text-white",
};

export function Badge({ tone = "neutral", solid = false, className = "", children, ...rest }) {
  const palette = solid ? SOLID : SOFT;
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ${palette[tone] ?? palette.neutral} ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}

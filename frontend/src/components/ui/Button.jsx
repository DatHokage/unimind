import { forwardRef } from "react";

/**
 * Nút hành động chuẩn hóa — frontend.md §2.1/§2.3.
 * Màu primary CHỈ dành cho hành động chính (§2.1), các mức còn lại trung tính.
 * Transition 150ms cho hover (§9 — không animation trang trí).
 */
const VARIANTS = {
  primary:
    "bg-primary text-white hover:bg-primary-hover disabled:bg-primary/50 shadow-sm",
  secondary:
    "bg-surface text-primary border border-border hover:bg-primary-soft hover:border-primary/40 disabled:opacity-50",
  ghost: "bg-transparent text-secondary hover:bg-app disabled:opacity-50",
  danger:
    "bg-transparent text-danger hover:bg-danger/10 disabled:opacity-50",
};

const SIZES = {
  sm: "text-xs px-2.5 py-1.5 gap-1.5",
  md: "text-sm px-4 py-2 gap-2",
};

export const Button = forwardRef(function Button(
  { variant = "primary", size = "md", className = "", children, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      type="button"
      className={`inline-flex items-center justify-center rounded-md font-medium transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
});

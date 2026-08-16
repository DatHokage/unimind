import { ChevronLeft, ChevronRight } from "lucide-react";

/**
 * Phân trang server-side — dùng kèm API trả về { data, page, size, totalElements, totalPages }.
 * Số dùng tabular-nums (§2.2); nút thứ cấp (ghost), không nút primary — phân trang là điều hướng, không phải hành động chính (§2.1).
 * Không render gì khi chỉ có 1 trang hoặc không có dữ liệu.
 */
export function Pagination({ page, totalPages, onPageChange, className = "" }) {
  if (totalPages <= 1) return null;
  return (
    <div className={`flex items-center justify-end gap-1 px-4 py-3 border-t border-border ${className}`}>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-secondary hover:bg-app disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 0}
        aria-label="Trang trước"
      >
        <ChevronLeft size={14} /> Trước
      </button>
      <span className="text-sm text-secondary num px-2">
        Trang {page + 1}/{totalPages}
      </span>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium text-secondary hover:bg-app disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150 cursor-pointer"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages - 1}
        aria-label="Trang sau"
      >
        Sau <ChevronRight size={14} />
      </button>
    </div>
  );
}

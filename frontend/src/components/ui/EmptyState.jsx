/**
 * Trạng thái rỗng — frontend.md §7/§8: không để bảng trống trơn,
 * luôn kèm gợi ý hành động tiếp theo. Icon đơn sắc (§9), không illustration màu mè.
 */
export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      {Icon && <Icon size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />}
      <p className="text-sm font-medium text-primary">{title}</p>
      {description && <p className="text-sm text-secondary mt-1">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

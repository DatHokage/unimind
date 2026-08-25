/**
 * Khối xám nhấp nháy thay spinner toàn trang: khung trang vẽ được NGAY khi
 * route mở (FCP/LCP không còn chờ API), dữ liệu về thì thay nội dung thật.
 * Dùng kèm className để tạo hình: <Skeleton className="h-4 w-32" />.
 */
export function Skeleton({ className = "" }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-border/60 ${className}`} />;
}

/** Cụm skeleton cho một Card chứa bảng — dùng chung cho các trang dashboard. */
export function SkeletonCard({ rows = 4 }) {
  return (
    <div className="bg-surface border border-border rounded-lg shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <Skeleton className="h-5 w-40" />
      </div>
      <div className="divide-y divide-border/60">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="px-4 py-3.5 flex items-center gap-4">
            <Skeleton className="h-3.5 w-6" />
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="h-3.5 flex-1 max-w-[220px]" />
            <Skeleton className="h-3.5 w-20 ml-auto" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Skeleton nguyên trang danh sách (dòng mô tả + card bảng) — các trang "… của tôi". */
export function SkeletonListPage({ rows = 4 }) {
  return (
    <div className="space-y-4">
      <Skeleton className="h-4 w-72" />
      <SkeletonCard rows={rows} />
    </div>
  );
}

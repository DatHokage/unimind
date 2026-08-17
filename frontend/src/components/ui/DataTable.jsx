import { Inbox } from "lucide-react";

/**
 * Bảng dữ liệu chuẩn hóa — frontend.md §7 (thành phần dùng nhiều nhất).
 *
 * columns: [{ key, label, align?: "left"|"right"|"center", className? }]
 * rows: mảng object; render qua `renderRow(row, i)` để page tự kiểm soát ô đặc biệt.
 * `sttStart` (tùy chọn): bật cột STT ở đầu bảng — số thứ tự của hàng đầu tiên.
 * Các trang admin phân trang truyền `page * PAGE_SIZE + 1` để STT chạy liên tục
 * qua các trang. Khi bật, `renderRow` nhận thêm ô STT đã render sẵn ở tham số
 * thứ ba (`renderRow(row, i, sttCell)`) — đặt `{sttCell}` làm ô đầu của hàng.
 * Cột số liệu căn phải + tabular-nums (§2.2); header nền app, hàng hover nhẹ (§7).
 */
export function DataTable({
  columns,
  rows = [],
  rowKey,
  renderRow,
  empty,
  sttStart = null,
  className = "",
}) {
  const withStt = sttStart != null;
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-app">
            {withStt && (
              <th className="w-12 px-3 py-2.5 text-center text-sm font-semibold text-secondary whitespace-nowrap border-b border-border">
                STT
              </th>
            )}
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-4 py-2.5 text-sm font-semibold text-secondary whitespace-nowrap border-b border-border ${
                  c.align === "right"
                    ? "text-right"
                    : c.align === "center"
                      ? "text-center"
                      : "text-left"
                }`}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-surface">
          {rows.map((row, i) =>
            renderRow(
              row,
              i,
              withStt ? (
                <td key="stt" className="px-3 py-2.5 align-middle whitespace-nowrap text-center text-secondary num">
                  {sttStart + i}
                </td>
              ) : null
            )
          )}
        </tbody>
      </table>
      {rows.length === 0 && (empty ?? <DataTableDefaultEmpty />)}
    </div>
  );
}

/** Ô tiêu chuẩn: text thường. */
export function Cell({ className = "", children }) {
  return (
    <td className={`px-4 py-2.5 align-middle whitespace-nowrap ${className}`}>
      {children}
    </td>
  );
}

/** Ô số liệu (điểm, tín chỉ, sĩ số): căn phải + tabular-nums (§2.2/§7). */
export function NumCell({ className = "", children }) {
  return <Cell className={`text-right num ${className}`}>{children}</Cell>;
}

/** Hàng chuẩn: hover nhẹ để dò theo hàng ngang (§7). */
export function Row({ children, className = "" }) {
  return (
    <tr className={`border-b border-border last:border-0 hover:bg-app transition-colors duration-150 ${className}`}>
      {children}
    </tr>
  );
}

function DataTableDefaultEmpty() {
  return (
    <div className="flex flex-col items-center py-12 text-center">
      <Inbox size={36} strokeWidth={1.5} className="text-secondary/60 mb-3" />
      <p className="text-sm text-secondary">Chưa có dữ liệu.</p>
    </div>
  );
}

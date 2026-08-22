/** Kiểu dáng form dùng chung cho các trang quản lý (office). */
export const INPUT_CLS =
  "w-full border border-border rounded-lg px-3 py-2 text-sm bg-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150";

/**
 * Dropdown gọn hơn INPUT_CLS: padding dọc mỏng hơn, cao ~32px để ngồi
 * ngang hàng với nút bấm trên thanh lọc, không phình to như ô nhập liệu.
 */
export const SELECT_CLS =
  "border border-border rounded-md px-2.5 py-1.5 text-sm bg-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150";

export const LABEL_CLS = "block text-sm font-medium mb-1";

/**
 * Ô nhập gọn cho thanh lọc (Năm, Kỳ…) — giống SELECT_CLS nhưng KHÔNG có
 * w-full sẵn trong class (INPUT_CLS có w-full nên ghép width vào sẽ xung đột,
 * ô vẫn giãn dài bất chấp w-16/w-20 đặt sau).
 */
export const INPUT_FILTER_CLS =
  "border border-border rounded-md px-2.5 py-1.5 text-sm bg-surface focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors duration-150";

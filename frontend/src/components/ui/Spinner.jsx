import { Loader2 } from "lucide-react";

export function Spinner({ label = "Đang tải…" }) {
  return (
    <div className="flex items-center gap-2 text-secondary text-sm py-12 justify-center">
      <Loader2 size={16} className="animate-spin" />
      {label}
    </div>
  );
}

import { Link, useLocation } from "react-router-dom";
import { Menu as MenuIcon, Plus } from "lucide-react";
import { getPageMeta } from "../../config/routeTitles";
import { Button } from "../ui";

/**
 * Header vùng nội dung — frontend.md §6:
 * trái = tiêu đề trang theo route (KHÔNG lặp tên hệ thống),
 * phải = nút hành động chính của trang nếu có.
 */
export default function Header({ onMenuClick }) {
  const { pathname } = useLocation();
  const meta = getPageMeta(pathname);

  return (
    <header className="sticky top-0 z-20 h-14 bg-surface border-b border-border flex items-center gap-3 px-4 lg:px-6">
      {/* Hamburger — chỉ hiện dưới 768px (§3) */}
      <button
        onClick={onMenuClick}
        className="md:hidden text-secondary hover:text-primary p-1 cursor-pointer"
        aria-label="Mở menu"
      >
        <MenuIcon size={20} />
      </button>

      {/* min-w-0 BẮT BUỘC: không có nó thì flex con không co thấp hơn nội dung,
          truncate thành vô dụng → tiêu đề dài đẩy nút hành động tràn ngang màn
          hình điện thoại (chỉ trang admin có cả tiêu đề dài + nút "+ ..."). */}
      <h1 className="text-2xl font-semibold truncate min-w-0">{meta.title}</h1>

      {meta.action && (
        <div className="ml-auto shrink-0">
          <Link to={meta.action.to} state={meta.action.state}>
            <Button variant="primary" aria-label={meta.action.label}>
              <Plus size={16} />
              {/* Dưới 640px chỉ còn icon: tiêu đề dài nhất + nút vẫn vừa ~320px */}
              <span className="hidden sm:inline">{meta.action.label}</span>
            </Button>
          </Link>
        </div>
      )}
    </header>
  );
}

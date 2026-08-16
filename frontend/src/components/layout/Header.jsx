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

      <h1 className="text-2xl font-semibold truncate">{meta.title}</h1>

      {meta.action && (
        <div className="ml-auto shrink-0">
          <Link to={meta.action.to} state={meta.action.state}>
            <Button variant="primary">
              <Plus size={16} />
              {meta.action.label}
            </Button>
          </Link>
        </div>
      )}
    </header>
  );
}

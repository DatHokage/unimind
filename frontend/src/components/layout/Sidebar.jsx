import { LogOut, PanelLeftClose, PanelLeft, LifeBuoy } from "lucide-react";
import { MENU } from "../../config/menuConfig";
import { useAuth, ROLE_LABELS, ROLE_TONES, initials } from "../../context/AuthContext";
import { Badge, Button } from "../ui";
import SidebarMenuItem from "./SidebarMenuItem";

/**
 * Sidebar — frontend.md §5: rộng 260px, collapse còn 72px (chỉ icon),
 * trên cùng branding + user, giữa là menu theo role, dưới cùng đăng xuất/hỗ trợ.
 */
export default function Sidebar({ collapsed, onToggle, mobileOpen, onCloseMobile }) {
  const { user, logout } = useAuth();
  const groups = MENU[user?.role] ?? [];
  const displayName = user?.name || user?.username || "";

  return (
    <>
      {/* Nền che khi sidebar mobile mở (<768px, §3) */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 md:hidden"
          onClick={onCloseMobile}
          aria-hidden
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex flex-col bg-surface border-r border-border transition-all duration-200
          ${collapsed ? "md:w-[72px]" : "md:w-[260px]"} w-[260px]
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
      >
        {/* §5.1 — Branding */}
        <div className="flex items-center gap-2.5 h-14 px-4 border-b border-border shrink-0">
          <img src="/favicon.svg" alt="UniMind" className="w-10 h-10 shrink-0" />
          {!collapsed && (
            <span className="text-lg font-semibold text-primary leading-tight">UniMind</span>
          )}
        </div>

        {/* §5.1 — User: avatar, tên, badge vai trò */}
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border shrink-0">
          <span className="w-9 h-9 rounded-full bg-primary-soft text-primary text-xs font-semibold flex items-center justify-center shrink-0">
            {initials(displayName)}
          </span>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-medium truncate" title={displayName}>
                {displayName}
              </div>
              <Badge tone={ROLE_TONES[user?.role] ?? "neutral"} className="mt-0.5">
                {ROLE_LABELS[user?.role] ?? user?.role}
              </Badge>
            </div>
          )}
        </div>

        {/* §5.2 — Menu chia nhóm theo role */}
        <nav className="flex-1 overflow-y-auto px-3 py-3">
          {groups.map((group) => (
            <div key={group.title} className="mb-4">
              {!collapsed && (
                <div className="px-3 mb-1.5 text-xs font-medium uppercase tracking-wide text-secondary">
                  {group.title}
                </div>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <SidebarMenuItem
                    key={item.label}
                    item={item}
                    collapsed={collapsed}
                    onNavigate={onCloseMobile}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* §5.3 — Đáy sidebar: hỗ trợ + đăng xuất, tách bằng đường border */}
        <div className="border-t border-border px-3 py-3 space-y-0.5 shrink-0">
          <div
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-secondary"
            title="Liên hệ phòng đào tạo khi cần hỗ trợ"
          >
            <LifeBuoy size={18} className="shrink-0" />
            {!collapsed && <span>Liên hệ phòng đào tạo</span>}
          </div>
          <button
            onClick={logout}
            title="Đăng xuất"
            className="w-full flex items-center gap-3 rounded-md px-3 py-2 text-sm text-secondary hover:bg-danger/10 hover:text-danger transition-colors duration-150 cursor-pointer"
          >
            <LogOut size={18} className="shrink-0" />
            {!collapsed && <span>Đăng xuất</span>}
          </button>
        </div>

        {/* Nút thu gọn/mở rộng — desktop (hữu ích với bảng dữ liệu rộng, §3) */}
        <div className="hidden md:block border-t border-border p-2 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggle}
            className="w-full"
            title={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
          >
            {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
            {!collapsed && "Thu gọn"}
          </Button>
        </div>
      </aside>
    </>
  );
}

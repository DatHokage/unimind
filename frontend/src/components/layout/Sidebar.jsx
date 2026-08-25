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
      {/* h-dvh (100dvh) thay vì inset-y-0: trên điện thoại, inset-y-0 lấy chiều cao
          LAYOUT viewport (đếm cả phần browser bar chiếm chỗ) → footer Đăng xuất/
          Liên hệ bị đẩy xuống dưới vùng nhìn thấy (mất nút trên mobile, lỗi /office).
          100dvh bám theo visual viewport nên đáy drawer luôn trên màn hình. */}
      <aside
        className={`fixed top-0 left-0 z-40 flex flex-col h-dvh bg-surface border-r border-border transition-all duration-200
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
              <div className="text-sm font-medium truncate">{displayName}</div>
              <Badge tone={ROLE_TONES[user?.role] ?? "neutral"} className="mt-0.5">
                {ROLE_LABELS[user?.role] ?? user?.role}
              </Badge>
            </div>
          )}
        </div>

        {/* §5.2 — Menu chia nhóm theo role.
            min-h-0 BẮT BUỘC: không có nó thì flex con không co thấp hơn nội dung
            → sidebar cao hơn màn hình điện thoại, nút Đăng xuất bị đẩy chìm dưới
            đáy (phải cuộn mới thấy). Có nó thì nav tự cuộn trong, đáy luôn ghim. */}
        <nav className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-3 py-3">
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

        {/* §5.3 — Đáy sidebar: hỗ trợ + đăng xuất, tách bằng đường border.
            paddingBottom theo safe-area để không bị vệt home-indicator iPhone che. */}
        <div
          className="border-t border-border px-3 py-2 space-y-0.5 shrink-0"
          style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
        >
          <div
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-secondary"
          >
            <LifeBuoy size={18} className="shrink-0" />
            {!collapsed && <span>Liên hệ phòng đào tạo</span>}
          </div>
          <button
            onClick={logout}
            aria-label="Đăng xuất"
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
          >
            {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
            {!collapsed && "Thu gọn"}
          </Button>
        </div>
      </aside>
    </>
  );
}
